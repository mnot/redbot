import codecs
from functools import partial
import json
import os
from typing import Any, List, Match, Tuple, Union  # pylint: disable=unused-import
from urllib.parse import urljoin, quote as urlquote

from jinja2 import Environment, PackageLoader, select_autoescape, Markup, escape

import thor

from redbot import __version__
from redbot.formatter import Formatter, relative_time, f_num
from redbot.resource import HttpResource
from redbot.speak import Note, levels, categories  # pylint: disable=unused-import

nl = "\n"


def unicode_url_escape(url: str, safe: str) -> str:
    """
    URL escape a unicode string. Assume that anything already encoded
    is to be left alone.
    """
    # also include "~" because it doesn't need to be encoded,
    # but Python does anyway :/
    return urlquote(url, safe + r"%~")


uri_gen_delims = r":/?#[]@"
uri_sub_delims = r"!$&'()*+,;="
e_url = partial(unicode_url_escape, safe=uri_gen_delims + uri_sub_delims)
e_authority = partial(unicode_url_escape, safe=uri_sub_delims + r"[]:@")
e_path = partial(unicode_url_escape, safe=uri_sub_delims + r":@/")
e_path_seg = partial(unicode_url_escape, safe=uri_sub_delims + r":@")
e_query = partial(unicode_url_escape, safe=uri_sub_delims + r":@/?")
e_query_arg = partial(unicode_url_escape, safe=r"!$'()*+,:@/?")
e_fragment = partial(unicode_url_escape, safe=r"!$&'()*+,;:@=/?")


def e_js(instr: str) -> Markup:
    """
    Make sure instr is safe for writing into a double-quoted
    JavaScript string.
    """
    if not instr:
        return Markup("")
    instr = instr.replace("\\", "\\\\")
    instr = instr.replace('"', r"\"")
    instr = instr.replace("<", r"\x3c")
    return Markup(instr)


class BaseHtmlFormatter(Formatter):
    """
    Base class for HTML formatters."""

    media_type = "text/html"

    def __init__(self, *args: Any, **kw: Any) -> None:
        Formatter.__init__(self, *args, **kw)
        self.hidden_text = []  # type: List[Tuple[str, str]]
        self.templates = Environment(
            loader=PackageLoader("redbot.formatter"),
            trim_blocks=True,
            autoescape=select_autoescape(
                enabled_extensions=("html", "xml"), default_for_string=True,
            ),
        )
        self.templates.filters.update(
            {"f_num": f_num, "relative_time": relative_time, "req_qs": self.req_qs}
        )
        self.start = thor.time()

    def feed(self, chunk: bytes) -> None:
        pass

    def start_output(self) -> None:
        if self.resource:
            uri = self.resource.request.uri or ""
            req_headers = self.resource.request.headers
        else:
            uri = ""
            req_headers = []
        extra_title = " <span class='save'>"
        if self.kw.get("is_saved", None):
            extra_title += " saved "
        if self.resource and self.resource.check_name != "default":
            extra_title += f"{escape(self.resource.check_name)} response"
        extra_title += "</span>"
        extra_body_class = ""
        if self.kw.get("is_blank", None):
            extra_body_class = "blank"
        descend = ""
        if self.kw.get("descend", False):
            descend = "&descend=True"
        tpl = self.templates.get_template("response_start.html")
        self.output(
            tpl.render(
                static=self.config["static_root"],
                version=__version__,
                html_uri=uri,
                test_id=self.kw.get("test_id", ""),
                config=Markup(
                    json.dumps(
                        {
                            "redbot_uri": e_js(uri),
                            "redbot_req_hdrs": req_headers,
                            "redbot_version": __version__,
                        },
                        ensure_ascii=True,
                    ).replace("<", "\\u003c")
                ),
                extra_js=self.format_extra(".js"),
                extra_title=Markup(extra_title),
                extra_body_class=extra_body_class,
                descend=descend,
            )
        )

    def finish_output(self) -> None:
        """
        The bottom bits.
        """
        self.output(self.format_extra())
        tpl = self.templates.get_template("footer.html")
        self.output(tpl.render(baseuri=self.config["ui_uri"]))

    def error_output(self, message: str) -> None:
        """
        Something bad happened.
        """
        self.output(f"<p class='error'>{message}</p>")
        tpl = self.templates.get_template("footer.html")
        self.output(tpl.render(baseuri=self.config["ui_uri"]))

    def status(self, message: str) -> None:
        "Update the status bar of the browser"
        self.output(
            f"""
<script>
<!-- {thor.time() - self.start:3.3f}
qs('#red_status').textContent = "{escape(message)}"
-->
</script>
"""
        )

    def debug(self, message: str) -> None:
        "Debug to console."
        self.output(
            f"""
<script>
<!--
console.log("{thor.time() - self.start:3.3f} {e_js(message)}");
-->
</script>
"""
        )

    def final_status(self) -> None:
        #        See issue #51
        #        self.status("REDbot made %(reqs)s requests in %(elapse)2.3f seconds." % {
        #            'reqs': fetch.total_requests,
        self.status("")
        self.output(
            f"""
<div id="final_status">{thor.time() - self.start:2.2f} seconds</div>
"""
        )

    def format_extra(self, etype: str = ".html") -> Markup:
        """
        Show extra content from the extra_dir, if any. MUST be UTF-8.
        Type controls the extension included; currently supported:
          - '.html': shown only on start page, after input block
          - '.js': javascript block (with script tag surrounding)
            included on every page view.
        """
        o = []
        if self.config.get("extra_dir", "") and os.path.isdir(self.config["extra_dir"]):
            extra_files = [
                p
                for p in os.listdir(self.config["extra_dir"])
                if os.path.splitext(p)[1] == etype
            ]
            for extra_file in extra_files:
                extra_path = os.path.join(self.config["extra_dir"], extra_file)
                try:
                    o.append(
                        codecs.open(
                            extra_path,
                            mode="r",
                            encoding="utf-8",  # type: ignore
                            errors="replace",
                        ).read()
                    )
                except IOError as why:
                    o.append(f"<!-- error opening {extra_file}: {why} -->")
        return Markup(nl.join(o))

    def req_qs(
        self,
        link: str = None,
        check_name: str = None,
        res_format: str = None,
        use_stored: bool = True,
        referer: bool = True,
    ) -> Markup:
        """
        Format a query string to refer to another REDbot resource.

        "link" is the resource to test; it is evaluated relative to the current context
        If blank, it is the same resource.

        "check_name" is the request type to show; see active_check/__init__.py. If not specified,
        that of the current context will be used.

        "res_format" is the response format; see formatter/*.py. If not specified, HTML will be
        used.

        If "use_stored" is true, we'll refer to the test_id, rather than make a new request.

        If 'referer" is true, we'll strip any existing Referer and add our own.

        Request headers are copied over from the current context.
        """
        out = []
        uri = self.resource.request.uri
        if use_stored and self.kw.get("test_id", None):
            out.append("id=%s" % e_query_arg(self.kw["test_id"]))
        else:
            out.append("uri=%s" % e_query_arg(urljoin(uri, link or "")))
        if self.resource.request.headers:
            for k, v in self.resource.request.headers:
                if referer and k.lower() == "referer":
                    continue
                out.append(f"req_hdr={e_query_arg(k)}%3A{e_query_arg(v)}")
        if referer:
            out.append(f"req_hdr=Referer%3A{e_query_arg(uri)}")
        if check_name:
            out.append(f"check_name={e_query_arg(check_name)}")
        elif self.resource.check_name is not None:
            out.append(f"check_name={e_query_arg(self.resource.check_name)}")
        if res_format:
            out.append(f"format={e_query_arg(res_format)}")
        return escape("&".join(out))
