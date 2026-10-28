#!/usr/bin/env python

"""
Parse links from a stream of HTML data.
"""

import codecs
from html.parser import HTMLParser
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlsplit

from httplint.charset import is_text_encoding, whatwg_encoding
from httplint.field.utils import split_params, unquote_string
from httplint.message import HttpMessageLinter

DEFAULT_ENCODING = "utf-8"
MAX_FEED_BYTES = 2 * 1024 * 1024
# A <base> inside these isn't the document's base (noscript: as when scripting is enabled).
INERT_TAGS = ("template", "svg", "math", "noscript")
# Byte order marks (UTF-8, UTF-16BE, UTF-16LE), which outrank a <meta>.
BOMS = (b"\xef\xbb\xbf", b"\xfe\xff", b"\xff\xfe")

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
        self.base_seen = False
        self.inert_depth = {tag: 0 for tag in INERT_TAGS}
        self.decode_as: Optional[str] = None
        # Whether the encoding is certain: the header gave one, the body starts with a BOM, or a
        # <meta> set it. None until known, as the headers can arrive after the parser is made.
        self._charset_fixed: Optional[bool] = None
        self._decoder: Optional[codecs.IncrementalDecoder] = None
        self._decoder_encoding = ""
        HTMLParser.__init__(self)

    def __getstate__(self) -> Dict[str, Any]:
        return {"errors": self.errors, "last_err_pos": self.last_err_pos, "ok": self.ok}

    def feed_bytes(self, bchunk: bytes) -> None:
        "Feed a given chunk of bytes to the parser"
        if self.ok:
            if self.bytes_fed == 0 and bchunk.startswith(BOMS):
                self._charset_fixed = True
            self.bytes_fed += len(bchunk)
            if self.bytes_fed > MAX_FEED_BYTES:
                self.ok = False
                return
            encoding = self.decode_as or self.message.character_encoding or DEFAULT_ENCODING
            self.feed(self._decode(bchunk, encoding))

    def _decode(self, bchunk: bytes, encoding: str) -> str:
        """
        Decode a chunk, holding over the start of a character that continues in the next one.
        A <meta> can change the encoding part way through, so the decoder follows it; bytes
        it was holding go to the new one.
        """
        if self._decoder is None or self._decoder_encoding != encoding:
            held = b""
            if self._decoder is not None:
                held = self._decoder.getstate()[0]
            self._decoder = new_decoder(encoding)
            self._decoder_encoding = encoding
            bchunk = held + bchunk
        try:
            return self._decoder.decode(bchunk)
        except UnicodeError:
            # e.g. utf-16 without a BOM; the page's label is no use, so treat it as the default
            self._decoder = new_decoder(DEFAULT_ENCODING)
            return self._decoder.decode(bchunk)

    def finish(self) -> None:
        "No more data is coming; process what the parser is holding back (e.g., a split tag)."
        if not self.ok or self._decoder is None:
            return
        try:
            self.feed(self._decoder.decode(b"", final=True))
        except UnicodeError:
            pass
        try:
            HTMLParser.close(self)
        except BadErrorIReallyMeanIt:
            pass
        except Exception as why:  # pylint: disable=broad-except
            if self.err:
                self.err(f"close problem: {why}")
            self.errors += 1

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
            attr_d = first_attrs(attrs)
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
            attr_d = first_attrs(attrs)
            inert = any(self.inert_depth.values())
            if "href" in attr_d and not self.base_seen and not inert:  # first <base href> counts
                self.base_seen = True
                self.message.base_uri = resolve_base(self.message.base_uri, attr_d["href"] or "")
        elif tag in self.inert_depth:
            self.inert_depth[tag] += 1
        elif tag == "meta":
            if self.message.headers.parsed.get("content-type", [None])[0] != "text/html":
                return  # XML documents don't take their encoding from a <meta>
            attr_d = first_attrs(attrs)
            if "charset" in attr_d and self._set_meta_charset(
                (attr_d["charset"] or "").strip(" \t\n\f\r")
            ):
                return  # otherwise, as in HTML, fall back to http-equiv
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

    def _set_meta_charset(self, label: Optional[str]) -> bool:
        """
        Apply a <meta> charset, unless the encoding is already certain (the first <meta> that
        sets it wins). A label that the Encoding Standard and Python both know is recorded on
        the message, as for the header. A Python-only text encoding (`latin-1`, `mac-roman`) is
        only used to decode later chunks, so the message never claims it. Anything else is
        ignored. Returns whether the label was one that could be used.
        """
        if self._charset_fixed is None:
            self._charset_fixed = self.message.whatwg_encoding is not None
        if not label:
            return False
        encoding = whatwg_encoding(label)
        if encoding in ("UTF-16LE", "UTF-16BE"):
            # The tag had to be readable as ASCII, so HTML takes these labels to mean UTF-8.
            label, encoding = "utf-8", "UTF-8"
        elif encoding == "x-user-defined":
            label, encoding = "windows-1252", "windows-1252"
        if not is_text_encoding(label) or encoding == "replacement":
            return False
        if encoding:
            if not self._charset_fixed:
                self.message.whatwg_encoding = encoding
                self.message.character_encoding = label
                self.decode_as = None
        elif codecs.lookup(label).name.replace("-", "_").startswith(NOT_META_CHARSETS):
            return False
        elif not self._charset_fixed:
            self.decode_as = label
        self._charset_fixed = True
        return True

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


def first_attrs(attrs: List[Tuple[str, Optional[str]]]) -> Dict[str, Optional[str]]:
    "A start tag's attributes as a dict; browsers use the first of a repeated one, not the last."
    attr_d: Dict[str, Optional[str]] = {}
    for name, value in attrs:
        attr_d.setdefault(name, value)
    return attr_d


def new_decoder(encoding: str) -> codecs.IncrementalDecoder:
    """
    An incremental decoder for a charset name supplied by a remote party, replacing bytes that
    aren't valid so that they can't quietly turn one URL into another. Falls back to UTF-8 if the
    name can't be used.
    """
    if is_text_encoding(encoding):
        try:
            return codecs.getincrementaldecoder(encoding)("replace")
        except LookupError:
            pass
    return codecs.getincrementaldecoder(DEFAULT_ENCODING)("replace")


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
