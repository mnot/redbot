#!/usr/bin/env python3

"""
The <meta http-equiv="content-type"> handling in the link parser.
"""

import time
import unittest
from configparser import ConfigParser
from typing import Dict, List, Optional, Tuple
from urllib.parse import unquote

import thor
import thor.http
from httplint.message import HttpMessageLinter

from redbot.resource import HttpResource
from redbot.resource.fetch import RedFetcher
from redbot.resource.link_parse import HTMLLinkParser

# label: (decode_as, character_encoding, whatwg_encoding)
Classes = Dict[str, Tuple[Optional[str], Optional[str], Optional[str]]]


def make_config() -> ConfigParser:
    conf = ConfigParser()
    conf.read_dict({"redbot": {"enable_local_access": "yes", "max_runtime": "20"}})
    return conf


def meta_tag(params: str) -> bytes:
    return f"<meta http-equiv='Content-Type' content='text/html; {params}'>".encode()


def new_message(content_type: str = "text/html") -> HttpMessageLinter:
    message = HttpMessageLinter()
    message.process_headers([(b"content-type", content_type.encode())])
    message.base_uri = "http://example.com/"
    return message


def parse_meta(params: str, message: Optional[HttpMessageLinter] = None) -> HTMLLinkParser:
    parser = HTMLLinkParser(message or new_message(), [])
    parser.feed_bytes(meta_tag(params))
    return parser


class TestMetaCharset(unittest.TestCase):
    def test_label_classes(self) -> None:
        # Standard labels set the message as a header would; Python-only text encodings only
        # decode; everything else is ignored.
        expected: Classes = {
            "latin1": (None, "latin1", "windows-1252"),
            "windows-1252": (None, "windows-1252", "windows-1252"),
            "gb2312": (None, "gb2312", "GBK"),
            "shift_jis": (None, "shift_jis", "Shift_JIS"),
            "latin-1": ("latin-1", None, None),
            "mac-roman": ("mac-roman", None, None),
            "euc_jp": ("euc_jp", None, None),
            "utf-7": (None, None, None),
            "utf-32": (None, None, None),
            "iso-2022-kr": (None, None, None),
            "hex": (None, None, None),
            "unicode_escape": (None, None, None),
            "rot13": (None, None, None),
            "unknown": (None, None, None),
        }
        for label, classes in expected.items():
            with self.subTest(label=label):
                parser = parse_meta(f"charset={label}")
                message = parser.message
                self.assertEqual(
                    (parser.decode_as, message.character_encoding, message.whatwg_encoding),
                    classes,
                )
                header = new_message(f"text/html; charset={label}")
                self.assertEqual(message.character_encoding, header.character_encoding)

    def test_later_meta_wins(self) -> None:
        parser = parse_meta("charset=latin-1")
        parser.feed_bytes(meta_tag("charset=utf-8"))
        self.assertEqual((parser.decode_as, parser.message.character_encoding), (None, "utf-8"))

    def test_unusable_keeps_header(self) -> None:
        message = new_message("text/html; charset=windows-1252")
        parser = parse_meta("charset=utf-7", message)
        self.assertEqual(
            (parser.decode_as, message.character_encoding, message.whatwg_encoding),
            (None, "windows-1252", "windows-1252"),
        )

    def test_quoted_among_other_params(self) -> None:
        parser = parse_meta('format=flowed; charset="latin1"; x=y')
        self.assertEqual(parser.message.character_encoding, "latin1")

    def test_no_charset_changes_nothing(self) -> None:
        for content_type in ["text/html", "text/html; charset=windows-1252"]:
            message = new_message(content_type)
            before = (message.character_encoding, message.whatwg_encoding)
            parser = parse_meta("format=flowed", message)
            parser.feed_bytes(meta_tag("charset"))
            self.assertEqual((message.character_encoding, message.whatwg_encoding), before)
            self.assertIsNone(parser.decode_as)


class TestMetaParams(unittest.TestCase):
    def test_pathological_params(self) -> None:
        # ~4 s each with split_string, except the last; a generous bound avoids flakiness
        for params in [
            "a" * 64000,
            "a=b" + "c" * 64000 + " x",
            'a="' + "b" * 64000,
            "x=" + "a;" * 32000,
        ]:
            with self.subTest(params=params[:12]):
                start = time.perf_counter()
                parse_meta(params)
                self.assertLess(time.perf_counter() - start, 1.0)


# label: (link text, codec of the page's bytes). A <meta> only affects later chunks, so the
# link is in the second one.
USABLE = {
    "latin-1": ("café", "latin-1"),
    "mac-roman": ("café", "mac-roman"),
    "euc_jp": ("日本", "euc_jp"),
}
# Not used to decode, so the (UTF-8) page is read as UTF-8, as when the header has the label.
UNUSABLE = {label: ("café", "utf-8") for label in ["utf-7", "hex", "unicode_escape", "bogus"]}


def serve_page(exchange: thor.http.HttpServerExchange) -> None:
    label = unquote(exchange.uri.decode("ascii")[1:])
    text, codec = {**USABLE, **UNUSABLE}[label]
    head = f"<meta http-equiv=content-type content='text/html; charset={label}'>".encode()
    exchange.response_start(b"200", b"OK", [(b"Content-Type", b"text/html")])
    exchange.response_body(head)

    def second_chunk() -> None:
        exchange.response_body(f'<a href="/{text}">x</a>'.encode(codec))
        exchange.response_done([])

    thor.schedule(0.2, second_chunk)


class TestMetaDecoding(unittest.TestCase):
    "Links in a page whose <meta> charset arrives in an earlier chunk, over a real connection."

    @staticmethod
    def links(label: str) -> List[str]:
        # A fresh server per page; fetching a second page from the same server stalled.
        saved_check_ip = RedFetcher.client.check_ip
        RedFetcher.client.check_ip = None
        server = thor.http.HttpServer(b"127.0.0.1", 0)
        server.on("exchange", serve_page)
        sock = server.tcp_server.sock
        assert sock is not None
        try:
            resource = HttpResource(make_config()["redbot"], descend=True)
            resource.set_request(f"http://127.0.0.1:{sock.getsockname()[1]}/{label}")
            resource.on("check_done", thor.stop)
            timeout = thor.schedule(20, thor.stop)
            resource.check()
            thor.run()
            timeout.delete()
        finally:
            server.shutdown()
            RedFetcher.client.check_ip = saved_check_ip
        return sorted(resource.links["a"]) if resource.check_done else ["timed out"]

    def test_links_decoded(self) -> None:
        for label, (text, _codec) in {**USABLE, **UNUSABLE}.items():
            with self.subTest(label=label):
                self.assertEqual(self.links(label), [f"/{text}"])


if __name__ == "__main__":
    unittest.main()
