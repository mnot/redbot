#!/usr/bin/env python

"""
Parse links from a stream of HTML data.
"""

import codecs
from html.parser import HTMLParser
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlsplit

from httplint.field.utils import split_string, unquote_string
from httplint.message import HttpMessageLinter
from httplint.syntax import rfc9110

from redbot.utils import decode_text

DEFAULT_ENCODING = "utf-8"
MAX_FEED_BYTES = 2 * 1024 * 1024
# A <base> inside these isn't the document's base (noscript: as when scripting is enabled).
INERT_TAGS = ("template", "svg", "math", "noscript")


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
        self.base_seen = False
        self.inert_depth = {tag: 0 for tag in INERT_TAGS}
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
            encoding = self.message.character_encoding or DEFAULT_ENCODING
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
            attr_d = dict(attrs)
            inert = any(self.inert_depth.values())
            if "href" in attr_d and not self.base_seen and not inert:  # first <base href> counts
                self.base_seen = True
                self.message.base_uri = resolve_base(self.message.base_uri, attr_d["href"] or "")
        elif tag in self.inert_depth:
            self.inert_depth[tag] += 1
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
                for param in split_string(params, rfc9110.parameter, r"\s*;\s*"):
                    try:
                        attr, val = param.split("=", 1)
                        param_dict[attr.lower()] = unquote_string(val)
                    except ValueError:
                        param_dict[param.lower()] = None
                enc = param_dict.get("charset", self.message.character_encoding) or DEFAULT_ENCODING
                try:
                    codecs.lookup(enc)
                    self.message.character_encoding = enc
                except LookupError:
                    pass

    def handle_endtag(self, tag: str) -> None:
        if self.inert_depth.get(tag):
            self.inert_depth[tag] -= 1

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


def resolve_base(page_uri: str, href: str) -> str:
    """
    Resolve a <base href> against the page's URI. As in the HTML spec, an unparseable href or a
    data: or javascript: URI leaves the page URI as the base (Chromium uses about:blank instead).
    """
    try:
        base = urljoin(page_uri, href.strip(" \t\n\f\r"))
        if urlsplit(base).scheme.lower() in ("data", "javascript"):
            return page_uri
    except ValueError:
        return page_uri
    return base


class BadErrorIReallyMeanIt(Exception):
    """See http://bugs.python.org/issue8885 for why this is necessary."""
