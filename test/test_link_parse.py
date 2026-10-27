#!/usr/bin/env python3

import gzip
import unittest
from configparser import ConfigParser
from redbot.resource import HttpResource
from redbot.resource.link_parse import HTMLLinkParser
from httplint.message import HttpMessageLinter


class TestRepeatedAttributes(unittest.TestCase):
    "A browser uses the first of a repeated attribute."

    @staticmethod
    def parse(html: str) -> tuple:
        links = []

        def capture_link(base: str, link: str, tag: str, title: str) -> None:
            links.append((tag, link, title))

        message = HttpMessageLinter()
        message.headers.parsed.update({"content-type": ["text/html"]})
        message.base_uri = "http://example.com/"
        parser = HTMLLinkParser(message, [capture_link])
        parser.feed(html)
        return links, message

    def test_first_url_attribute_wins(self) -> None:
        for html, expected in [
            ('<script src="/a.js" src="/b.js">', ("script", "/a.js", "")),
            ('<a href="/a" href="/b">', ("a", "/a", "")),
            ('<img src="/a.png" src="/b.png">', ("img", "/a.png", "")),
            ('<a href="/a" title="one" title="two">', ("a", "/a", "one")),
            ('<link rel="stylesheet" rel="x" href="/a.css" href="/b.css">', ("link", "/a.css", "")),
        ]:
            with self.subTest(html=html):
                links, _ = self.parse(html)
                self.assertEqual(links, [expected])

    def test_first_rel_wins(self) -> None:
        links, _ = self.parse('<link rel="icon" rel="stylesheet" href="/a.css">')
        self.assertEqual(links, [])

    def test_first_base_href_wins(self) -> None:
        _, message = self.parse('<base href="/a/" href="/b/">')
        self.assertEqual(message.base_uri, "http://example.com/a/")

    def test_first_meta_attribute_wins(self) -> None:
        _, message = self.parse(
            '<meta http-equiv="content-type" content="text/html; charset=latin1" '
            'content="text/html; charset=utf-8">'
        )
        self.assertEqual(message.character_encoding, "latin1")


class TestLinkParse(unittest.TestCase):
    def test_link_parsing(self):
        links = []

        def capture_link(base: str, link: str, tag: str, title: str) -> None:
            links.append((tag, link))

        message = HttpMessageLinter()
        message.headers.parsed.update({"content-type": ["text/html"]})
        message.base_uri = "http://example.com/"

        parser = HTMLLinkParser(message, [capture_link])

        html_content = """
        <html>
            <head>
                <link rel="stylesheet" href="/style.css">
            </head>
            <body>
                <a href="/foo">Foo</a>
                <img src="https://example.com/img.png" alt="Image">
                <iframe src="/frame"></iframe>
            </body>
        </html>
        """

        parser.feed(html_content)

        expected_links = [
            ("link", "/style.css"),
            ("a", "/foo"),
            ("img", "https://example.com/img.png"),
            ("iframe", "/frame"),
        ]

        self.assertEqual(len(links), len(expected_links))
        for expected in expected_links:
            self.assertIn(expected, links)

    def test_link_parsing_gzip_encoded(self):
        """Link parser must receive decoded bytes, not the raw network stream."""
        links = []

        def capture_link(base: str, link: str, tag: str, title: str) -> None:
            links.append((tag, link))

        message = HttpMessageLinter()
        message.process_headers(
            [
                (b"content-type", b"text/html"),
                (b"content-encoding", b"gzip"),
            ]
        )
        message.base_uri = "http://example.com/"

        parser = HTMLLinkParser(message, [capture_link])
        message.decoded.processors.append(parser.feed_bytes)

        html_content = b'<html><body><a href="/foo">Foo</a></body></html>'
        compressed = gzip.compress(html_content)

        message.feed_content(compressed)
        message.finish_content(True)

        self.assertIn(("a", "/foo"), links)

    def test_descend_resource_receives_decoded_links(self):
        """End-to-end: HttpResource with descend=True extracts links from gzip responses."""
        conf = ConfigParser()
        conf.add_section("redbot")
        resource = HttpResource(conf["redbot"], descend=True)

        captured = []
        resource.process_link = lambda base, link, tag, title: captured.append((tag, link))
        resource._link_parser.link_procs = [resource.process_link]

        resource.response.process_headers(
            [
                (b"content-type", b"text/html"),
                (b"content-encoding", b"gzip"),
            ]
        )
        resource.response.base_uri = "http://example.com/"

        body = b'<html><body><a href="/bar">Bar</a></body></html>'
        resource.response.feed_content(gzip.compress(body))
        resource.response.finish_content(True)

        self.assertIn(("a", "/bar"), captured)


class TestLinkParseChunking(unittest.TestCase):
    "Links survive a chunk boundary inside a character, and bad bytes can't alter them (#505)."

    @staticmethod
    def parse(chunks, content_type=b"text/html"):
        links = []
        message = HttpMessageLinter()
        message.process_headers([(b"content-type", content_type)])
        message.base_uri = "http://example.com/"
        parser = HTMLLinkParser(message, [lambda base, link, tag, title: links.append(link)])
        for chunk in chunks:
            parser.feed_bytes(chunk)
        parser.finish()
        return links

    def test_utf8_character_split_across_chunks(self):
        body = '<a href="/café">x</a><a href="/ok">ok</a>'.encode("utf-8")
        split = body.index(b"\xc3") + 1
        self.assertEqual(
            self.parse([body[:split], body[split:]], b"text/html; charset=utf-8"),
            ["/café", "/ok"],
        )

    def test_utf8_split_with_no_charset(self):
        body = '<a href="/café">x</a>'.encode("utf-8")
        split = body.index(b"\xc3") + 1
        self.assertEqual(self.parse([body[:split], body[split:]]), ["/café"])

    def test_double_byte_character_split_across_chunks(self):
        body = '<a href="/日本">x</a>'.encode("shift_jis")
        split = body.index(b"/") + 2
        self.assertEqual(
            self.parse([body[:split], body[split:]], b"text/html; charset=shift_jis"),
            ["/日本"],
        )

    def test_link_in_the_last_chunk_is_found(self):
        self.assertEqual(self.parse([b'<a href="/caf', b'e">x</a>']), ["/cafe"])

    def test_resource_flushes_the_parser_when_the_fetch_is_done(self):
        conf = ConfigParser()
        conf.read_dict({"redbot": {"max_links": "10"}})
        resource = HttpResource(conf["redbot"], descend=True, active_checks_enabled=False)
        resource.set_request("http://example.com/")
        resource.response.process_response_topline(b"1.1", b"200", b"OK")
        resource.response.process_headers([(b"Content-Type", b"text/html; charset=utf-8")])
        body = '<a href="/café">x</a>'.encode("utf-8")
        split = body.index(b"\xc3") + 1
        resource.response.decoded.feed_content(body[:split])
        resource.response.decoded.feed_content(body[split:])
        resource.response.finish_content(True)
        resource.emit("fetch_done")
        self.assertEqual(resource.links["a"], {"/café"})

    def test_utf16_without_a_bom_does_not_raise(self):
        body = '<a href="/ok">x</a>'.encode("utf-8")
        self.assertEqual(self.parse([body], b"text/html; charset=utf-16"), ["/ok"])

    def test_meta_utf16_does_not_raise(self):
        head = b'<meta http-equiv="content-type" content="text/html; charset=utf-16">'
        self.assertEqual(self.parse([head, b'<a href="/ok">x</a>']), ["/ok"])

    def test_nothing_is_flushed_after_a_stopped_fetch(self):
        conf = ConfigParser()
        conf.read_dict({"redbot": {"max_links": "10"}})
        resource = HttpResource(conf["redbot"], descend=True, active_checks_enabled=False)
        resource.set_request("http://example.com/")
        resource.response.process_response_topline(b"1.1", b"200", b"OK")
        resource.response.process_headers([(b"Content-Type", b"text/html")])
        resource.response.decoded.feed_content(b'<img src="/held')
        resource.response.decoded.feed_content(b'.png">')
        resource.stop()  # the response never completed
        self.assertEqual(resource.linked, [])

    def test_every_split_point(self):
        body = '<a href="/café/日本語">x</a>'.encode("utf-8")
        for i in range(1, len(body)):
            self.assertEqual(self.parse([body[:i], body[i:]]), ["/café/日本語"], i)

    def test_invalid_bytes_are_replaced_not_dropped(self):
        links = self.parse([b'<a href="/caf\xe9">x</a>'])
        self.assertEqual(links, ["/caf�"])

    def test_unusable_charset_falls_back_to_utf8(self):
        body = '<a href="/café">x</a>'.encode("utf-8")
        self.assertEqual(self.parse([body], b"text/html; charset=hex"), ["/café"])

    def test_meta_charset_change_mid_stream(self):
        head = b'<meta http-equiv="content-type" content="text/html; charset=latin-1">'
        self.assertEqual(self.parse([head, b'<a href="/caf\xe9">x</a>']), ["/café"])


if __name__ == "__main__":
    unittest.main()
