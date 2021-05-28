"""
A collection of notes that the REDbot can emit.

PLEASE NOTE: the summary field is automatically HTML escaped, so it can contain arbitrary text (as
long as it's unicode).

However, the longer text field IS NOT ESCAPED, and therefore all variables to be interpolated into
it need to be escaped to be safe for use in HTML.
"""

from binascii import b2a_hex
from enum import Enum
from typing import Any, Dict, Union

from jinja2 import Markup, escape
from markdown import markdown


class categories(Enum):
    "Note classifications."
    GENERAL = "General"
    SECURITY = "Security"
    CONNEG = "Content Negotiation"
    CACHING = "Caching"
    VALIDATION = "Validation"
    CONNECTION = "Connection"
    RANGE = "Partial Content"


class levels(Enum):
    "Note levels."
    GOOD = "good"
    WARN = "warning"
    BAD = "bad"
    INFO = "info"


class Note:
    """
    A note about an HTTP resource, representation, or other component
    related to the URI under test.
    """

    category = None  # type: categories
    level = None  # type: levels
    summary = ""
    text = ""

    def __init__(self, subject: str, vrs: Dict[str, Union[str, int]] = None) -> None:
        self.subject = subject
        self.vars = vrs or {}

    def __eq__(self, other: Any) -> bool:
        return bool(
            self.__class__ == other.__class__
            and self.vars == other.vars
            and self.subject == other.subject
        )

    def show_summary(self, lang: str) -> Markup:
        """
        Output a textual summary of the message as a Unicode string.

        Note that if it is displayed in an environment that needs
        encoding (e.g., HTML), that is *NOT* done.
        """
        return Markup(self.summary % self.vars)

    def show_text(self, lang: str) -> Markup:
        """
        Show the HTML text for the message as a Unicode string.

        The resulting string is already HTML-encoded.
        """
        return Markup(
            markdown(
                self.text % {k: escape(str(v)) for k, v in self.vars.items()},
                output_format="html",
            )
        )


def display_bytes(inbytes: bytes, encoding: str = "utf-8", truncate: int = 40) -> str:
    """
    Format arbitrary input bytes for display.

    Printable Unicode characters are displayed without modification;
    everything else is shown as escaped hex.
    """
    instr = inbytes.decode(encoding, "backslashreplace")
    out = []
    for char in instr[:truncate]:
        if not char.isprintable():
            char = r"\x%s" % b2a_hex(char.encode(encoding)).decode("ascii")
        out.append(char)
    return "".join(out)
