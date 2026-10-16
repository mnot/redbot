"""
HAR Formatter for REDbot.
"""

import operator
import re
import textwrap
from html.parser import HTMLParser
from typing import List, Optional

import thor.http.error as httperr
from httplint import HttpResponseLinter
from httplint.note import Note, categories, levels
from typing_extensions import Unpack

from redbot.formatter import Formatter, FormatterArgs
from redbot.i18n import _
from redbot.resource import HttpResource

NL = "\n"

_CONTROL_RE = re.compile(r"[\x00-\x08\x0a-\x1f\x7f-\x9f]")
_CONTROL_NO_NL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def escape_controls(text: str, keep_newlines: bool = False) -> str:
    """
    Replace C0 and C1 control characters (and DEL) in server-controlled text with visible
    escapes like \\x1b, so they can't drive the user's terminal. Tab is left alone, as are
    newlines if keep_newlines is set.
    """
    regex = _CONTROL_NO_NL_RE if keep_newlines else _CONTROL_RE
    return regex.sub(lambda m: f"\\x{ord(m.group(0)):02x}", text)


class BaseTextFormatter(Formatter):
    """
    Base class for text formatters."""

    media_type = "text/plain"

    note_categories = list(categories)

    link_order = [
        ("link", _("Head Links")),
        ("script", _("Script Links")),
        ("frame", _("Frame Links")),
        ("iframe", _("IFrame Links")),
        ("img", _("Image Links")),
    ]

    error_template = _("Error: %s\n")

    def __init__(self, *args: Unpack[FormatterArgs]) -> None:
        Formatter.__init__(self, *args)
        self.verbose = False

    def start_output(self) -> None:
        pass

    def feed(self, sample: bytes) -> None:
        pass

    def status(self, status: str) -> None:
        pass

    def finish_output(self) -> None:
        "Fill in the template with RED's results."
        if self.resource.response.complete or self.resource.nonfinal_responses:
            if self.resource.nonfinal_responses:
                self.output(
                    NL.join([self.format_headers(r) for r in self.resource.nonfinal_responses])
                    + NL
                    + NL
                )
            if self.resource.response.complete:
                self.output(self.format_headers(self.resource.response) + NL + NL)
            elif isinstance(self.resource.fetch_error, httperr.HttpError):
                self.output(
                    self.error_template % self._format_fetch_error(self.resource.fetch_error)
                )

            self.output(self.format_recommendations(self.resource) + NL)
        else:
            if self.resource.fetch_error is None:
                pass
            elif isinstance(self.resource.fetch_error, httperr.HttpError):
                self.output(
                    self.error_template % self._format_fetch_error(self.resource.fetch_error)
                )
            else:
                raise AssertionError("Unknown incomplete response error.")

    @staticmethod
    def _format_fetch_error(error: httperr.HttpError) -> str:
        if error.detail:
            return f"{escape_controls(error.desc)} ({escape_controls(error.detail)})"
        return escape_controls(error.desc)

    def error_output(self, message: str) -> None:
        self.output(self.error_template % escape_controls(message))

    @staticmethod
    def format_headers(response: HttpResponseLinter) -> str:
        out = [
            escape_controls(
                f"HTTP/{response.version} {response.status_code_str} {response.status_phrase}"
            )
        ]
        return NL.join(out + [escape_controls(f"{h[0]}:{h[1]}") for h in response.headers.text])

    def format_recommendations(self, resource: HttpResource) -> str:
        return "".join(
            [self.format_recommendation(resource, category) for category in self.note_categories]
        )

    def format_recommendation(self, resource: HttpResource, category: categories) -> str:
        notes = [note for note in resource.response.notes if note.category == category]
        if not notes:
            return ""
        out = []
        if list(notes):
            out.append(f"* {category.value}:")
        for note in notes:
            out.append(f"  * {self.colorize(note.level, note.summary)}")
            if self.verbose:
                out.append("")
                out.extend("    " + line for line in self.format_text(note))
                out.append("")
            for subnote in note.subnotes:
                out.append(f"    * {self.colorize(subnote.level, subnote.summary)}")
                if self.verbose:
                    out.append("")
                    out.extend("      " + line for line in self.format_text(subnote))
                    out.append("")
        out.append(NL)
        return NL.join(out)

    @staticmethod
    def format_text(note: Note) -> List[str]:
        text = strip_tags(re.sub(r"(?m)\s\s+", " ", note.detail))
        return textwrap.wrap(escape_controls(text, keep_newlines=True))

    def colorize(self, level: Optional[levels], instr: str) -> str:
        instr = escape_controls(instr)
        if self.kw.get("tty_out", False):
            # info
            color_start = "\033[0;32m"
            color_end = "\033[0;39m"
            if level == levels.GOOD:
                color_start = "\033[1;32m"
                color_end = "\033[0;39m"
            if level == levels.BAD:
                color_start = "\033[1;31m"
                color_end = "\033[0;39m"
            if level == levels.WARN:
                color_start = "\033[1;33m"
                color_end = "\033[0;39m"
            else:
                color_start = "\033[1;34m"
                color_end = "\033[0;39m"
            return color_start + instr + color_end
        return instr


class TextFormatter(BaseTextFormatter):
    """
    Format a REDbot object as text.
    """

    name = "txt"
    media_type = "text/plain"

    def finish_output(self) -> None:
        BaseTextFormatter.finish_output(self)


class VerboseTextFormatter(TextFormatter):
    name = "txt_verbose"

    def __init__(self, *args: Unpack[FormatterArgs]) -> None:
        TextFormatter.__init__(self, *args)
        self.verbose = True


class TextListFormatter(BaseTextFormatter):
    """
    Format multiple REDbot responses as a textual list.
    """

    name = "text"
    media_type = "text/plain"
    can_multiple = True

    def __init__(self, *args: Unpack[FormatterArgs]) -> None:
        BaseTextFormatter.__init__(self, *args)

    def finish_output(self) -> None:
        "Fill in the template with RED's results."
        BaseTextFormatter.finish_output(self)
        sep = "=" * 78
        for hdr_tag, heading in self.link_order:
            subresources = [d[0] for d in self.resource.linked if d[1] == hdr_tag]
            self.output(f"{sep}{NL}{heading} ({len(subresources)}){NL}{sep}{NL}")
            if subresources:
                subresources.sort(key=operator.attrgetter("request.uri"))
                for subresource in subresources:
                    self.output(self.format_uri(subresource) + NL + NL)
                    self.output(self.format_headers(subresource.response) + NL + NL)
                    self.output(self.format_recommendations(subresource) + NL + NL)

    def format_uri(self, resource: HttpResource) -> str:
        return self.colorize(None, resource.request.uri or "")


class VerboseTextListFormatter(TextListFormatter):
    name = "txt_verbose"

    def __init__(self, *args: Unpack[FormatterArgs]) -> None:
        TextListFormatter.__init__(self, *args)
        self.verbose = True


class MLStripper(HTMLParser):
    def __init__(self) -> None:
        HTMLParser.__init__(self)
        self.reset()
        self.fed: List[str] = []

    def handle_data(self, data: str) -> None:
        self.fed.append(data)

    def get_data(self) -> str:
        return "".join(self.fed)

    def error(self, message: str) -> None:
        pass


def strip_tags(html: str) -> str:
    stripper = MLStripper()
    stripper.feed(html)
    return stripper.get_data()
