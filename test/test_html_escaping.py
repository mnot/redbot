#!/usr/bin/env python3

"""
The HTML formatter escapes each value once, in the right context (mnot/redbot#525).
"""

import unittest
from configparser import ConfigParser
from types import SimpleNamespace
from typing import List

from redbot.formatter.html import SingleEntryHtmlFormatter
from redbot.i18n import set_locale
from redbot.resource import HttpResource
from redbot.webui.links import WebUiLinkGenerator


class TestHtmlEscaping(unittest.TestCase):
    def formatter(self, location: str = "", **config: str):
        parser = ConfigParser()
        parser.read_dict({"redbot": config})
        cfg = parser["redbot"]
        resource = HttpResource(cfg)
        resource.set_request("http://a.example/")
        resource.response.process_response_topline(b"1.1", b"302", b"Found")
        headers = [(b"Content-Type", b"text/html")]
        if location:
            headers.append((b"Location", location.encode()))
        resource.response.process_headers(headers)
        resource.response.finish_content(True)
        out: List[str] = []
        formatter = SingleEntryHtmlFormatter(
            cfg,
            resource,
            out.append,
            {"nonce": "n", "link_generator": WebUiLinkGenerator(SimpleNamespace(config=cfg))},
        )
        return formatter, out

    def test_location_is_escaped_once(self):
        formatter, out = self.formatter("http://a.example/?x=1&y=2&z='\"<>")
        with set_locale("en"):
            formatter.finish_output()
        page = "".join(out)
        self.assertIn('value="http://a.example/?x=1&amp;y=2&amp;z=&#39;&#34;&lt;&gt;"', page)
        self.assertNotIn("&amp;amp;", page)
        self.assertNotIn("&amp;#", page)
        self.assertNotIn("&amp;lt;", page)

    def test_linkified_body_link_is_escaped_once(self):
        formatter, _ = self.formatter(content_links="yes")
        resource = formatter.resource
        resource.response_decoded_sample = [b'<a href="/page?a=1&b=2">x</a>']
        resource.links = {"a": {"/page?a=1&b=2"}}
        resource.response.base_uri = "http://a.example/"
        with set_locale("en"):
            body = str(formatter.format_body_sample(resource))
        self.assertIn('value="http://a.example/page?a=1&amp;b=2"', body)
        self.assertIn('class="post_link nocode"', body)
        self.assertNotIn("&amp;amp;", body)

    def test_status_is_escaped_for_javascript_not_html(self):
        formatter, out = self.formatter()
        formatter.status('fetching http://a.example/?a=1&b=2 (it\'s "x" </script>)')
        script = "".join(out)
        self.assertIn("a=1&b=2 (it's", script)
        self.assertNotIn("&amp;", script)
        self.assertNotIn("&#39;", script)
        self.assertIn(r"\"x\"", script)  # a quote can't end the string
        self.assertIn(r"\x3c/script>", script)  # nor can markup end the script


if __name__ == "__main__":
    unittest.main()
