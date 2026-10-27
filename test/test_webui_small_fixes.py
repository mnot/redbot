#!/usr/bin/env python3

"""
Small Web UI behaviours: saving a missing test (mnot/redbot#528) and the client error log
(mnot/redbot#536).
"""

import tempfile
import unittest
from configparser import ConfigParser
from unittest.mock import MagicMock

from redbot.webui.handlers.client_error import ClientErrorHandler
from redbot.webui.handlers.save import SaveHandler


def make_ui(**values: str) -> MagicMock:
    parser = ConfigParser()
    parser.read_dict({"redbot": values})
    ui = MagicMock()
    ui.config = parser["redbot"]
    ui.query_string = {}
    return ui


class TestSaveMissingTest(unittest.TestCase):
    def test_missing_id_is_a_404(self):
        with tempfile.TemporaryDirectory() as save_dir:
            ui = make_ui(save_dir=save_dir)
            ui.path = ["saved", "zzzzzzzz"]
            SaveHandler.handle(ui)
        self.assertEqual(ui.error_response.call_args[0][0], b"404")

    def test_missing_save_directory_is_a_404_like_the_get_side(self):
        ui = make_ui(save_dir="/nonexistent/redbot-save-dir")
        ui.path = ["saved", "abcdefgh"]
        SaveHandler.handle(ui)
        self.assertEqual(ui.error_response.call_args[0][0], b"404")

    def test_existing_id_redirects(self):
        with tempfile.TemporaryDirectory() as save_dir:
            open(f"{save_dir}/abcdefgh", "wb").close()
            ui = make_ui(save_dir=save_dir)
            ui.path = ["saved", "abcdefgh"]
            SaveHandler.handle(ui)
        ui.error_response.assert_not_called()
        self.assertEqual(ui.exchange.response_start.call_args[0][0], b"303")


class TestClientErrorLog(unittest.TestCase):
    def logged(self, body: bytes) -> str:
        ui = make_ui()
        ui.req_body = body
        ClientErrorHandler.handle(ui)
        return ui.error_log.call_args[0][0]

    def test_control_characters_cannot_reach_the_log(self):
        line = self.logged(b"boom\rFAKE LOG LINE\x0b\x0c\x1b[31m\nnext")
        for char in "\r\n\x0b\x0c\x1b":
            self.assertNotIn(char, line)
        self.assertTrue(line.startswith("Client JS -> boom"))

    def test_ordinary_messages_are_unchanged(self):
        self.assertEqual(
            self.logged(b"Uncaught TypeError: x is undefined at /static/script.js, 3:4"),
            "Client JS -> Uncaught TypeError: x is undefined at /static/script.js, 3:4",
        )


if __name__ == "__main__":
    unittest.main()
