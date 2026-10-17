#!/usr/bin/env python

"""
Parse links from a stream of HTML data.
"""

import codecs
from html.parser import HTMLParser
from typing import Any, Callable, Dict, List, Optional, Tuple

from httplint.charset import is_text_encoding, whatwg_encoding
from httplint.field.utils import split_params, unquote_string
from httplint.message import HttpMessageLinter

from redbot.utils import decode_text

DEFAULT_ENCODING = "utf-8"
MAX_FEED_BYTES = 2 * 1024 * 1024

# Python codecs that decode bytes to text but that a <meta> must not select: UTF-7 and
# UTF-16/32 (HTML treats a UTF-16 <meta> as UTF-8), and ones that aren't character encodings.
NOT_META_CHARSETS = (
    "utf_7",
    "utf_16",
    "utf_32",
    "unicode_escape",
    "raw_unicode_escape",
    "idna",
    "punycode",
)


class HTMLLinkParser(HTMLParser):
    """
    Parse the links out of an HTML document in a very forgiving way.

    feed() accepts a HttpMessageLinter object and a chunk of the document at a
    time.

    When links are found, link_procs will be called for each with the
    following arguments;
        - base (base URI for the link, in a unicode string)
        - link (URI as it appeared in document, in a unicode string)
        - tag (name of the element that contained it)
        - title (title attribute as a unicode string, if any)
    """

    link_parseable_types = [
        "text/html",
        "application/xhtml+xml",
        "application/atom+xml",
    ]

    link_types: Dict[str, Tuple[str, Optional[List[str]]]] = {
        "link": ("href", ["stylesheet"]),
        "a": ("href", None),
        "img": ("src", None),
        "script": ("src", None),
        "frame": ("src", None),
        "iframe": ("src", None),
    }

    def __init__(
        self,
        message: HttpMessageLinter,
        link_procs: List[Callable[[str, str, str, str], None]],
        err: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.message = message
        self.link_procs = link_procs
        self.err = err
        self.errors = 0
        self.last_err_pos: int = 0
        self.ok = True
        self.bytes_fed = 0
        self.decode_as: Optional[str] = None
        HTMLParser.__init__(self)

    def __getstate__(self) -> Dict[str, Any]:
        return {"errors": self.errors, "last_err_pos": self.last_err_pos, "ok": self.ok}

    def feed_bytes(self, bchunk: bytes) -> None:
        "Feed a given chunk of bytes to the parser"
        if self.ok:
            self.bytes_fed += len(bchunk)
            if self.bytes_fed > MAX_FEED_BYTES:
                self.ok = False
                return
            encoding = self.decode_as or self.message.character_encoding or DEFAULT_ENCODING
            decoded = decode_text(bchunk, encoding, "ignore")
            self.feed(decoded)

    def feed(self, data: str) -> None:
        "Feed a given chunk of str to the parser"
        if not self.ok:
            return
        if self.message.headers.parsed.get("content-type", [None])[0] in self.link_parseable_types:
            try:
                HTMLParser.feed(self, data)
            except BadErrorIReallyMeanIt:
                pass
            except Exception as why:  # pylint: disable=broad-except
                if self.err:
                    self.err(f"feed problem: {why}")
                self.errors += 1
        else:
            self.ok = False

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag in self.link_types:
            attr_d = dict(attrs)
            url_attr, rels = self.link_types[tag]
            if not rels or attr_d.get("rel", None) in rels:
                target = attr_d.get(url_attr, "")
                if target:
                    if "#" in target:
                        target = target[: target.index("#")]
                    title = (attr_d.get("title", "") or "").strip()
                    for proc in self.link_procs:
                        proc(self.message.base_uri, target, tag, title)
        elif tag == "base":
            self.message.base_uri = dict(attrs).get("href", self.message.base_uri) or ""
        elif tag == "meta":
            attr_d = dict(attrs)
            if (attr_d.get("http-equiv", "") or "").lower() != "content-type":
                return
            ct = attr_d.get("content", None)
            if ct:
                try:
                    media_type, params = ct.split(";", 1)
                except ValueError:
                    media_type, params = ct, ""
                media_type = media_type.lower()
                param_dict: Dict[str, Optional[str]] = {}
                for param in split_params(params):
                    try:
                        attr, val = param.split("=", 1)
                        param_dict[attr.lower()] = unquote_string(val)
                    except ValueError:
                        param_dict[param.lower()] = None
                self._set_meta_charset(param_dict.get("charset"))

    def _set_meta_charset(self, label: Optional[str]) -> None:
        """
        Apply a <meta> charset. A label that the Encoding Standard and Python both know is
        recorded on the message, as for the header. A Python-only text encoding (`latin-1`,
        `mac-roman`) is only used to decode later chunks, so the message never claims it.
        Anything else is ignored.
        """
        if not label or not is_text_encoding(label):
            return
        encoding = whatwg_encoding(label)
        if encoding == "replacement":
            return
        if encoding:
            self.message.whatwg_encoding = encoding
            self.message.character_encoding = label
            self.decode_as = None
        elif not codecs.lookup(label).name.replace("-", "_").startswith(NOT_META_CHARSETS):
            self.decode_as = label

    def error(self, message: str) -> None:
        self.errors += 1
        if self.getpos()[0] == self.last_err_pos:
            # we're in a loop; give up.
            if self.err:
                self.err(f"giving up on link parsing after {self.errors} errors")
            self.ok = False
            raise BadErrorIReallyMeanIt()
        self.last_err_pos, _ = self.getpos()
        if self.err:
            self.err(message)


class BadErrorIReallyMeanIt(Exception):
    """See http://bugs.python.org/issue8885 for why this is necessary."""
