#!/usr/bin/env python3

"""
The table view of linked resources (mnot/redbot#526), and the formats that list them, cope with
being bound to a check rather than the whole test.
"""

import unittest
from configparser import ConfigParser
from html.parser import HTMLParser
from types import SimpleNamespace
from typing import List, Optional, Tuple

from redbot.formatter.har import HarFormatter
from redbot.formatter.html import TableHtmlFormatter
from redbot.formatter.text import TextListFormatter
from redbot.i18n import set_locale
from redbot.resource import HttpResource
from redbot.webui.links import WebUiLinkGenerator


class TagCounter(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.opened = 0
        self.closed = 0

    def handle_starttag(self, tag, attrs):
        self.opened += tag == "a"

    def handle_endtag(self, tag):
        self.closed += tag == "a"


def config() -> ConfigParser:
    parser = ConfigParser()
    parser.add_section("redbot")
    return parser


def respond(
    resource: HttpResource, status: bytes, headers: Optional[List[Tuple[bytes, bytes]]] = None
) -> None:
    resource.response.process_response_topline(b"1.1", status, b"Phrase")
    resource.response.process_headers(headers or [(b"Content-Type", b"text/html")])
    resource.response.finish_content(True)
    resource.request.start_time = resource.response.start_time = 1.0


def descend_resource() -> HttpResource:
    cfg = config()["redbot"]
    top = HttpResource(cfg, descend=True)
    top.set_request("http://a.example/")
    respond(top, b"200")
    for path, status, headers in [
        ("moved.js", b"301", [(b"Location", b"http://a.example/new.js")]),
        ("gone.js", b"404", None),
        ("fine.js", b"200", None),
    ]:
        linked = HttpResource(cfg, active_checks_enabled=False)
        linked.set_request(f"http://a.example/{path}")
        respond(linked, status, headers)
        top.linked.append((linked, "script"))
    return top


def table_formatter(resource: HttpResource, output: List[str]) -> TableHtmlFormatter:
    cfg = config()["redbot"]
    return TableHtmlFormatter(
        cfg,
        resource,
        output.append,
        {"nonce": "n", "link_generator": WebUiLinkGenerator(SimpleNamespace(config=cfg))},
    )


class TestTableView(unittest.TestCase):
    def render(self) -> str:
        out: List[str] = []
        formatter = table_formatter(descend_resource(), out)
        with set_locale("en"):
            formatter.finish_output()
        return "".join(out)

    def test_redirect_links_to_its_location(self):
        page = self.render()
        self.assertIn('name="uri" value="http://a.example/new.js"', page)
        self.assertIn('value="301"', page)  # the link's label

    def test_error_statuses_are_marked_bad(self):
        page = self.render()
        self.assertIn('<td class="bad">404</td>', page)
        self.assertNotIn('<td class="bad">200</td>', page)

    def test_links_are_balanced(self):
        counter = TagCounter()
        counter.feed(self.render())
        self.assertEqual(counter.opened, counter.closed)


class TestFormatsBoundToACheck(unittest.TestCase):
    "With descend and check_name, the displayed resource is a SubRequest, which has no .linked."

    def subrequest(self) -> HttpResource:
        top = descend_resource()
        subrequest = top.subreqs["range"]
        subrequest.set_request("http://a.example/")
        respond(subrequest, b"206")
        subrequest.response.finish_time = 2.0
        return subrequest

    def test_table_view(self):
        out: List[str] = []
        formatter = table_formatter(self.subrequest(), out)
        with set_locale("en"):
            formatter.finish_output()
        self.assertIn("</html>", "".join(out))

    def test_text_list(self):
        out: List[str] = []
        formatter = TextListFormatter(config()["redbot"], self.subrequest(), out.append, {})
        formatter.finish_output()
        self.assertTrue(out)

    def test_har(self):
        out: List[str] = []
        formatter = HarFormatter(config()["redbot"], self.subrequest(), out.append, {})
        formatter.finish_output()
        self.assertIn('"log"', "".join(out))


if __name__ == "__main__":
    unittest.main()
