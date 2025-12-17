"""
HTML Formatter for REDbot.
"""

import operator
import re
import textwrap
from typing import Any, List, Match, Tuple, Union
from urllib.parse import urljoin

from typing_extensions import Unpack
from httplint import get_field_description
from httplint.note import Note, levels, categories
import thor
import thor.http.error as httperr

from redbot import __version__
from redbot.formatter import FormatterArgs
from redbot.formatter.html_base import (
    BaseHtmlFormatter,
    e_query_arg,
    Markup,
    escape,
    NL,
)
from redbot.resource import HttpResource, active_check
from redbot.i18n import _, LazyProxy, ngettext


class SingleEntryHtmlFormatter(BaseHtmlFormatter):
    """
    Present a single REDbot response in detail.
    """

    # the order of note categories to display
    note_categories = [
        categories.GENERAL,
        categories.SECURITY,
        categories.CONNECTION,
        categories.CONNEG,
        categories.CACHING,
        categories.VALIDATION,
        categories.RANGE,
    ]

    # associating categories with subrequests
    note_responses = {
        categories.CONNEG: [active_check.ConnegCheck.check_id],
        categories.VALIDATION: [
            active_check.ETagValidate.check_id,
            active_check.LmValidate.check_id,
        ],
        categories.RANGE: [active_check.RangeRequest.check_id],
    }

    # Media types that browsers can view natively
    viewable_types = [
        "text/plain",
        "text/html",
        "application/xhtml+xml",
        "application/pdf",
        "image/gif",
        "image/jpeg",
        "image/jpg",
        "image/png",
        "application/javascript",
        "application/x-javascript",
        "text/javascript",
        "text/x-javascript",
        "text/css",
    ]

    # Validator uris, by media type
    validators = {
        "text/html": "https://validator.w3.org/check?uri=%s",
        "text/css": "https://jigsaw.w3.org/css-validator/validator?uri=%s&",
        "application/xhtml+xml": "https://validator.w3.org/check?uri=%s",
        "application/atom+xml": "https://validator.w3.org/feed/check.cgi?url=%s",
        "application/rss+xml": "https://validator.w3.org/feed/check.cgi?url=%s",
    }

    name = "html"

    def __init__(self, *args: Unpack[FormatterArgs]) -> None:
        BaseHtmlFormatter.__init__(self, *args)
        self.templates.filters.update(
            {
                "header_present": self.format_header,
                "header_description": self.format_header_description,
                "subrequest_messages": self.format_subrequest_messages,
            }
        )
        self.header_presenter = HeaderPresenter(self)

    def finish_output(self) -> None:
        self.final_status()
        media_type = self.resource.response.headers.parsed.get("content-type", [""])[0]
        if self.resource.response.complete or self.resource.nonfinal_responses:
            validator_link = self.validators.get(media_type, None)
            if validator_link and self.resource.response.complete:
                validator_link = validator_link % e_query_arg(
                    self.resource.request.uri or ""
                )
            else:
                validator_link = None
            is_saved = self.kw.get("is_saved", False)
            save_mtime = self.kw.get("save_mtime", None)
            allow_save = self.kw.get("allow_save", False)
            if is_saved and save_mtime and (float(save_mtime) - thor.time() < 3600):
                is_saved = False
                allow_save = True

            tpl = self.templates.get_template("response_finish.html")
            self.output(
                tpl.render(
                    dict(
                        self.template_vars,
                        **{
                            "resource": self.resource,
                            "body": self.format_body_sample(self.resource),
                            "is_resource": isinstance(self.resource, HttpResource),
                            "is_saved": is_saved,
                            "save_mtime": save_mtime,
                            "allow_save": allow_save,
                            "har_link": self.redbot_link(
                                _("view HAR"),
                                res_format="har",
                                title=_(
                                    "View a HAR (HTTP ARchive, a JSON format) file for this test"
                                ),
                            ),
                            "descend_link": self.redbot_link(
                                _("check embedded"),
                                use_stored=False,
                                descend=True,
                                referer=True,
                                title=_(
                                    "Run REDbot on images, frames and embedded links"
                                ),
                            ),
                            "validator_link": validator_link,
                        },
                    )
                )
            )
        else:
            http_error = self.resource.fetch_error
            if http_error is None:
                pass  # usually a global timeout...
            elif isinstance(http_error, httperr.HttpError):
                if http_error.detail:
                    self.error_output(f"{http_error.desc} ({http_error.detail})")
                else:
                    self.error_output(http_error.desc)
            else:
                raise AssertionError(
                    f"Unknown incomplete response error {self.resource.fetch_error}"
                )

    def format_body_sample(self, resource: HttpResource) -> Markup:
        """show the stored body sample"""
        sample = b"".join(resource.response_decoded_sample)
        try:
            uni_sample = sample.decode(
                resource.response.character_encoding or "utf-8", "ignore"
            )
        except (TypeError, LookupError):
            uni_sample = sample.decode("utf-8", "replace")
        safe_sample = escape(uni_sample)
        if self.config.getboolean("content_links", False):
            for __, link_set in list(resource.links.items()):
                for link in link_set:
                    if len(link) > 8000:  # avoid processing inline assets through regex
                        continue
                    try:
                        abs_link = urljoin(resource.response.base_uri, link)
                    except ValueError:
                        continue  # we're not interested in raising these upstream

                    link_str = self.redbot_link(
                        escape(link),
                        abs_link,
                        use_stored=False,
                        css_class="nocode",
                        referer=True,
                    )

                    def link_to(matchobj: Match) -> str:
                        return rf"{matchobj.group(1)}{link_str}{matchobj.group(1)}"  # pylint: disable=cell-var-from-loop

                    safe_sample = Markup(
                        re.sub(
                            rf"(&#34;|&#39;){re.escape(link)}\1", link_to, safe_sample
                        )
                    )
        message: Union[str, LazyProxy] = ""
        if not resource.response_decoded_complete:
            message = _(
                "<p class='btw'>REDbot isn't showing all content, because it's so big!</p>"
            )
        return Markup(f"<pre class='prettyprint'>{safe_sample}</pre>\n{message}")

    def format_subrequest_messages(self, category: categories) -> Markup:
        out = []
        if isinstance(self.resource, HttpResource) and category in self.note_responses:
            for check_id in self.note_responses[category]:
                if not self.resource.subreqs[check_id].fetch_started:
                    continue
                check_name = self.resource.subreqs[check_id].check_name
                out.append(
                    f'<span class="req_link">'
                    f'({self.redbot_link(_("%s response") % check_name, check_name=check_id)}'
                )
                smsgs = [
                    note
                    for note in getattr(
                        self.resource.subreqs[check_id].response, "notes", []
                    )
                    if note.level in [levels.BAD]
                    and note not in self.resource.response.notes
                ]
                if smsgs:
                    out.append(
                        ngettext(" - %d problem\n", " - %d problems\n", len(smsgs))
                        % len(smsgs)
                    )
                out.append(")</span>")
        return Markup(NL.join(out))

    def format_header(self, header: Tuple[str, str]) -> Markup:
        return Markup(self.header_presenter.show(header[0], header[1]))

    def format_header_description(self, header_name: str) -> Markup:
        description = get_field_description(header_name)
        if description:
            return Markup(
                '<span class="tip">'
                + self._markdown.reset().convert(
                    description % {"field_name": header_name}
                )
                + "</span>"
            )
        return Markup("")


class HeaderPresenter:
    """
    Present a HTTP header in the Web UI. By default, it will:
        - Escape HTML sequences to avoid XSS attacks
        - Wrap long lines
    However if a method is present that corresponds to the header's
    field-name, that method will be run instead to represent the value.
    """

    def __init__(self, formatter: BaseHtmlFormatter) -> None:
        self.formatter = formatter

    def show(self, name: str, value: str) -> Markup:
        """
        Return the given header name/value pair after
        presentation processing.
        """
        name = name.lower()
        name_token = name.replace("-", "_")
        if name_token[0] != "_" and name_token != "show" and hasattr(self, name_token):
            content: Markup = getattr(self, name_token)(name, value)
            return content
        return escape(self._wrap(value, len(name)))

    def bare_uri(self, name: str, value: str) -> str:
        "Present a bare URI header value"
        value = value.rstrip()
        svalue = value.lstrip()
        space = len(value) - len(svalue)
        link = self.formatter.redbot_link(
            self._wrap(escape(svalue), len(name), 0),
            svalue,
            use_stored=False,
            referer=True,
        )
        return Markup(f"{' ' * space}{link}")

    content_location = location = x_xrds_location = bare_uri

    @staticmethod
    def _wrap(value: str, sub_width: int, indent_amount: int = 8) -> str:
        "wrap a line to fit in the header box"
        hdr_sz = 75
        sw = hdr_sz - min(hdr_sz - 1, sub_width)
        tr = textwrap.TextWrapper(
            width=sw, subsequent_indent=" " * indent_amount, break_long_words=True
        )
        return tr.fill(value)


class TableHtmlFormatter(BaseHtmlFormatter):
    """
    Present a summary of multiple HttpResources.
    """

    can_multiple = True
    name = "html"

    def __init__(self, *args: Any, **kw: Any) -> None:
        BaseHtmlFormatter.__init__(self, *args, **kw)
        self.problems: List[Note] = []
        self.templates.filters.update(
            {
                "index_problem": self.index_problem,
                "note_description": self.format_note_description,
            }
        )

    def finish_output(self) -> None:
        self.final_status()
        is_saved = self.kw.get("is_saved", False)
        save_mtime = self.kw.get("save_mtime", None)
        allow_save = self.kw.get("allow_save", False)
        if is_saved and save_mtime and (float(save_mtime) - thor.time() < 3600):
            is_saved = False
            allow_save = True

        tpl = self.templates.get_template("response_multi_finish.html")
        self.output(
            tpl.render(
                dict(
                    self.template_vars,
                    **{
                        "droid_lists": self.make_droid_lists(self.resource),
                        "problems": self.problems,
                        "levels": levels,
                        "is_saved": is_saved,
                        "save_mtime": save_mtime,
                        "allow_save": allow_save,
                        "har_link": self.redbot_link(
                            "view har",
                            res_format="har",
                            title="View a HAR (HTTP ARchive, a JSON format) file for this test",
                        ),
                    },
                )
            )
        )

    @staticmethod
    def make_droid_lists(
        resource: HttpResource,
    ) -> List[Tuple[str, List[HttpResource]]]:
        link_order = [
            ("link", "Head Links"),
            ("script", "Script Links"),
            ("frame", "Frame Links"),
            ("iframe", "IFrame Links"),
            ("img", "Image Links"),
        ]
        droid_lists = [("", [resource])]
        for hdr_tag, heading in link_order:
            droids = [d[0] for d in resource.linked if d[1] == hdr_tag]
            if droids:
                droids.sort(key=operator.attrgetter("response.base_uri"))
                droid_lists.append((heading, droids))
        return droid_lists

    def index_problem(self, problem: Note) -> int:
        if not problem in self.problems:
            self.problems.append(problem)
        return self.problems.index(problem) + 1

    def format_note_description(self, header_name: str) -> Markup:
        description = get_field_description(header_name)
        if description:
            return Markup(
                self._markdown.reset().convert(
                    description % {"field_name": header_name}
                )
            )
        return Markup("")
