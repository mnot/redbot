#!/usr/bin/env python3

import unittest
from configparser import ConfigParser

import thor.http.error as httperr

from redbot.formatter import find_formatter
from redbot.i18n import set_locale
from redbot.resource import HttpResource

PAYLOAD = "<script/src=//attacker.test/x.js></script>"


def make_formatter(output):
    parser = ConfigParser()
    parser.read_dict({"redbot": {}})
    config = parser["redbot"]
    resource = HttpResource(config)
    return find_formatter("html")(config, resource, output, {"nonce": "n"})


class TestErrorOutputEscaping(unittest.TestCase):
    def test_error_output_escapes_message(self):
        out = []
        with set_locale("en"):
            make_formatter(out.append).error_output(f"bad ({PAYLOAD})")
        page = "".join(out)
        self.assertNotIn("<script/src", page)
        self.assertIn("&lt;script/src=//attacker.test/x.js&gt;&lt;/script&gt;", page)

    def test_fetch_error_detail_is_escaped(self):
        out = []
        formatter = make_formatter(out.append)
        formatter.resource.fetch_error = httperr.HttpVersionError(PAYLOAD)
        with set_locale("en"):
            formatter.finish_output()
        page = "".join(out)
        self.assertIn("Unrecognised HTTP version", page)
        self.assertNotIn("<script/src", page)
        self.assertIn("&lt;script/src", page)

    def test_plain_message_unchanged(self):
        out = []
        with set_locale("en"):
            make_formatter(out.append).error_output("REDbot timeout.")
        self.assertIn("<p class='error foo'>REDbot timeout.</p>", "".join(out))


if __name__ == "__main__":
    unittest.main()
