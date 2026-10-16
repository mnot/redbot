#!/usr/bin/env python3

import os
import tempfile
import unittest
from configparser import ConfigParser
from unittest.mock import MagicMock, patch

from redbot.webui.handlers.run_test import RunTestHandler


def make_ui(save_dir, query_string):
    conf = ConfigParser()
    conf.add_section("redbot")
    conf["redbot"]["save_dir"] = save_dir
    ui = MagicMock()
    ui.config = conf["redbot"]
    ui.query_string = query_string
    ui.response_done = False
    return ui


class TestSaveFileCreation(unittest.TestCase):
    """Regression tests for #445: rejected requests must not create save files."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.save_dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)
        # Keep the real timer and network out of it.
        for target in ("thor.schedule", "redbot.webui.handlers.run_test.HttpResource"):
            patcher = patch(target)
            patcher.start()
            self.addCleanup(patcher.stop)

    def saved_files(self):
        return os.listdir(self.save_dir)

    def test_malformed_uri_leaves_no_file(self):
        ui = make_ui(self.save_dir, {"uri": ["http://example.com/"]})
        with patch("redbot.webui.handlers.run_test.iri_to_uri", side_effect=ValueError):
            RunTestHandler.handle(ui)
        self.assertEqual(ui.error_response.call_args[0][0], b"400")
        self.assertEqual(self.saved_files(), [])

    def test_bad_request_header_leaves_no_file(self):
        ui = make_ui(self.save_dir, {"uri": ["http://example.com/"], "req_hdr": ["no-colon"]})
        RunTestHandler.handle(ui)
        self.assertEqual(ui.error_response.call_args[0][0], b"400")
        self.assertEqual(self.saved_files(), [])

    def test_multiple_referers_leave_no_file(self):
        ui = make_ui(
            self.save_dir,
            {"uri": ["http://example.com/"], "req_hdr": ["Referer: a", "Referer: b"]},
        )
        RunTestHandler.handle(ui)
        self.assertEqual(ui.error_response.call_args[0][0], b"403")
        self.assertEqual(self.saved_files(), [])

    def test_rate_limited_request_leaves_no_file(self):
        ui = make_ui(self.save_dir, {"uri": ["http://example.com/"]})
        with patch("redbot.webui.handlers.run_test.ratelimiter.process", side_effect=ValueError):
            RunTestHandler.handle(ui)
        self.assertEqual(self.saved_files(), [])

    def test_pending_captcha_leaves_no_file(self):
        ui = make_ui(self.save_dir, {"uri": ["http://example.com/"]})
        with (
            patch("redbot.webui.handlers.run_test.ratelimiter.process"),
            patch("redbot.webui.handlers.run_test.CaptchaHandler") as captcha,
        ):
            captcha.return_value.configured.return_value = True
            RunTestHandler.handle(ui)
        captcha.return_value.run.assert_called_once()
        self.assertEqual(self.saved_files(), [])

    def test_accepted_request_creates_file_and_exposes_id(self):
        ui = make_ui(self.save_dir, {"uri": ["http://example.com/"]})
        params_seen = []

        def make_formatter(config, resource, output, params):
            # Like the real Formatter, keep a reference to the caller's dict.
            formatter = MagicMock()
            formatter.kw = params
            params_seen.append(params)
            return formatter

        with (
            patch("redbot.webui.handlers.run_test.ratelimiter.process"),
            patch("redbot.webui.handlers.run_test.CaptchaHandler") as captcha,
            patch("redbot.webui.handlers.run_test.find_formatter") as find_formatter,
        ):
            captcha.return_value.configured.return_value = False
            find_formatter.return_value.side_effect = make_formatter
            RunTestHandler.handle(ui)
        files = self.saved_files()
        self.assertEqual(len(files), 1)
        self.assertEqual(params_seen[0]["test_id"], files[0])
        self.assertEqual(params_seen[0]["allow_save"], files[0])

    def accepted_request(self, ui):
        """Run handle() through to _continue_test; return the formatter mock."""
        formatter = MagicMock()
        with (
            patch("redbot.webui.handlers.run_test.ratelimiter.process"),
            patch("redbot.webui.handlers.run_test.CaptchaHandler") as captcha,
            patch("redbot.webui.handlers.run_test.find_formatter") as find_formatter,
        ):
            captcha.return_value.configured.return_value = False
            find_formatter.return_value.return_value = formatter
            RunTestHandler.handle(ui)
        return formatter

    @staticmethod
    def fire_formatter_done(formatter):
        for call in formatter.on.call_args_list:
            if call[0][0] == "formatter_done":
                call[0][1]()
                return
        raise AssertionError("formatter_done listener not registered")

    def test_formatter_done_saves_when_file_was_created(self):
        ui = make_ui(self.save_dir, {"uri": ["http://example.com/"]})
        formatter = self.accepted_request(ui)
        with patch("redbot.webui.handlers.run_test.save_test") as save_test:
            self.fire_formatter_done(formatter)
        self.assertEqual(save_test.call_count, 1)

    def test_formatter_done_skips_save_when_file_creation_fails(self):
        # If mkstemp fails, init_save_file returns None and never sets
        # ui.save_path, so save_test must not be called.
        ui = make_ui(self.save_dir, {"uri": ["http://example.com/"]})
        with patch("tempfile.mkstemp", side_effect=OSError):
            formatter = self.accepted_request(ui)
        with patch("redbot.webui.handlers.run_test.save_test") as save_test:
            self.fire_formatter_done(formatter)
        save_test.assert_not_called()
        self.assertEqual(self.saved_files(), [])

    def test_response_done_before_continuation_leaves_no_file(self):
        # e.g. the runtime timeout fired while waiting on the captcha provider.
        ui = make_ui(self.save_dir, {"uri": ["http://example.com/"]})
        with (
            patch("redbot.webui.handlers.run_test.ratelimiter.process"),
            patch("redbot.webui.handlers.run_test.CaptchaHandler") as captcha,
        ):
            captcha.return_value.configured.return_value = True
            RunTestHandler.handle(ui)
        continue_test = captcha.call_args[0][1]
        ui.response_done = True
        continue_test()
        ui.exchange.response_start.assert_not_called()
        self.assertEqual(self.saved_files(), [])


if __name__ == "__main__":
    unittest.main()
