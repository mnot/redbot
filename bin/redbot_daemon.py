#!/usr/bin/env python3

"""
Run REDbot as a daemon.
"""

from configparser import ConfigParser, SectionProxy
import locale
import os
import sys
from typing import Dict
from urllib.parse import urlsplit

import thor
from thor.events import EventEmitter
from thor.loop import _loop

if os.environ.get("SYSTEMD_WATCHDOG"):
    from systemd.daemon import notify, Notification

from redbot import __version__
from redbot.type import RawHeaderListType
from redbot.webui import RedWebUi

_loop.precision = .1


class RedBotServer:
    """Run REDbot as a standalone Web server."""

    static_types = {
        b'.html': b'text/html',
        b'.js': b'text/javascript',
        b'.css': b'text/css',
        b'.png': b'image/png',
        b'.txt': b'text/plain'
    }
    watchdog_freq = 5

    def __init__(self, config: SectionProxy) -> None:
        self.config = config
        self.static_files = {}    # type: Dict[bytes, bytes]
        # Load static files
        self.walk_files(config['asset_dir'], b"static/")
        if config.get('extra_base_dir'):
            self.walk_files(config['extra_base_dir'])
        # Set up the watchdog
        if os.environ.get("SYSTEMD_WATCHDOG"):
            thor.schedule(self.watchdog_freq, self.watchdog_ping)
        # Set up the server
        server = thor.http.HttpServer(config.get('host', ''), int(config['port']))
        server.on('exchange', self.red_handler)
        try:
            thor.run()
        except KeyboardInterrupt:
            sys.stderr.write("Stopping...\n")
            thor.stop()

    def walk_files(self, dir_name: str, base: bytes = b"") -> None:
        for root, dirs, files in os.walk(dir_name):
            for name in files:
                try:
                    path = os.path.join(root, name)
                    uri = os.path.relpath(path, dir_name).encode('utf-8')
                    self.static_files[b"/%s%s" % (base, uri)] = open(path, 'rb').read()
                    if uri.endswith(b"/index.html"):
                        self.static_files[b"/%s%s" % (base, uri[:-10])] = open(path, 'rb').read()
                except IOError:
                    sys.stderr.write("* Problem loading %s\n" % path)

    def red_handler(self, x: EventEmitter) -> None:
        @thor.events.on(x)
        def request_start(method: bytes, uri: bytes, req_hdrs: RawHeaderListType) -> None:
            p_uri = urlsplit(uri)
            if p_uri.path in self.static_files:
                file_ext = os.path.splitext(p_uri.path)[1].lower() or b'.html'
                content_type = self.static_types.get(file_ext, b'application/octet-stream')
                headers = []
                headers.append((b'Content-Type', content_type))
                headers.append((b'Cache-Control', b'max-age=3600'))
                x.response_start(b"200", b"OK", headers)
                x.response_body(self.static_files[p_uri.path])
                x.response_done([])
            elif p_uri.path == b"/":
                try:
                    req_hdrs.append(
                      (b'client-ip', x.http_conn.tcp_conn.socket.getpeername()[0].encode('idna')))
                    RedWebUi(self.config,
                             method.decode(self.config['charset']), p_uri.query, req_hdrs,
                             x, self.error_log)
                except Exception:
                    self.error_log("""

*** FATAL ERROR
REDbot has encountered a fatal error which it really, really can't recover from
in standalone server mode. Details follow.
""")
                    import traceback
                    dump = traceback.format_exc()
                    thor.stop()
                    self.error_log(dump)
                    sys.exit(1)
            else:
                headers = []
                headers.append((b'Content-Type', b'text/plain'))
                headers.append((b'Cache-Control', b'max-age=3600'))
                x.response_start(b"404", b"Not Found", headers)
                x.response_body(b"'%s' not found." % p_uri.path)
                x.response_done([])

    def error_log(self, message: str) -> None:
        sys.stderr.write("%s\n" % message)

    def watchdog_ping(self) -> None:
        notify(Notification.WATCHDOG)
        thor.schedule(self.watchdog_freq, self.watchdog_ping)



if __name__ == "__main__":

    from optparse import OptionParser
    usage = "Usage: %prog configfile"
    version = "REDbot version %s" % __version__
    option_parser = OptionParser(usage=usage, version=version)
    (options, args) = option_parser.parse_args()
    if len(args) < 1:
        option_parser.error("Please specify a config file.")

    conf = ConfigParser()
    conf.read(args[0])
    redconf = conf['redbot']

    try:
        locale.setlocale(locale.LC_ALL, locale.normalize(redconf['lang']))
    except ValueError:
        locale.setlocale(locale.LC_ALL, '')

    sys.stderr.write(
        "Starting on PID %s...\n" % os.getpid() + \
        "http://%s:%s/\n" % (redconf.get('host', ''), redconf['port']))

    RedBotServer(redconf)
