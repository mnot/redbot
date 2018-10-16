#!/usr/bin/env python

"""
A Web UI for RED, the Resource Expert Droid.
"""


import locale
import os
import sys
from urllib.parse import urlsplit

from redbot import __version__
from redbot.resource.robot_fetch import RobotFetcher
from redbot.formatter import html
from redbot.webui import RedWebUi, except_handler_factory

import thor
from thor.loop import _loop
_loop.precision = .1

### Configuration ##########################################################

class Config:
    """
    Configuration object.
    """

    # Output language (not working yet; see #169)
    lang = "en"

    # Output character set. No real reason to change from UTF-8...
    charset = "utf-8"

    # Where to store exceptions; set to None to disable traceback logging
    exception_dir = 'exceptions'

    # how many seconds to allow a check to run for
    max_runtime = 60

    # Where to keep files for future reference, when users save them. None to disable.
    save_dir = '/var/state/redbot/'

    # how long to store things when users save them, in days.
    save_days = 30

    # show errors in the browser; boolean
    debug = False  # DEBUG_CONTROL

    # domains which we reject requests for when they're in the referer.
    referer_spam_domains = ['www.youtube.com']

    # log when total traffic is bigger than this (in bytes), so we can catch abuse
    # None to disable; 0 to log all.
    log_traffic = 1024 * 1024 * 8

# Where to cache robots.txt
RobotFetcher.robot_cache_dir = "/var/state/robots-txt/" if not Config.debug else False

# directory containing files to append to the front page; None to disable
html.extra_dir = "extra"

# URI root for static assets (absolute or relative, but no trailing '/')
html.static_root = 'static'


### End configuration ######################################################


try:
    locale.setlocale(locale.LC_ALL, locale.normalize(Config.lang))
except:
    locale.setlocale(locale.LC_ALL, '')


def cgi_main():
    """Run REDbot as a CGI Script."""
    def out(inbytes):
        try:
            sys.stdout.buffer.write(inbytes)
            sys.stdout.flush()
        except IOError:
            pass

    ui_uri = "%s://%s%s%s" % (
        'HTTPS' in os.environ and "https" or "http",
        os.environ.get('HTTP_HOST'),
        os.environ.get('SCRIPT_NAME'),
        os.environ.get('PATH_INFO', ''))
    method = os.environ.get('REQUEST_METHOD').encode(Config.charset)
    query_string = os.environ.get('QUERY_STRING', "").encode(Config.charset)

    def response_start(code, phrase, res_hdrs):
        out_v = [b"Status: %s %s" % (code, phrase)]
        for k, v in res_hdrs:
            out_v.append(b"%s: %s" % (k, v))
        out_v.append(b"")
        out_v.append(b"")
        out(b"\n".join(out_v))

    freak_ceiling = 20000
    def response_body(chunk):
        rest = None
        if len(chunk) > freak_ceiling:
            rest = chunk[freak_ceiling:]
            chunk = chunk[:freak_ceiling]
        out(chunk)
        if rest:
            response_body(rest)

    def response_done(trailers):
        thor.schedule(0, thor.stop)
    try:
        RedWebUi(Config, ui_uri, method, query_string,
                 response_start, response_body, response_done)
        thor.run()
    except:
        except_handler_factory(Config, qs=query_string)()


def standalone_main(host, port, static_dir):
    """Run REDbot as a standalone Web server."""

    # load static files
    static_types = {
        '.js': b'text/javascript',
        '.css': b'text/css',
        '.png': b'image/png',
    }
    static_files = {}
    for root, dirs, files in os.walk(static_dir):
        for name in files:
            try:
                path = os.path.join(root, name)
                uri = os.path.relpath(path, static_dir)
                static_files[b"/static/%s" % uri.encode('utf-8')] = open(path, 'rb').read()
            except IOError:
                sys.stderr.write("* Problem loading %s\n" % path)

    def red_handler(x):
        @thor.events.on(x)
        def request_start(method, uri, req_hdrs):
            p_uri = urlsplit(uri)
            if p_uri.path in static_files:
                headers = []
                file_ext = os.path.splitext(p_uri.path)[1].lower()
                content_encoding = static_types.get(file_ext, b'application/octet-stream')
                headers.append((b'Content-Encoding', content_encoding))
                headers.append((b'Cache-Control', b'max-age=300'))
                x.response_start(b"200", b"OK", headers)
                x.response_body(static_files[p_uri.path])
                x.response_done([])
            elif p_uri.path == b"/":
                try:
                    RedWebUi(Config, '/', method, p_uri.query,
                             x.response_start, x.response_body, x.response_done)
                except Exception:
                    sys.stderr.write("""

*** FATAL ERROR
REDbot has encountered a fatal error which it really, really can't recover from
in standalone server mode. Details follow.

""")
                    import traceback
                    traceback.print_exc()
                    thor.stop()
            else:
                x.response_start(b"404", b"Not Found", [])
                x.response_done([])

    server = thor.http.HttpServer(host, port)
    server.on('exchange', red_handler)

    try:
        thor.run()
    except KeyboardInterrupt:
        sys.stderr.write("Stopping...\n")
        thor.stop()

def standalone_monitor(host, port, static_dir):
    """Fork a process as a standalone Web server and watch it."""
    from multiprocessing import Process
    while True:
        p = Process(target=standalone_main, args=(host, port, static_dir))
        sys.stderr.write("* Starting REDbot server...\n")
        p.start()
        p.join()


if __name__ == "__main__":
    if 'GATEWAY_INTERFACE' in os.environ:  # CGI
        cgi_main()
    else:
        # standalone server
        from optparse import OptionParser
        usage = "Usage: %prog [options] port static_dir"
        version = "REDbot version %s" % __version__
        option_parser = OptionParser(usage=usage, version=version)
        (options, args) = option_parser.parse_args()
        if len(args) < 2:
            option_parser.error("Please specify a port and a static directory.")
        try:
            port = int(args[0])
        except ValueError:
            option_parser.error("Port is not an integer.")

        static_dir = args[1]
        sys.stderr.write(
            "Starting standalone server on PID %s...\n" % os.getpid() + \
            "http://localhost:%s/\n" % port)

        standalone_main("", port, static_dir)
