#!/usr/bin/env python

"""
A CGI-based Web UI for RED, the Resource Expert Droid.
"""

import cgitb
from configparser import ConfigParser, SectionProxy
import locale
import os
import sys
import stat
import traceback
import tempfile
from types import TracebackType
from typing import Callable, Type

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

    try:
        RedWebUi(
            config,
            method.decode(config["charset"]),
            query_string,
            req_hdrs,
            req_body,
            Exchange(),
        )
        thor.run()
    except Exception:  # pylint: disable=broad-except
        except_handler_factory(config, qs=query_string.decode(config["charset"]))()


# adapted from cgitb.Hook
def except_handler_factory(
    config: SectionProxy, out: Callable[[str], int] = None, qs: str = None
) -> Callable[..., None]:
    """
    Log an exception gracefully.

    config is a config object; out is a function that takes a string; qs is a bytes query string.
    """
    if not out:
        out = sys.stdout.write
    error_template = "<p class='error'>%s</p>"

    def except_handler(
        etype: Type[BaseException] = None,
        evalue: BaseException = None,
        etb: TracebackType = None,
    ) -> None:
        """
        Log uncaught exceptions and display a friendly error.
        """
        if not etype or not evalue or not etb:
            etype, evalue, etb = sys.exc_info()

        out(cgitb.reset())
        if not config.get("exception_dir", ""):
            out(
                error_template
                % """
    A problem has occurred, but it probably isn't your fault.
    """
            )
        else:
            if qs:
                doc = f"<h3><code>{qs}</code></h3>"
            try:
                doc += cgitb.html((etype, evalue, etb), 5)
            except Exception:  # pylint: disable=broad-except
                doc += (
                    "<pre>"
                    + "".join(traceback.format_exception(etype, evalue, etb))
                    + "</pre>"
                )
            if config.getboolean("debug"):
                out(doc)
                return
            try:
                while etb.tb_next is not None:
                    etb = etb.tb_next
                e_file = etb.tb_frame.f_code.co_filename
                e_line = etb.tb_frame.f_lineno
                ldir = os.path.join(config["exception_dir"], os.path.split(e_file)[-1])
                if not os.path.exists(ldir):
                    os.umask(0o002)
                    os.makedirs(ldir)
                (fd, path) = tempfile.mkstemp(
                    prefix=f"{e_line}_", suffix=".html", dir=ldir
                )
                fh = os.fdopen(fd, "w")
                fh.write(doc)
                fh.close()
                os.chmod(path, stat.S_IROTH)
                out(
                    error_template
                    % """\
A problem has occurred, but it probably isn't your fault.
REDbot has remembered it, and we'll try to fix it soon."""
                )
            except Exception:  # pylint: disable=broad-except
                out(
                    error_template
                    % """\
A problem has occurred, but it probably isn't your fault.
REDbot tried to save it, but it couldn't! Oops."""
                )
                out("<h3>Original Error</h3>")
                out("<pre>")
                out("".join(traceback.format_exception(etype, evalue, etb)))
                out("</pre>")
                out("<h3>Write Error</h3>")
                out("<pre>")
                out("".join(traceback.format_exc()))
                out("</pre>")
        sys.exit(1)  # We're in an uncertain state, so we must die horribly.

    return except_handler


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
