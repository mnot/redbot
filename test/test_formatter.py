#!/usr/bin/env python3

import unittest

import redbot.formatter.har
import redbot.formatter.html
import redbot.formatter.text as text
from redbot.formatter import available_formatters, find_formatter


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


if __name__ == "__main__":
    unittest.main()
