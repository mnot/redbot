#!/usr/bin/env python3

"""
An error response is in the format the client asked for (mnot/redbot#537).
"""

import json
import unittest
from configparser import ConfigParser
from typing import List
from unittest.mock import MagicMock

from redbot.webui import RedWebUi


def error_response(query: bytes):
    parser = ConfigParser()
    parser.add_section("redbot")
    exchange = MagicMock()
    ui = RedWebUi(parser["redbot"], "POST", b"check", query, [], b"", exchange, "127.0.0.1")
    ui.error_response(b"400", b"Bad Request", "Request URI is <malformed>.")
    headers = dict(exchange.response_start.call_args[0][2])
    body = b"".join(call[0][0] for call in exchange.response_body.call_args_list).decode()
    return exchange.response_start.call_args[0][0], headers[b"Content-Type"], body


class TestErrorFormat(unittest.TestCase):
    def test_default_is_html(self):
        status, content_type, body = error_response(b"uri=x")
        self.assertEqual(status, b"400")
        self.assertTrue(content_type.startswith(b"text/html"))
        self.assertIn("Request URI is &lt;malformed&gt;.", body)

    def test_har(self):
        _, content_type, body = error_response(b"uri=x&format=har")
        self.assertTrue(content_type.startswith(b"application/json"))
        self.assertEqual(json.loads(body)["log"]["_red_error"], "Request URI is <malformed>.")

    def test_text(self):
        _, content_type, body = error_response(b"uri=x&format=text")
        self.assertTrue(content_type.startswith(b"text/plain"), content_type)
        self.assertIn("Request URI is <malformed>.", body)
        self.assertNotIn("<html", body)

    def test_unknown_format_falls_back_to_html(self):
        _, content_type, _ = error_response(b"uri=x&format=nonesuch")
        self.assertTrue(content_type.startswith(b"text/html"))


if __name__ == "__main__":
    unittest.main()
