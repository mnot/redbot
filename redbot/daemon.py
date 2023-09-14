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

import thor
from thor.loop import _loop

from redbot import __version__
from redbot.type import RawHeaderListType
from redbot.webui import RedWebUi

if os.environ.get("SYSTEMD_WATCHDOG"):
    try:
        from cysystemd.daemon import notify, Notification  # type: ignore
    except ImportError:
        notify = Notification = None  # pylint: disable=invalid-name
else:
    notify = Notification = None  # pylint: disable=invalid-name

_loop.precision = 0.2
_loop.debug = True


def print_debug(message: str, profile: Optional[cProfile.Profile]) -> None:
    sys.stderr.write(f"WARNING: {message}\n\n")
    if profile:
        st = io.StringIO()
        ps = Stats(profile, stream=st).sort_stats("cumulative")
        ps.print_stats(15)
        sys.stderr.write(f"{st.getvalue()}\n")


_loop.debug_out = print_debug  # type: ignore

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
        self.static_files = self.walk_files(self.config["asset_dir"], b"static/")
        if self.config.get("extra_base_dir"):
            self.static_files.update(self.walk_files(self.config["extra_base_dir"]))

        # Set up the server
        server = thor.http.HttpServer(
            self.config.get("host", "").encode("utf-8"), int(self.config["port"])
        )
        server.on("exchange", self.handler)
        try:
            thor.run()
        except KeyboardInterrupt:
            sys.stderr.write("Stopping...\n")
            thor.stop()

    def watchdog_ping(self) -> None:
        notify(Notification.WATCHDOG)
        thor.schedule(self.watchdog_freq, self.watchdog_ping)

    @staticmethod
    def walk_files(dir_name: str, base: bytes = b"") -> Dict[bytes, bytes]:
        out: Dict[bytes, bytes] = {}
        for root, _, files in os.walk(dir_name):
            for name in files:
                try:
                    path = os.path.join(root, name)
                    uri = os.path.relpath(path, dir_name).encode("utf-8")
                    with open(path, "rb") as fh:
                        out[b"/%s%s" % (base, uri)] = fh.read()
                    if uri.endswith(b"/index.html"):
                        with open(path, "rb") as fh:
                            out[b"/%s%s" % (base, uri[:-10])] = fh.read()
                except IOError:
                    sys.stderr.write(f"* Problem loading {path}\n")
        return out


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
        self.config = server.config
        self.static_files = server.static_files
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
        if p_uri.path in self.static_files:
            file_ext = os.path.splitext(p_uri.path)[1].lower() or b".html"
            content_type = self.static_types.get(file_ext, b"application/octet-stream")
            headers = []
            headers.append((b"Content-Type", content_type))
            headers.append((b"Cache-Control", b"max-age=86400"))
            self.exchange.response_start(b"200", b"OK", headers)
            self.exchange.response_body(self.static_files[p_uri.path])
            self.exchange.response_done([])
        elif p_uri.path == b"/":
            try:
                self.req_hdrs.append(
                    (
                        b"client-ip",
                        self.exchange.http_conn.tcp_conn.socket.getpeername()[0].encode(
                            "idna"
                        ),
                    )
                )
                RedWebUi(
                    self.config,
                    self.method.decode(self.config["charset"]),
                    p_uri.query,
                    self.req_hdrs,
                    self.req_body,
                    self.exchange,
                    self.error_log,
                )
            except Exception:  # pylint: disable=broad-except
                self.error_log(
                    """
*** FATAL ERROR
REDbot has encountered a fatal error which it really, really can't recover from
in standalone server mode. Details follow.
"""
                )

                dump = traceback.format_exc()
                thor.stop()
                self.error_log(dump)
                sys.exit(1)
        else:
            headers = []
            headers.append((b"Content-Type", b"text/plain"))
            headers.append((b"Cache-Control", b"max-age=3600"))
            self.exchange.response_start(b"404", b"Not Found", headers)
            self.exchange.response_body(b"'%s' not found." % p_uri.path)
            self.exchange.response_done([])

    @staticmethod
    def error_log(message: str) -> None:
        sys.stderr.write(f"{message}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="REDbot daemon")
    parser.add_argument(
        "config_file", type=argparse.FileType("r"), help="configuration file"
    )
    args = parser.parse_args()
    conf = ConfigParser()
    conf.read_file(args.config_file)

    try:
        locale.setlocale(locale.LC_ALL, locale.normalize(conf["redbot"]["lang"]))
    except ValueError:
        locale.setlocale(locale.LC_ALL, "")

    sys.stderr.write(
        f"Starting on PID {os.getpid()}... (thor {thor.__version__})\n"
        + f"http://{conf['redbot'].get('host', '')}:{conf['redbot']['port']}/\n"
    )

    RedBotServer(conf["redbot"])


if __name__ == "__main__":
    main()
