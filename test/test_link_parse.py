#!/usr/bin/env python3

import unittest
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

if __name__ == "__main__":
    unittest.main()
