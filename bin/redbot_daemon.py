#!/usr/bin/env python3

"""
Run REDbot as a daemon.
"""

from configparser import ConfigParser, SectionProxy
from functools import partial
import locale
import os
import signal
import sys
import traceback
from types import FrameType
from typing import Dict
from urllib.parse import urlsplit

import thor
from thor.events import EventEmitter
from thor.loop import _loop

from redbot import __version__
from redbot.type import RawHeaderListType
from redbot.webui import RedWebUi

if os.environ.get("SYSTEMD_WATCHDOG"):
    try:
        from cysystemd.daemon import notify, Notification
    except ImportError:
        notify = Notification = None
else:
    notify = Notification = None

_loop.precision = 0.1


class RedBotServer:
    """Run REDbot as a standalone Web server."""

    watchdog_freq = 5

    def __init__(self, config: SectionProxy) -> None:
        self.config = config
        self.handler = partial(RedHandler, server=self)

        sys.stderr.write(f"Starting REDbot {__version__} (thor {thor.__version__}).")

        # Set up the watchdog
        if notify is not None:
            thor.schedule(self.watchdog_freq, self.watchdog_ping)
            signal.signal(signal.SIGABRT, self.abrt_handler)

        # Read static files
        self.static_files = self.walk_files(self.config["asset_dir"], b"static/")
        if self.config.get("extra_base_dir"):
            self.static_files.update(self.walk_files(self.config["extra_base_dir"]))

        # Set up the server
        server = thor.http.HttpServer(
            self.config.get("host", "").encode('utf-8'), int(self.config["port"])
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

    def abrt_handler(self, signum: int, frame: FrameType) -> None:
        sys.stderr.write("* ABORT\n")
        traceback.print_stack(frame)
        sys.exit(0)

    @staticmethod
    def walk_files(dir_name: str, base: bytes = b"") -> Dict[bytes, bytes]:
        out = {}  # type: Dict[bytes, bytes]
        for root, dirs, files in os.walk(dir_name):
            for name in files:
                try:
                    path = os.path.join(root, name)
                    uri = os.path.relpath(path, dir_name).encode("utf-8")
                    out[b"/%s%s" % (base, uri)] = open(path, "rb").read()
                    if uri.endswith(b"/index.html"):
                        out[b"/%s%s" % (base, uri[:-10])] = open(path, "rb").read()
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

    def __init__(self, exchange: EventEmitter, server: RedBotServer) -> None:
        self.exchange = exchange
        self.config = server.config
        self.static_files = server.static_files
        self.method = b""
        self.uri = b""
        self.req_hdrs = []  # type: RawHeaderListType
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
            headers.append((b"Cache-Control", b"max-age=3600"))
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
            except Exception:
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

    def error_log(self, message: str) -> None:
        sys.stderr.write(f"{message}\n")


if __name__ == "__main__":

    from optparse import OptionParser

    usage = "Usage: %prog configfile"
    version = f"REDbot version {__version__}"
    option_parser = OptionParser(usage=usage, version=version)
    (options, args) = option_parser.parse_args()
    if len(args) < 1:
        option_parser.error("Please specify a config file.")

    conf = ConfigParser()
    conf.read(args[0])
    config = conf["redbot"]

    try:
        locale.setlocale(locale.LC_ALL, locale.normalize(config["lang"]))
    except ValueError:
        locale.setlocale(locale.LC_ALL, "")

    sys.stderr.write(
        f"Starting on PID {os.getpid()}...\n"
        + f"http://{config.get('host', '')}:{config['port']}/\n"
    )

    RedBotServer(config)
