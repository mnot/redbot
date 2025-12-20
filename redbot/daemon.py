#!/usr/bin/env python3

"""
Run REDbot as a daemon.
"""

import argparse
from configparser import ConfigParser, SectionProxy
import cProfile
from functools import partial
import io
import inspect
import os
from pstats import Stats
import signal
import sys
import traceback
from types import FrameType
from typing import Dict, Optional
from urllib.parse import urlsplit

from importlib_resources import files as resource_files

import httplint
import thor
from thor.loop import _loop
from thor.tcp import TcpConnection

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


class RedBotServer:
    """Run REDbot as a standalone Web server."""

    watchdog_freq = 3

    def __init__(self, config: SectionProxy) -> None:
        self.config = config
        self.handler = partial(RedRequestHandler, server=self)

        # Set up the watchdog
        if notify is not None:
            thor.schedule(self.watchdog_freq, self.watchdog_ping)

        # Read static files
        self.static_root = os.path.join("/", config["static_root"]).encode("ascii")
        self.static_files = resource_files("redbot.assets")
        self.extra_files = {}
        extra_base_dir = self.config.get("extra_base_dir", None)
        if extra_base_dir:
            self.extra_files = self.walk_files(extra_base_dir)

        # Get the UI path we're being served from
        ui_uri_config = self.config.get("ui_uri", "/")
        ui_uri_parsed = urlsplit(ui_uri_config)
        self.ui_path = ui_uri_parsed.path.encode("utf-8")
        if not self.ui_path.endswith(b"/"):
            self.ui_path += b"/"

        # Start garbage collection
        if config.get("save_dir", ""):
            thor.schedule(10, self.gc_state)

        # Set up the server
        self.http_server = thor.http.HttpServer(
            self.config.get("host", "").encode("utf-8"),
            self.config.getint("port", fallback=8000),
        )
        self.http_server.on("exchange", self.handler)

        # Install signal handlers
        for signum in [
            signal.SIGSEGV,
            signal.SIGABRT,
            signal.SIGFPE,
            signal.SIGBUS,
            signal.SIGILL,
        ]:
            signal.signal(signum, self.handle_crash_signal)
        signal.signal(signal.SIGINT, self.shutdown_signal)
        signal.signal(signal.SIGTERM, self.shutdown_signal)

    def run(self) -> None:
        try:
            thor.run()
        except KeyboardInterrupt:
            # this should be handled by the signal handler, but just in case
            self.shutdown()
            thor.run()

    def shutdown_signal(self, sig: int, frame: Optional[FrameType]) -> None:
        self.console("Shutting down...")
        self.shutdown()

    def shutdown(self) -> None:
        self.http_server.on("stop", thor.stop)
        self.http_server.graceful_shutdown()

    def watchdog_ping(self) -> None:
        notify(Notification.WATCHDOG)
        thor.schedule(self.watchdog_freq, self.watchdog_ping)

    def gc_state(self) -> None:
        clean_saved_tests(self.config)
        thor.schedule(self.config.getint("gc_mins", fallback=2) * 60, self.gc_state)

    def handle_crash_signal(
        self, sig: int, frame: Optional[FrameType] = None
    ) -> signal.Handlers:
        self.console(f"*** {signal.strsignal(sig)}\n")
        current_frame = inspect.currentframe()
        assert current_frame
        frame = current_frame.f_back
        assert frame
        traceback.print_stack(frame, limit=1)
        self.console("  * Local Variables")
        for key, val in frame.f_locals.items():
            self.console(f"    {key}: {val}")
        handlers = self.http_server.loop.registered_fd_handlers()
        self.console("  * TCP Connections")
        for handler in handlers:
            if isinstance(handler, TcpConnection):
                self.console(f"    {repr(handler)}")
        self.console("  * Scheduled Events")
        for when, event in self.http_server.loop.scheduled_events():
            self.console(f"    {when:.2f} - {repr(event)}")
        sys.exit(1)

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


class RedRequestHandler:
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
        if not exchange.http_conn.tcp_conn:
            return
        self.client_ip = exchange.http_conn.tcp_conn.socket.getpeername()[0]
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
        try:
            p_uri = urlsplit(self.uri)
        except UnicodeDecodeError:
            return self.bad_request(b"That's not a URL.")
        if (
            p_uri.path.startswith(self.server.static_root + b"/")
            or p_uri.path in self.server.extra_files
            or p_uri.path.rstrip(b"/") in self.server.extra_files
        ):
            return self.serve_static(p_uri.path)

        if p_uri.path.startswith(self.server.ui_path):
            # The path effective relative to the UI URI
            # e.g., /red/foo/bar -> foo/bar
            # defaults to empty string
            ui_path = p_uri.path[len(self.server.ui_path) :]
            client_ip = self.client_ip
            try:
                RedWebUi(
                    self.server.config,
                    self.method.decode(self.server.config.get("charset", "utf-8")),
                    ui_path,
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
            return self.not_found(p_uri.path)

    def serve_static(self, path: bytes) -> None:
        path = os.path.normpath(path)
        if path.startswith(self.server.static_root + b"/"):
            # Strip the static root from the path to get relative file path
            path = path[len(self.server.static_root) + 1 :]
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

    def bad_request(self, why: bytes = b"bad request") -> None:
        headers = []
        headers.append((b"Content-Type", b"text/plain"))
        self.exchange.response_start(b"400", b"Bad Request", headers)
        self.exchange.response_body(why)
        self.exchange.response_done([])


# debugging output
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
    parser.add_argument("config_file", type=str, help="configuration file")
    args = parser.parse_args()
    conf = ConfigParser()
    conf.read(args.config_file)

    if args.debug:
        _loop.debug = True

    sys.stderr.write(
        f"Starting REDbot {redbot.__version__} on PID {os.getpid()}"
        + f" (thor {thor.__version__}; httplint {httplint.__version__})\n"
        + f"http://{conf['redbot'].get('host', '')}:{conf['redbot']['port']}/\n"
    )

    server = RedBotServer(conf["redbot"])
    server.run()


if __name__ == "__main__":
    main()
