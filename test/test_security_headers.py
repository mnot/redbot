#!/usr/bin/env python3

import gzip
import pickle
import tempfile
import unittest
from configparser import ConfigParser
from types import SimpleNamespace
from unittest.mock import MagicMock

from redbot.resource import HttpResource
from redbot.webui import RedWebUi
from redbot.webui.handlers.save import LoadSavedTestHandler
from redbot.webui.handlers.show import ShowHandler
from redbot.webui.headers import security_headers


def config(**values):
    parser = ConfigParser()
    parser.read_dict({"redbot": values})
    return parser["redbot"]


class TestSecurityHeaders(unittest.TestCase):
    def test_policy(self):
        headers = dict(security_headers("abc"))
        policy = headers[b"Content-Security-Policy"].decode("ascii")
        self.assertEqual(
            policy,
            "script-src 'strict-dynamic' 'nonce-abc'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'",
        )
        self.assertEqual(headers[b"X-Content-Type-Options"], b"nosniff")


class TestSavedPageHeaders(unittest.TestCase):
    def test_saved_page_sends_csp(self):
        with tempfile.TemporaryDirectory() as save_dir:
            cfg = config(save_dir=save_dir)
            resource = HttpResource(cfg)
            resource.set_request("http://example.com/")
            resource.check_done = True  # as in a real, completed test
            with gzip.open(f"{save_dir}/abc123", "w") as fh:
                pickle.dump(resource, fh)

            ui = SimpleNamespace(
                config=cfg,
                path=["saved", "abc123"],
                query_string={},
                nonce="NONCE",
                link_generator=MagicMock(),
                exchange=MagicMock(),
                output=lambda chunk: None,
                response_done=False,
                error_response=MagicMock(),
            )
            LoadSavedTestHandler.handle(ui)

        ui.error_response.assert_not_called()
        status, _phrase, headers = ui.exchange.response_start.call_args[0]
        self.assertEqual(status, b"200")
        header_map = dict(headers)
        self.assertIn(b"nonce-NONCE", header_map[b"Content-Security-Policy"])
        self.assertEqual(header_map[b"X-Content-Type-Options"], b"nosniff")


class TestOtherResponsesSendHeaders(unittest.TestCase):
    def ui(self, **extra):
        return SimpleNamespace(
            config=config(),
            nonce="NONCE",
            locale="en",
            timeout=None,
            response_done=False,
            response_started=False,
            exchange=MagicMock(),
            output=lambda chunk: None,
            error_log=MagicMock(),
            link_generator=MagicMock(),
            query_string={},
            **extra,
        )

    def assert_headers(self, ui):
        headers = dict(ui.exchange.response_start.call_args[0][2])
        self.assertIn(b"nonce-NONCE", headers[b"Content-Security-Policy"])
        self.assertEqual(headers[b"X-Content-Type-Options"], b"nosniff")

    def test_error_response(self):
        ui = self.ui()
        RedWebUi.error_response(ui, b"400", b"Bad Request", "nope")
        self.assert_headers(ui)

    def test_show_page(self):
        ui = self.ui()
        ShowHandler.handle(ui)
        self.assert_headers(ui)


if __name__ == "__main__":
    unittest.main()
