#!/usr/bin/env python3

"""
Run REDbot as a daemon.
"""

import argparse
from configparser import ConfigParser, SectionProxy
import cProfile
import faulthandler
from functools import partial
import io
import locale
import os
from pstats import Stats
import sys
import traceback
from typing import Dict, Optional
from urllib.parse import urlsplit

from importlib_resources import files as resource_files

import httplint
import thor
from thor.loop import _loop

import redbot
from redbot.type import RawHeaderListType
from redbot.webui import RedWebUi
from redbot.webui.saved_tests import clean_saved_tests

if os.environ.get("SYSTEMD_WATCHDOG"):
    try:
        from cysystemd.daemon import notify, Notification  # type: ignore
    except ImportError:
        sys.stderr.write("WARNING: watchdog enabled, but csystemd not available.\n")
        notify = Notification = None  # pylint: disable=invalid-name
else:
    notify = Notification = None  # pylint: disable=invalid-name

_loop.precision = 0.2

# dump stack on faults
faulthandler.enable()


class RedBotServer:
    """Run REDbot as a standalone Web server."""

    watchdog_freq = 3

    def __init__(self, config: SectionProxy) -> None:
        self.config = config
        self.handler = partial(RedHandler, server=self)

        # Set up the watchdog
        if notify is not None:
            thor.schedule(self.watchdog_freq, self.watchdog_ping)

        # Read static files
        self.static_root = os.path.join("/", config["static_root"]).encode("ascii")
        self.static_files = resource_files("redbot.assets")
        self.extra_files = {}
        if self.config.get("extra_base_dir"):
            self.extra_files = self.walk_files(self.config["extra_base_dir"])

        # Start garbage collection
        if config.get("save_dir", ""):
            thor.schedule(10, self.gc_state)

        # Set up the server
        server = thor.http.HttpServer(
            self.config.get("host", "").encode("utf-8"),
            self.config.getint("port", fallback=8000),
        )
        server.on("exchange", self.handler)
        try:
            thor.run()
        except KeyboardInterrupt:
            self.console("Stopping...")
            thor.stop()

    def watchdog_ping(self) -> None:
        notify(Notification.WATCHDOG)
        thor.schedule(self.watchdog_freq, self.watchdog_ping)

    def gc_state(self) -> None:
        clean_saved_tests(self.config)
        thor.schedule(self.config.getint("gc_mins", fallback=2) * 60, self.gc_state)

    def walk_files(self, dir_name: str, uri_base: bytes = b"") -> Dict[bytes, bytes]:
        out: Dict[bytes, bytes] = {}
        for root, _, files in os.walk(dir_name):
            for name in files:
                try:
                    path = os.path.join(root, name)
                    uri = os.path.relpath(path, dir_name).encode("utf-8")
                    with open(path, "rb") as fh:
                        out[b"/%s%s" % (uri_base, uri)] = fh.read()
                    if uri.endswith(b"/index.html"):
                        with open(path, "rb") as fh:
                            out[b"/%s%s" % (uri_base, uri[:-11])] = fh.read()
                except IOError:
                    self.console(f"Problem loading static file {path}")
        return out

    @staticmethod
    def console(message: str) -> None:
        sys.stderr.write(f"{message}\n")


class RedHandler:
    static_types = {
        b".html": b"text/html",
        b".js": b"text/javascript",
        b".css": b"text/css",
        b".png": b"image/png",
        b".txt": b"text/plain",
        b".woff": b"font/woff",
        b".ttf": b"font/ttf",
        b".eot": b"application/vnd.ms-fontobject",
        b".svg": b"image/svg+xml",
    }

    def __init__(
        self, exchange: thor.http.server.HttpServerExchange, server: RedBotServer
    ) -> None:
        self.exchange = exchange
        self.server = server
        self.method = b""
        self.uri = b""
        self.req_hdrs: RawHeaderListType = []
        self.req_body = b""
        exchange.on("request_start", self.request_start)
        exchange.on("request_body", self.request_body)
        exchange.on("request_done", self.request_done)

    def request_start(
        self, method: bytes, uri: bytes, req_hdrs: RawHeaderListType
    ) -> None:
        self.method = method
        self.uri = uri
        self.req_hdrs = req_hdrs

    def request_body(self, chunk: bytes) -> None:
        self.req_body += chunk

    def request_done(self, trailers: RawHeaderListType) -> None:
        p_uri = urlsplit(self.uri)
        if p_uri.path == b"/":
            client_ip = self.exchange.http_conn.tcp_conn.socket.getpeername()[0]
            try:
                RedWebUi(
                    self.server.config,
                    self.method.decode(self.server.config["charset"]),
                    p_uri.query,
                    self.req_hdrs,
                    self.req_body,
                    self.exchange,
                    client_ip,
                    self.server.console,
                )
                return None
            except Exception:  # pylint: disable=broad-except
                self.server.console(
                    """
*** FATAL ERROR
REDbot has encountered a fatal error which it really, really can't recover from
in standalone server mode. Details follow.
"""
                )

                dump = traceback.format_exc()
                thor.stop()
                self.server.console(dump)
                sys.exit(1)
        else:
            return self.serve_static(p_uri.path)

    def serve_static(self, path: bytes) -> None:
        path = os.path.normpath(path)
        if path.startswith(self.server.static_root + b"/"):
            path = b"/".join(path.split(b"/")[2:])
            try:
                with self.server.static_files.joinpath(path.decode("ascii")).open(
                    mode="rb"
                ) as fh:
                    content = fh.read()
            except OSError:
                return self.not_found(path)
        else:
            try:
                content = self.server.extra_files[path]
            except (KeyError, TypeError):
                return self.not_found(path)
        file_ext = os.path.splitext(path)[1].lower() or b".html"
        content_type = self.static_types.get(file_ext, b"application/octet-stream")
        headers = []
        headers.append((b"Content-Type", content_type))
        headers.append((b"Cache-Control", b"max-age=86400"))
        self.exchange.response_start(b"200", b"OK", headers)
        self.exchange.response_body(content)
        self.exchange.response_done([])
        return None

    def not_found(self, path: bytes) -> None:
        headers = []
        headers.append((b"Content-Type", b"text/plain"))
        headers.append((b"Cache-Control", b"max-age=3600"))
        self.exchange.response_start(b"404", b"Not Found", headers)
        self.exchange.response_body(b"'%s' not found." % path)
        self.exchange.response_done([])


def print_debug(message: str, profile: Optional[cProfile.Profile]) -> None:
    sys.stderr.write(f"WARNING: {message}\n\n")
    if profile:
        st = io.StringIO()
        ps = Stats(profile, stream=st).sort_stats("cumulative")
        ps.print_stats(15)
        sys.stderr.write(f"{st.getvalue()}\n")


_loop.debug_out = print_debug  # type: ignore


def main() -> None:
    parser = argparse.ArgumentParser(description="REDbot daemon")
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        dest="debug",
        help="Dump slow operations to STDERR",
    )
    parser.add_argument(
        "config_file", type=argparse.FileType("r"), help="configuration file"
    )
    args = parser.parse_args()
    conf = ConfigParser()
    conf.read_file(args.config_file)

    try:
        locale.setlocale(locale.LC_ALL, locale.normalize(conf["redbot"]["lang"]))
    except locale.Error:  # Catch more general locale-related error
        print("Warning: Failed to set locale from config. Using default 'en' locale.")
        locale.setlocale(locale.LC_ALL, "en_US.UTF-8")  # Default to English locale

    if args.debug:
        _loop.debug = True

    sys.stderr.write(
        f"Starting REDbot {redbot.__version__} on PID {os.getpid()}"
        + f" (thor {thor.__version__}; httplint {httplint.__version__})\n"
        + f"http://{conf['redbot'].get('host', '')}:{conf['redbot']['port']}/\n"
    )

    RedBotServer(conf["redbot"])


if __name__ == "__main__":
    main()
