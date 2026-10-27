#!/usr/bin/env python3

import unittest
from configparser import ConfigParser
from types import SimpleNamespace

import redbot.formatter.har
import redbot.formatter.html
import redbot.formatter.text as text
from httplint.note import categories

from redbot.formatter import available_formatters, find_formatter
from redbot.formatter.html import SingleEntryHtmlFormatter, TableHtmlFormatter
from redbot.i18n import set_locale
from redbot.resource import HttpResource
from redbot.webui.links import WebUiLinkGenerator


class TestFindFormatter(unittest.TestCase):
    def test_text_single_and_list(self):
        self.assertIs(find_formatter("text", "text", False), text.TextFormatter)
        self.assertIs(find_formatter("text", "text", True), text.TextListFormatter)

    def test_text_verbose_single_and_list(self):
        self.assertIs(find_formatter("text_verbose", "text", False), text.VerboseTextFormatter)
        self.assertIs(find_formatter("text_verbose", "text", True), text.VerboseTextListFormatter)

    def test_html_single_and_list(self):
        html = redbot.formatter.html
        self.assertIs(find_formatter("html", "html", False), html.SingleEntryHtmlFormatter)
        self.assertIs(find_formatter("html", "html", True), html.TableHtmlFormatter)

    def test_har(self):
        self.assertIs(find_formatter("har", "html", False), redbot.formatter.har.HarFormatter)

    def test_unknown_uses_default(self):
        self.assertIs(find_formatter("nonesuch", "text", False), text.TextFormatter)

    def test_every_available_formatter_resolves(self):
        for name in available_formatters():
            for multiple in (False, True):
                formatter = find_formatter(name, "html", multiple)
                self.assertEqual(formatter.name, name)

    def test_existing_names_kept(self):
        for name in ("html", "text", "har"):
            self.assertIn(name, available_formatters())


class TestHtmlFormatterIsolation(unittest.TestCase):
    "Formatters share one template environment; none may see another's resource."

    @staticmethod
    def _formatter(config, uri, formatter_class):
        resource = HttpResource(config)
        resource.set_request(uri, headers=[("Cookie", f"secret-for-{uri}")])
        resource.response.process_response_topline(b"1.1", b"302", b"Found")
        resource.response.process_headers(
            [(b"Location", f"{uri}next".encode()), (b"Content-Type", b"text/html")]
        )
        resource.response.finish_content(True)
        out: list[str] = []
        formatter = formatter_class(
            config,
            resource,
            out.append,
            {"nonce": "n", "link_generator": WebUiLinkGenerator(SimpleNamespace(config=config))},
        )
        return formatter, out

    def test_single_entry_formatters_do_not_leak(self):
        config = ConfigParser()
        config.add_section("redbot")
        cfg = config["redbot"]
        first, first_out = self._formatter(cfg, "http://a.example/", SingleEntryHtmlFormatter)
        self._formatter(cfg, "http://b.example/", SingleEntryHtmlFormatter)
        with set_locale("en"):
            first.finish_output()
        page = "".join(first_out)
        self.assertIn("a.example", page)
        self.assertNotIn("b.example", page)
        self.assertNotIn("secret-for-http://b.example/", page)

    def test_subrequest_messages_use_the_rendering_formatter(self):
        config = ConfigParser()
        config.add_section("redbot")
        cfg = config["redbot"]
        first, _ = self._formatter(cfg, "http://a.example/", SingleEntryHtmlFormatter)
        second, _ = self._formatter(cfg, "http://b.example/", SingleEntryHtmlFormatter)
        first.kw["test_id"] = "first_id"
        second.kw["test_id"] = "second_id"
        for formatter in (first, second):
            formatter.resource.subreqs["range"].fetch_started = True
        template = first.templates.from_string("{{ category|subrequest_messages }}")
        with set_locale("en"):
            out = template.render(formatter=first, category=categories.RANGE)
        self.assertIn("first_id", out)
        self.assertNotIn("second_id", out)

    def test_table_formatters_keep_their_own_problems(self):
        config = ConfigParser()
        config.add_section("redbot")
        cfg = config["redbot"]
        first, _ = self._formatter(cfg, "http://a.example/", TableHtmlFormatter)
        second, _ = self._formatter(cfg, "http://b.example/", TableHtmlFormatter)
        with set_locale("en"):
            first.finish_output()
        self.assertEqual(len(first.problems), 1)
        self.assertEqual(second.problems, [])


if __name__ == "__main__":
    unittest.main()
