#!/usr/bin/env python3

import tempfile
import unittest
from configparser import ConfigParser
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from redbot.daemon import RedRequestHandler
from redbot.formatter import find_formatter
from redbot.formatter.html import HeaderPresenter
from redbot.resource import HttpResource
from redbot.resource.link_parse import HTMLLinkParser
from redbot.utils import decode_text
from redbot.webui import RedWebUi
from redbot.webui.links import WebUiLinkGenerator
from redbot.webui.handlers.run_test import RunTestHandler
from redbot.webui.handlers.save import LoadSavedTestHandler, SaveHandler
from redbot.webui.saved_tests import save_test, valid_test_id


def config(**values):
    parser = ConfigParser()
    parser.read_dict({"redbot": values})
    return parser["redbot"]


def request_status(method, uri):
    "Run a request through RedRequestHandler.request_done; return the status it sent."
    exchange = MagicMock()
    server = SimpleNamespace(
        config=config(),
        static_root=b"/static",
        extra_files={},
        ui_path=b"/",
        signer=None,
        static_files=MagicMock(),
        console=MagicMock(),
    )
    handler = RedRequestHandler(exchange, server)
    handler.method = method
    handler.uri = uri
    handler.req_hdrs = [(b"Host", b"x")]
    with patch("redbot.daemon.RedWebUi") as web_ui:
        handler.request_done([])
    if web_ui.called:
        return b"dispatched"
    return exchange.response_start.call_args[0][0]


class TestDaemonRequestTarget(unittest.TestCase):
    def test_bad_ipv6_authority(self):
        self.assertEqual(request_status(b"GET", b"//["), b"400")

    def test_non_utf8_method(self):
        self.assertEqual(request_status(b"\xff\xfe", b"/"), b"400")

    def test_nul_in_saved_path(self):
        self.assertEqual(request_status(b"GET", b"/saved/a\x00b"), b"400")

    def test_nul_in_static_path(self):
        self.assertEqual(request_status(b"GET", b"/static/a\x00b"), b"400")

    def test_ordinary_request_dispatches(self):
        self.assertEqual(request_status(b"GET", b"/"), b"dispatched")


class TestSavedTestIds(unittest.TestCase):
    def ui(self, method, test_id):
        return SimpleNamespace(
            config=config(save_dir=tempfile.gettempdir()),
            method=method,
            path=["saved", test_id],
            query_string={},
            exchange=MagicMock(),
            error_response=MagicMock(),
        )

    def test_valid_ids(self):
        self.assertTrue(valid_test_id("lu5wrg7x"))
        self.assertTrue(valid_test_id("a_B9"))

    def test_invalid_ids(self):
        for bad in ["..", ".", "a/b", "a\x00b", "", "é", "a b"]:
            self.assertFalse(valid_test_id(bad), bad)

    def test_save_rejects_dotdot_without_touching_files(self):
        ui = self.ui("POST", "..")
        with patch("redbot.webui.handlers.save.os.utime") as utime:
            SaveHandler.handle(ui)
        utime.assert_not_called()
        self.assertEqual(ui.error_response.call_args[0][0], b"400")

    def test_load_rejects_nul(self):
        ui = self.ui("GET", "a\x00b")
        LoadSavedTestHandler.handle(ui)
        self.assertEqual(ui.error_response.call_args[0][0], b"404")


class TestSaveTest(unittest.TestCase):
    def test_no_save_path_is_skipped(self):
        with tempfile.TemporaryDirectory() as save_dir:
            ui = SimpleNamespace(config={"save_dir": save_dir}, save_path="")
            save_test(ui, MagicMock())  # must not raise


class TestHeaderPresenter(unittest.TestCase):
    def setUp(self):
        self.formatter = MagicMock()
        self.formatter.links.resource_link.return_value = "<a>link</a>"
        self.presenter = HeaderPresenter(self.formatter)

    def test_field_named_like_an_attribute(self):
        for name in ["Formatter", "show", "bare-uri", "__init__", ""]:
            self.assertEqual(str(self.presenter.show(name, " x<")), "x&lt;", name)

    def test_presenter_is_found_by_prefix(self):
        class Custom(HeaderPresenter):
            def present_x_custom(self, name, value):
                return f"[{name}={value}]"

        self.assertEqual(Custom(self.formatter).show("X-Custom", "v"), "[x-custom=v]")
        # the prefix, not the bare name, selects a presenter
        self.assertEqual(str(Custom(self.formatter).show("present-x-custom", "v")), "v")

    def test_uri_fields_are_links(self):
        for name in ["Location", "Content-Location", "X-XRDS-Location"]:
            self.assertEqual(str(self.presenter.show(name, " /a")), "<a>link</a>", name)


class TestCharsetFromRemote(unittest.TestCase):
    def test_decode_text_fallbacks(self):
        for charset in ["undefined", "hex", "rot13", "no-such-charset", None, ""]:
            self.assertEqual(decode_text(b"abc", charset), "abc", charset)

    def test_decode_text_honours_valid_charset(self):
        self.assertEqual(decode_text("é".encode("latin-1"), "latin-1"), "é")

    def test_body_sample_with_bad_charset(self):
        cfg = config()
        resource = HttpResource(cfg)
        resource.response_decoded_sample = [b"hello"]
        resource.response.character_encoding = "undefined"
        formatter = find_formatter("html")(cfg, resource, lambda s: None, {"nonce": "n"})
        self.assertIn("hello", str(formatter.format_body_sample(resource)))

    def test_link_parser_with_bad_charset(self):
        for charset in ["undefined", "hex"]:
            message = MagicMock()
            message.character_encoding = charset
            parser = HTMLLinkParser(message, [])
            parser.feed_bytes(b"<a href='/x'>x</a>")  # must not raise


class TestNoSavePathByDefault(unittest.TestCase):
    def test_save_path_starts_empty(self):
        # init_save_file only sets save_path on success; save_test relies on the default.
        with patch.object(RedWebUi, "handlers", []):
            ui = RedWebUi(config(), "GET", b"", b"", [], b"", MagicMock(), "127.0.0.1")
        self.assertEqual(ui.save_path, "")


class TestHostileTargetOrReferer(unittest.TestCase):
    def test_nonfinal_response_without_exchange_version(self):
        # thor sets exchange.res_version only for final responses
        resource = HttpResource(config())
        resource.exchange = SimpleNamespace(res_version=None, conn=SimpleNamespace(res_version=b"1.1"))
        resource._response_nonfinal(b"103", b"Early Hints", [(b"Link", b"</a>")])
        self.assertEqual(len(resource.nonfinal_responses), 1)

    def test_unparseable_location_is_shown_as_text(self):
        resource = HttpResource(config())
        resource.set_request("http://example.com/")
        generator = WebUiLinkGenerator(SimpleNamespace(config=config()))
        html = generator.resource_link(resource, "http://[", "http://[", use_stored=False)
        self.assertEqual(html, "http://[")

    def test_unparseable_referer_with_spam_domains(self):
        ui = SimpleNamespace(
            config=config(referer_spam_domains="spam.example"),
            query_string={"uri": ["http://example.com/"], "req_hdr": ["Referer:http://["]},
            output=lambda chunk: None,
            nonce="n",
            locale="en",
            link_generator=MagicMock(),
            error_response=MagicMock(),
            timeout=None,
            timeout_error=MagicMock(),
            save_path="",
        )
        RunTestHandler.handle(ui)
        self.assertEqual(ui.error_response.call_args[0][0], b"403")


class TestDaemonSurvivesHostileCookies(unittest.TestCase):
    """
    #466: an exception out of RedWebUi makes RedRequestHandler.request_done stop
    the whole daemon, so run real requests through it with a captcha configured.
    """

    def post_check(self, cookie):
        exchange = MagicMock()
        server = SimpleNamespace(
            config=config(
                captcha_provider="hcaptcha",
                captcha_secret="s3cret",
                captcha_sitekey="key",
            ),
            static_root=b"/static",
            extra_files={},
            ui_path=b"/",
            signer=None,
            static_files=MagicMock(),
            console=MagicMock(),
        )
        handler = RedRequestHandler(exchange, server)
        handler.client_ip = "192.0.2.1"
        handler.method = b"POST"
        handler.uri = b"/check?uri=http://127.0.0.1:8001/"
        handler.req_hdrs = [(b"Host", b"x"), (b"Cookie", cookie)]
        handler.request_done([])
        return exchange.response_start.call_args[0][0]

    def test_non_ascii_hmac(self):
        self.assertEqual(self.post_check(b'human_time=9999999999; human_hmac="\\351"'), b"403")

    def test_non_ascii_time(self):
        self.assertEqual(self.post_check(b'human_time="\\262"; human_hmac=abc'), b"403")

    def test_overlong_time(self):
        self.assertEqual(self.post_check(b"human_time=" + b"9" * 5000 + b"; human_hmac=abc"), b"403")


if __name__ == "__main__":
    unittest.main()
