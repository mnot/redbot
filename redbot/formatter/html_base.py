from functools import partial
import json
import os
import time
from typing import List, Tuple, Union, Optional
from urllib.parse import urljoin, urlencode, quote as urlquote

import httplint
from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup, escape
from typing_extensions import Unpack

import redbot
from redbot.formatter import Formatter, FormatterArgs, relative_time, f_num
from redbot.i18n import LazyProxy, _, ngettext
from redbot.webui.captcha import CAPTCHA_PROVIDERS

NL = "\n"


def unicode_url_escape(url: str, safe: str) -> str:
    """
    URL escape a unicode string. Assume that anything already encoded
    is to be left alone.
    """
    # also include "~" because it doesn't need to be encoded,
    # but Python does anyway :/
    return urlquote(url, safe + r"%~")


uri_gen_delims = r":/?#[]@"  # pylint: disable=invalid-name
uri_sub_delims = r"!$&'()*+,;="  # pylint: disable=invalid-name
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
    templates = Environment(
        loader=PackageLoader("redbot.formatter"),
        extensions=["jinja2.ext.i18n"],
        trim_blocks=True,
        autoescape=select_autoescape(
            enabled_extensions=("html", "xml"),
            default_for_string=True,
        ),
    )
    templates.install_gettext_callables(_, ngettext, newstyle=True)  # type: ignore[attr-defined]  # pylint: disable=no-member

    def __init__(self, *args: Unpack[FormatterArgs]) -> None:
        Formatter.__init__(self, *args)
        self.templates.filters.update(
            {
                "f_num": f_num,
                "relative_time": relative_time,
                "redbot_link": self.redbot_link,
            }
        )
        captcha_provider = self.config.get("captcha_provider", "")
        captcha_data = CAPTCHA_PROVIDERS.get(captcha_provider, {})
        self.template_vars = {
            "formatter": self,
            "redbot_version": redbot.__version__,
            "httplint_version": httplint.__version__,
            "baseuri": self.config.get("ui_uri", "https://redbot.org/"),
            "static": self.config.get("static_root", "static"),
            "captcha_provider": captcha_provider,
            "captcha_script_url": Markup(
                captcha_data.get("script_url", b"").decode("ascii")
            ),
            "nonce": self.kw["nonce"],
        }
        self.start = time.time()

    def feed(self, sample: bytes) -> None:
        pass

    def start_output(self) -> None:
        uri = self.resource.request.uri or ""
        req_headers = self.resource.request.headers.text
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
                dict(
                    self.template_vars,
                    **{
                        "html_uri": uri,
                        "test_id": self.kw.get("test_id", ""),
                        "config": Markup(
                            json.dumps(
                                {
                                    "redbot_uri": e_js(uri),
                                    "redbot_req_hdrs": req_headers,
                                    "redbot_version": redbot.__version__,
                                    "httplint_version": httplint.__version__,
                                    "captcha_provider": self.config.get(
                                        "captcha_provider", ""
                                    ),
                                    "captcha_sitekey": self.config.get(
                                        "captcha_sitekey", None
                                    ),
                                    "i18n": {
                                        "add_req_hdr": str(_("add a request header")),
                                        "view_notes": str(_("view notes")),
                                        "view_body": str(_("view body")),
                                        "sort_alpha": str(_("sort by alpha")),
                                        "wire_order": str(_("show wire order")),
                                        "header_warning": str(
                                            _(
                                                "Setting the %s request header can "
                                                "lead to unpredictable results."
                                            )
                                        ),
                                    },
                                },
                                ensure_ascii=True,
                            ).replace("<", "\\u003c")
                        ),
                        "extra_js": self.format_extra(".js"),
                        "extra_title": Markup(extra_title),
                        "extra_body_class": extra_body_class,
                        "descend": descend,
                    },
                )
            )
        )

    def finish_output(self) -> None:
        """
        The bottom bits.
        """
        self.output(self.format_extra())
        tpl = self.templates.get_template("footer.html")
        self.output(tpl.render(self.template_vars))

    def error_output(self, message: str) -> None:
        """
        Something bad happened.
        """
        self.output(f"<p class='error foo'>{message}</p>")
        tpl = self.templates.get_template("footer.html")
        self.output(tpl.render(self.template_vars))

    def status(self, status: str) -> None:
        "Update the status bar of the browser"
        self.output(
            f"""
<script nonce="{self.kw['nonce']}">
<!-- {time.time() - self.start:3.3f}
document.querySelector('#red_status').textContent = "{escape(status)}"
-->
</script>
"""
        )

    def debug(self, message: str) -> None:
        "Debug to console."
        self.output(
            f"""
<script nonce="{self.kw['nonce']}">
<!--
console.log("{time.time() - self.start:3.3f} {e_js(message)}");
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
<div id="final_status">{time.time() - self.start:2.2f} seconds</div>
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
        out = []
        extra_dir = self.config.get("extra_dir", None)
        if extra_dir and os.path.isdir(extra_dir):
            extra_files = [
                p for p in os.listdir(extra_dir) if os.path.splitext(p)[1] == etype
            ]
            for extra_file in extra_files:
                extra_path = os.path.join(extra_dir, extra_file)
                try:
                    with open(
                        extra_path,
                        mode="r",
                        encoding="utf-8",
                        errors="replace",
                    ) as fh:
                        out.append(fh.read())
                except IOError as why:
                    out.append(f"<!-- error opening {extra_file}: {why} -->")
        return Markup(NL.join(out))

    def redbot_link(
        self,
        link_value: Union[str, LazyProxy],
        link: Optional[str] = None,
        check_name: Optional[str] = None,
        res_format: Optional[str] = None,
        use_stored: bool = True,
        descend: bool = False,
        referer: bool = False,
        css_class: str = "",
        title: Union[str, LazyProxy] = "",
    ) -> Markup:
        """
        Format an HTML form to refer to another REDbot resource. If it can be, it will be linked
        with a GET; otherwise a POST form will be written.

        "link_value" is the link text.

        "link" is the resource to test; it is evaluated relative to the current context
        If blank, it is the same resource.

        "check_name" is the request type to show; see active_check/__init__.py. If not specified,
        that of the current context will be used.

        "res_format" is the response format; see formatter/*.py. If not specified, HTML will be
        used.

        If "use_stored" is true, we'll refer to the test_id, rather than make a new request.

        If 'referer" is true, we'll strip any existing Referer and add our own.

        "css_class" adds css classes; 'title' adds a title.

        Request headers are copied over from the current context.
        """
        uri = self.resource.request.uri
        if not uri:
            return Markup("-")
        args: List[Tuple[str, str]] = []
        if check_name:
            args.append(("check_name", check_name))
        elif self.resource.check_id is not None:
            args.append(("check_name", self.resource.check_id))
        if res_format:
            args.append(("format", res_format))
        if use_stored and self.kw.get("test_id", None):
            args.append(("id", self.kw["test_id"]))
            return Markup(
                f"<a href='?{urlencode(args, doseq=True)}'"
                f"class='{css_class}' title='{title}'>{link_value}</a>"
            )
        args.append(("uri", urljoin(uri, link or "")))
        for name, val in self.resource.request.headers.text:
            if referer and name.lower() == "referer":
                continue
            args.append(("req_hdr", f"{name}:{val}"))
        if referer:
            args.append(("req_hdr", f"Referer:{uri}"))
        if descend:
            args.append(("descend", "1"))
        argstring = "".join(
            f"""<input type='hidden' name='{arg[0]}' value='{str(arg[1]).replace("'", '"')}' />"""
            for arg in args
        )
        return Markup(
            f'<form class="link" action="" method="POST">'
            f'<input type="submit" value="{link_value}" class="post_link {css_class}"'
            f' title="{title}" />{argstring}</form>'
        )
