#!/usr/bin/env python

"""
A CGI-based Web UI for RED, the Resource Expert Droid.
"""

from configparser import ConfigParser
import locale
import os
import sys

import thor
from thor.loop import _loop

from redbot import __version__
from redbot.webui import RedWebUi, except_handler_factory

_loop.precision = .1



def cgi_main(config):
    """Run REDbot as a CGI Script."""
    def out(inbytes):
        try:
            sys.stdout.buffer.write(inbytes)
            sys.stdout.flush()
        except IOError:
            pass

    config['ui_uri'] = "%s://%s%s%s" % (
        'HTTPS' in os.environ and "https" or "http",
        os.environ.get('HTTP_HOST'),
        os.environ.get('SCRIPT_NAME'),
        os.environ.get('PATH_INFO', ''))
    method = os.environ.get('REQUEST_METHOD').encode(config['charset'])
    query_string = os.environ.get('QUERY_STRING', "").encode(config['charset'])

    def response_start(code, phrase, res_hdrs):
        out_v = [b"Status: %s %s" % (code, phrase)]
        for name, value in res_hdrs:
            out_v.append(b"%s: %s" % (name, value))
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
        RedWebUi(config, method, query_string, response_start, response_body, response_done)
        thor.run()
    except Exception:
        except_handler_factory(config, qs=query_string)()


if __name__ == "__main__":
    config = ConfigParser()
    config.read(os.environ.get('REDBOT_CONFIG', "config.txt"))
    redconf = config['redbot']

    try:
        locale.setlocale(locale.LC_ALL, locale.normalize(redconf['lang']))
    except ValueError:
        locale.setlocale(locale.LC_ALL, '')

    if 'GATEWAY_INTERFACE' in os.environ:  # CGI
        cgi_main(redconf)
