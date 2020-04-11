#!/usr/bin/env python

"""
HTML Formatter for REDbot.
"""

import operator
import re
import textwrap
from typing import Any, List, Match, Tuple, Union  # pylint: disable=unused-import
from urllib.parse import urljoin

from markdown import markdown

import thor.http.error as httperr

from redbot import __version__
from redbot.formatter import Formatter
from redbot.formatter.html_base import (
    BaseHtmlFormatter,
    e_query_arg,
    Markup,
    escape,
    nl,
)
from redbot.resource import HttpResource, active_check
from redbot.message.headers import HeaderProcessor
from redbot.speak import Note, levels, categories  # pylint: disable=unused-import


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
        categories.CONNEG: [active_check.ConnegCheck.check_name],
        categories.VALIDATION: [
            active_check.ETagValidate.check_name,
            active_check.LmValidate.check_name,
        ],
        categories.RANGE: [active_check.RangeRequest.check_name],
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
        "text/html": "http://validator.w3.org/check?uri=%s",
        "text/css": "http://jigsaw.w3.org/css-validator/validator?uri=%s&",
        "application/xhtml+xml": "http://validator.w3.org/check?uri=%s",
        "application/atom+xml": "http://feedvalidator.org/check.cgi?url=%s",
        "application/rss+xml": "http://feedvalidator.org/check.cgi?url=%s",
    }

    name = "html"

    def __init__(self, *args: Any, **kw: Any) -> None:
        BaseHtmlFormatter.__init__(self, *args, **kw)
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
        media_type = self.resource.response.parsed_headers.get("content-type", [""])[0]
        if self.resource.response.complete:
            validator_link = self.validators.get(media_type, None)
            if validator_link:
                validator_link = validator_link % e_query_arg(self.resource.request.uri)
            tpl = self.templates.get_template("response_finish.html")
            self.output(
                tpl.render(
                    formatter=self,
                    resource=self.resource,
                    body=self.format_body_sample(self.resource),
                    is_resource=isinstance(self.resource, HttpResource),
                    is_saved=self.kw.get("is_saved", False),
                    allow_save=self.kw.get("allow_save", False),
                    har_link=self.req_qs(res_format="har"),
                    self_link=self.req_qs(use_stored=False),
                    validator_link=validator_link,
                    baseuri=self.config["ui_uri"],
                )
            )
        else:
            http_error = self.resource.response.http_error
            if http_error is None:
                pass  # usually a global timeout...
            elif isinstance(http_error, httperr.HttpError):
                if http_error.detail:
                    self.error_output(f"{http_error.desc} ({http_error.detail})")
                else:
                    self.error_output(http_error.desc)
            else:
                raise AssertionError(
                    f"Unknown incomplete response error {self.resource.response.http_error}"
                )

    def format_body_sample(self, resource: HttpResource) -> Markup:
        """show the stored body sample"""
        if resource.response.status_code == "206":
            sample = resource.response.payload
        else:
            sample = resource.response.decoded_sample
        try:
            uni_sample = sample.decode(resource.response.character_encoding, "ignore")
        except (TypeError, LookupError):
            uni_sample = sample.decode("utf-8", "replace")
        safe_sample = escape(uni_sample)
        if hasattr(resource, "links"):
            for tag, link_set in list(resource.links.items()):
                for link in link_set:
                    try:
                        link = urljoin(resource.response.base_uri, link)
                    except ValueError:
                        continue  # we're not interested in raising these upstream

                    def link_to(matchobj: Match) -> str:
                        return r"%s<a href='?%s' class='nocode'>%s</a>%s" % (
                            matchobj.group(1),
                            self.req_qs(link, use_stored=False),
                            escape(link),
                            matchobj.group(1),
                        )

                    safe_sample = Markup(
                        re.sub(
                            r"('|&quot;)%s\1" % re.escape(link), link_to, safe_sample
                        )
                    )
        message = ""
        if not resource.response.decoded_sample_complete:
            message = "<p class='btw'>REDbot isn't showing the whole body, because it's so big!</p>"
        return Markup(f"<pre class='prettyprint'>{safe_sample}</pre>\n{{ message }}")

    def format_subrequest_messages(self, category: categories) -> Markup:
        out = []
        if isinstance(self.resource, HttpResource) and category in self.note_responses:
            for check_name in self.note_responses[category]:
                if not self.resource.subreqs[check_name].fetch_started:
                    continue
                out.append(
                    '<span class="req_link"> (<a href="?%s">%s response</a>'
                    % (self.req_qs(check_name=check_name), check_name)
                )
                smsgs = [
                    note
                    for note in getattr(self.resource.subreqs[check_name], "notes", [])
                    if note.level in [levels.BAD] and note not in self.resource.notes
                ]
                if len(smsgs) == 1:
                    out.append(f" - {len(smsgs)} problem\n")
                elif smsgs:
                    out.append(f" - {len(smsgs)} problems\n")
                out.append(")</span>")
        return Markup(nl.join(out))

    def format_header(self, header: Tuple[str, str]) -> Markup:
        return Markup(self.header_presenter.Show(header[0], header[1]))

    def format_header_description(self, header_name: str) -> Markup:
        description = HeaderProcessor.find_header_handler(header_name).description
        if description:
            return Markup(
                '<span class="tip">'
                + markdown(
                    description % {"field_name": header_name}, output_format="html5"
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

    def __init__(self, formatter: Formatter) -> None:
        self.formatter = formatter

    def Show(self, name: str, value: str) -> Markup:
        """
        Return the given header name/value pair after
        presentation processing.
        """
        name = name.lower()
        name_token = name.replace("-", "_")
        if name_token[0] != "_" and hasattr(self, name_token):
            return getattr(self, name_token)(name, value)
        return Markup(self.I(escape(value), len(name)))

    def BARE_URI(self, name: str, value: str) -> str:
        "Present a bare URI header value"
        value = value.rstrip()
        svalue = value.lstrip()
        space = len(value) - len(svalue)
        return '%s<a href="?%s">%s</a>' % (
            " " * space,
            self.formatter.req_qs(svalue, use_stored=False),
            self.I(escape(svalue), len(name)),
        )

    content_location = location = x_xrds_location = BARE_URI

    @staticmethod
    def I(value: str, sub_width: int) -> str:
        "wrap a line to fit in the header box"
        hdr_sz = 75
        sw = hdr_sz - min(hdr_sz - 1, sub_width)
        tr = textwrap.TextWrapper(
            width=sw, subsequent_indent=" " * 8, break_long_words=True
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
        self.problems = []  # type: List[Note]
        self.templates.filters.update(
            {
                "index_problem": self.index_problem,
                "note_description": self.format_note_description,
            }
        )

    def finish_output(self) -> None:
        self.final_status()
        tpl = self.templates.get_template("response_multi_finish.html")
        self.output(
            tpl.render(
                formatter=self,
                droid_lists=self.make_droid_lists(self.resource),
                problems=self.problems,
                levels=levels,
                is_saved=self.kw.get("is_saved", False),
                allow_save=self.kw.get("allow_save", False),
                har_link=self.req_qs(res_format="har"),
                self_link=self.req_qs(use_stored=False),
                baseuri=self.config["ui_uri"],
            )
        )

    def make_droid_lists(
        self, resource: HttpResource
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
        description = HeaderProcessor.find_header_handler(header_name).description
        if description:
            return Markup(
                markdown(
                    description % {"field_name": header_name}, output_format="html5"
                )
            )
        return Markup("")
