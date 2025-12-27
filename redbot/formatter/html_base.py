from functools import partial
import json
import os
import time
from typing import TYPE_CHECKING
from urllib.parse import quote as urlquote, urljoin

import httplint
from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup, escape
from typing_extensions import Unpack

import redbot
from redbot.formatter import Formatter, FormatterArgs, relative_time, f_num
from redbot.formatter.null_links import NullLinkGenerator
from redbot.i18n import _, ngettext
from redbot.type import LinkGenerator
from redbot.webui.captcha import CAPTCHA_PROVIDERS

if TYPE_CHECKING:
    from redbot.webui.handlers.base import RequestHandler

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
            }
        )
        captcha_provider = self.config.get("captcha_provider", "")
        captcha_data = CAPTCHA_PROVIDERS.get(captcha_provider, {})
        self.links: LinkGenerator = self.kw.get("link_generator") or NullLinkGenerator()
        self.template_vars = {
            "formatter": self,
            "links": self.links,
            "redbot_version": redbot.__version__,
            "httplint_version": httplint.__version__,
            "baseuri": self.config.get("ui_uri", "https://redbot.org/"),
            "static": urljoin(
                self.config.get("ui_uri", "/"),
                self.config.get("static_root", "static"),
            ),
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
        elif self.kw.get("check_name"):
            extra_title += f"{escape(self.kw['check_name'])} response"
        extra_title += "</span>"
        extra_body_class = ""
        if self.kw.get("is_blank", None):
            extra_body_class = "blank"

        tpl = self.templates.get_template("response_start.html")
        self.output(
            tpl.render(
                dict(
                    self.template_vars,
                    **{
                        "html_uri": uri,
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
                                        "view_body": str(_("view content")),
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
                        "descend": self.kw.get("descend", False),
                        "test_id": self.kw.get("test_id", ""),
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
