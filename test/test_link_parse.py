#!/usr/bin/env python3

import gzip
import unittest
from configparser import ConfigParser
from redbot.resource import HttpResource
from redbot.resource.link_parse import HTMLLinkParser
from httplint.message import HttpMessageLinter

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
        message.process_headers([
            (b"content-type", b"text/html"),
            (b"content-encoding", b"gzip"),
        ])
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

        resource.response.process_headers([
            (b"content-type", b"text/html"),
            (b"content-encoding", b"gzip"),
        ])
        resource.response.base_uri = "http://example.com/"

        body = b'<html><body><a href="/bar">Bar</a></body></html>'
        resource.response.feed_content(gzip.compress(body))
        resource.response.finish_content(True)

        self.assertIn(("a", "/bar"), captured)


if __name__ == "__main__":
    unittest.main()
