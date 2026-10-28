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
from unittest.mock import MagicMock, patch

from redbot.formatter.html import TableHtmlFormatter
from redbot.i18n import set_locale
from redbot.resource import HttpResource
from redbot.webui.handlers.run_test import RunTestHandler
from redbot.webui.handlers.save import LoadSavedTestHandler
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
        self.assertIn(">301</button>", page)  # the link's label

    def test_error_statuses_are_marked_bad(self):
        page = self.render()
        self.assertIn('<td class="bad">404</td>', page)
        self.assertNotIn('<td class="bad">200</td>', page)

    def test_links_are_balanced(self):
        counter = TagCounter()
        counter.feed(self.render())
        self.assertEqual(counter.opened, counter.closed)


class TestRedirectLinks(unittest.TestCase):
    "The redirect link in the table resolves Location against the linked resource (#526)."

    def render(self, uri: str, location: str) -> str:
        cfg = config()["redbot"]
        top = HttpResource(cfg, descend=True)
        top.set_request("http://top.example/page")
        respond(top, b"200")
        linked = HttpResource(cfg, active_checks_enabled=False)
        linked.set_request(uri)
        respond(linked, b"301", [(b"Location", location.encode())])
        top.linked.append((linked, "script"))
        out: List[str] = []
        formatter = table_formatter(top, out)
        with set_locale("en"):
            formatter.finish_output()
        return "".join(out)

    def test_relative_location_is_resolved_against_the_linked_resource(self):
        page = self.render("http://other.example/sub/dir/mv3", "next")
        self.assertIn('name="uri" value="http://other.example/sub/dir/next"', page)

    def test_absolute_location_is_kept(self):
        page = self.render("http://other.example/mv", "https://third.example/x")
        self.assertIn('name="uri" value="https://third.example/x"', page)

    def test_useless_locations_get_no_link(self):
        for location in ["", " "]:
            with self.subTest(location=location):
                page = self.render("http://other.example/sub/mv", location)
                self.assertNotIn(">301</button>", page)  # shown, but not as a link
                self.assertIn("<td>301</td>", page)


class TestDescendWithACheck(unittest.TestCase):
    "A descend run shows the top resource even if a check is named, because only it has links."

    def test_run_test_displays_the_top_resource(self):
        ui = MagicMock()
        ui.config = config()["redbot"]
        ui.query_string = {
            "uri": ["http://example.com/"],
            "descend": ["True"],
            "check_name": ["range"],
        }
        ui.response_done = False
        with (
            patch("redbot.webui.handlers.run_test.thor.schedule"),
            patch("redbot.webui.handlers.run_test.HttpResource") as resource_class,
            patch("redbot.webui.handlers.run_test.find_formatter") as find_formatter,
            patch("redbot.webui.handlers.run_test.ratelimiter.process"),
            patch("redbot.webui.handlers.run_test.CaptchaHandler") as captcha,
        ):
            captcha.return_value.configured.return_value = False
            RunTestHandler.handle(ui)
        top = resource_class.return_value
        find_formatter.return_value.return_value.bind_resource.assert_called_once_with(top)

    def test_saved_descend_test_renders_the_table_for_a_named_check(self):
        top = descend_resource()
        top.check_done = True  # as in a saved test
        ui = MagicMock()
        ui.config = config()["redbot"]
        ui.query_string = {"check_name": ["conneg"]}
        ui.nonce = "n"
        ui.link_generator = WebUiLinkGenerator(SimpleNamespace(config=ui.config))
        with set_locale("en"):
            rendered = LoadSavedTestHandler.render_saved(ui, "abc", top, False, 0.0)
        self.assertIsNotNone(rendered)
        page = "".join(rendered[1])
        self.assertIn("moved.js", page)  # the linked resources are there
        ui.error_response.assert_not_called()


if __name__ == "__main__":
    unittest.main()
