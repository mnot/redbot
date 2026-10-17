#!/usr/bin/env python3

"""
The <meta http-equiv="content-type"> handling in the link parser.
"""

import time
import unittest
from typing import List, Optional, Tuple

from httplint.message import HttpMessageLinter

from redbot.resource.link_parse import HTMLLinkParser

Charset = Tuple[Optional[str], Optional[str]]


def meta_tag(params: str) -> bytes:
    return f"<meta http-equiv='Content-Type' content='text/html; {params}'>".encode()


def new_message(content_type: str = "text/html") -> HttpMessageLinter:
    message = HttpMessageLinter()
    message.process_headers([(b"content-type", content_type.encode())])
    message.base_uri = "http://example.com/"
    return message


def charset_from_header(label: str) -> Charset:
    message = new_message(f"text/html; charset={label}")
    return message.character_encoding, message.whatwg_encoding


def charset_from_meta(label: str) -> Charset:
    message = new_message()
    HTMLLinkParser(message, []).feed_bytes(meta_tag(f"charset={label}"))
    return message.character_encoding, message.whatwg_encoding


def links_after_meta(label: str, content_type: str = "text/html") -> List[str]:
    "Links from a non-ASCII (ISO-8859-1) body that follows a meta tag naming `label`."
    links: List[str] = []
    parser = HTMLLinkParser(
        new_message(content_type), [lambda base, link, tag, title: links.append(link)]
    )
    parser.feed_bytes(meta_tag(f"charset={label}"))
    parser.feed_bytes('<a href="/caf\xe9">x</a>'.encode("latin-1"))
    return links


class TestMetaCharset(unittest.TestCase):
    def test_same_as_header(self) -> None:
        labels = [
            # Encoding Standard labels
            "utf-8", "UTF-8", "utf8", "latin1", "iso-8859-1", "windows-1252", "cp1252",
            "gb2312", "shift_jis", "macintosh", "ISO-8859-2", "iso-2022-kr",
            # Python names that aren't labels, and unknown ones
            "latin-1", "utf-7", "utf_8", "mac-roman", "unicode_escape", "hex", "no-such-charset",
        ]  # fmt: skip
        for label in labels:
            with self.subTest(label=label):
                meta = charset_from_meta(label)
                header = charset_from_header(label)
                self.assertEqual(meta[0], header[0])
                if meta[0]:
                    self.assertEqual(meta[1], header[1])

    def test_known_labels(self) -> None:
        self.assertEqual(charset_from_meta("latin1"), ("latin1", "windows-1252"))
        self.assertEqual(charset_from_meta("gb2312"), ("gb2312", "GBK"))
        self.assertEqual(charset_from_meta("UTF-8"), ("UTF-8", "UTF-8"))

    def test_unknown_labels(self) -> None:
        for label in ["latin-1", "utf-7", "utf_8", "mac-roman", "hex", "bogus", "iso-2022-kr"]:
            with self.subTest(label=label):
                self.assertEqual(charset_from_meta(label), (None, None))

    def test_unknown_label_keeps_header(self) -> None:
        message = new_message("text/html; charset=windows-1252")
        HTMLLinkParser(message, []).feed_bytes(meta_tag("charset=utf-7"))
        self.assertEqual(message.character_encoding, "windows-1252")
        self.assertEqual(message.whatwg_encoding, "windows-1252")

    def test_quoted_among_other_params(self) -> None:
        message = new_message()
        HTMLLinkParser(message, []).feed_bytes(meta_tag('format=flowed; charset="latin1"; x=y'))
        self.assertEqual(message.character_encoding, "latin1")

    def test_no_charset_changes_nothing(self) -> None:
        for content_type in ["text/html", "text/html; charset=windows-1252"]:
            message = new_message(content_type)
            before = (message.character_encoding, message.whatwg_encoding)
            parser = HTMLLinkParser(message, [])
            parser.feed_bytes(meta_tag("format=flowed"))
            parser.feed_bytes(meta_tag("charset"))
            self.assertEqual((message.character_encoding, message.whatwg_encoding), before)

    def test_body_decoded_with_label(self) -> None:
        for label in ["latin1", "windows-1252"]:
            with self.subTest(label=label):
                self.assertEqual(links_after_meta(label), ["/caf\xe9"])

    def test_unknown_label_decodes_utf8(self) -> None:
        # the invalid byte is dropped, as when the header has the label
        for label in ["latin-1", "utf-7", "mac-roman", "no-such-charset"]:
            with self.subTest(label=label):
                self.assertEqual(links_after_meta(label), ["/caf"])
                self.assertEqual(links_after_meta(label, f"text/html; charset={label}"), ["/caf"])


class TestMetaParams(unittest.TestCase):
    def test_pathological_params(self) -> None:
        # ~4 s each with split_string; a generous bound keeps this from being flaky
        for params in ["a" * 64000, "a=b" + "c" * 64000 + " x", "x=" + "a;" * 32000]:
            with self.subTest(params=params[:12]):
                parser = HTMLLinkParser(new_message(), [])
                start = time.perf_counter()
                parser.feed_bytes(meta_tag(params))
                self.assertLess(time.perf_counter() - start, 1.0)


if __name__ == "__main__":
    unittest.main()
