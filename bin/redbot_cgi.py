#!/usr/bin/env python

"""
A CGI-based Web UI for RED, the Resource Expert Droid.
"""

from configparser import ConfigParser, SectionProxy
import locale
import os
import sys

import thor
from thor.loop import _loop

from redbot.type import RawHeaderListType, HttpResponseExchange
from redbot.webui import RedWebUi

_loop.precision = 0.1


def cgi_main(config: SectionProxy) -> None:
    """Run REDbot as a CGI Script."""

    def out(inbytes: bytes) -> None:
        try:
            sys.stdout.buffer.write(inbytes)
            sys.stdout.flush()
        except IOError:
            pass

    config["ui_uri"] = (
        f'{"HTTPS" in os.environ and "https" or "http"}://'
        f'{os.environ.get("HTTP_HOST")}'
        f'{os.environ.get("SCRIPT_NAME")}'
        f'{os.environ.get("PATH_INFO", "")}'
    )
    method = os.environ.get("REQUEST_METHOD").encode(config["charset"])
    query_string = os.environ.get("QUERY_STRING", "").encode(config["charset"])
    req_hdrs: RawHeaderListType = []
    for (key, val) in os.environ.items():
        if key[:5] == "HTTP_":
            req_hdrs.append((key[:5].lower().encode("ascii"), val.encode("ascii")))
    req_body = sys.stdin.read().encode("utf-8")

    class Exchange(HttpResponseExchange):
        def response_start(
            self, status_code: bytes, status_phrase: bytes, res_hdrs: RawHeaderListType
        ) -> None:
            out_v = [b"Status: %s %s" % (status_code, status_phrase)]
            for name, value in res_hdrs:
                out_v.append(b"%s: %s" % (name, value))
            out_v.append(b"")
            out_v.append(b"")
            out(b"\n".join(out_v))

        def response_body(self, chunk: bytes) -> None:
            freak_ceiling = 20000
            rest = None
            if len(chunk) > freak_ceiling:
                rest = chunk[freak_ceiling:]
                chunk = chunk[:freak_ceiling]
            out(chunk)
            if rest:
                self.response_body(rest)

        def response_done(self, trailers: RawHeaderListType) -> None:
            thor.schedule(0, thor.stop)

    RedWebUi(
        config,
        method.decode(config["charset"]),
        query_string,
        req_hdrs,
        req_body,
        Exchange(),
    )
    thor.run()


if __name__ == "__main__":
    conf = ConfigParser()
    conf.read(os.environ.get("REDBOT_CONFIG", "config.txt"))
    redconf = conf["redbot"]

    try:
        locale.setlocale(locale.LC_ALL, locale.normalize(redconf["lang"]))
    except ValueError:
        locale.setlocale(locale.LC_ALL, "")

    if "GATEWAY_INTERFACE" in os.environ:  # CGI
        cgi_main(redconf)
