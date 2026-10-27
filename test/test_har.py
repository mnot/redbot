import json
import unittest
from typing import List
from unittest.mock import MagicMock

from httplint.message import HttpResponseLinter

from redbot.formatter.har import HarFormatter, format_media_type


def make_formatter(out: List[str]) -> HarFormatter:
    return HarFormatter(MagicMock(), MagicMock(), out.append, {})


class TestMimeType(unittest.TestCase):
    def test_no_content_type(self) -> None:
        self.assertEqual(format_media_type(None), "")

    def test_no_params(self) -> None:
        self.assertEqual(format_media_type(("text/html", {})), "text/html")

    def test_params(self) -> None:
        self.assertEqual(
            format_media_type(("text/html", {"charset": "utf-8", "q": "1"})),
            "text/html; charset=utf-8; q=1",
        )

    def test_quoted_param(self) -> None:
        self.assertEqual(
            format_media_type(("multipart/form-data", {"boundary": 'a b"c'})),
            'multipart/form-data; boundary="a b\\"c"',
        )

    def test_trailing_newline_is_quoted(self) -> None:
        self.assertEqual(
            format_media_type(("text/html", {"a": "x\n"})),
            'text/html; a="x\n"',
        )

    def entry_mime_type(self, content_type: bytes) -> object:
        "Build an entry from a response parsed by httplint, and return its mimeType."
        response = HttpResponseLinter()
        response.process_response_topline(b"1.1", b"200", b"OK")
        response.process_headers([(b"Content-Type", content_type)])
        response.start_time = 2.0
        response.finish_time = 3.0
        resource = MagicMock()
        resource.request.start_time = 1.0
        resource.request.headers.text = []
        resource.response = response
        resource.response_header_length = 10
        formatter = make_formatter([])
        formatter.add_entry(resource)
        return formatter.har["log"]["entries"][0]["response"]["content"]["mimeType"]

    def test_entry_mime_type_is_string(self) -> None:
        self.assertEqual(
            self.entry_mime_type(b"text/html; charset=utf-8"), "text/html; charset=utf-8"
        )

    def test_entry_quoted_param(self) -> None:
        self.assertEqual(
            self.entry_mime_type(b'multipart/form-data; boundary="a b"'),
            'multipart/form-data; boundary="a b"',
        )


class TestErrorOutput(unittest.TestCase):
    def test_error_is_valid_har_json(self) -> None:
        out: List[str] = []
        make_formatter(out).error_output('REDbot "timeout".')
        har = json.loads("".join(out))
        self.assertEqual(har["log"]["entries"], [])
        self.assertEqual(har["log"]["_red_error"], 'REDbot "timeout".')
        for field in ("version", "creator"):
            self.assertIn(field, har["log"])


class TestFailedFetch(unittest.TestCase):
    "A fetch that failed must not look like a successful run with nothing in it (#535)."

    def finish(self, fetch_error: object) -> dict:
        resource = MagicMock()
        resource.response.complete = False
        resource.fetch_error = fetch_error
        out: List[str] = []
        HarFormatter(MagicMock(), resource, out.append, {}).finish_output()
        return json.loads("".join(out))

    def test_error_is_reported(self) -> None:
        error = MagicMock()
        error.desc = "Connection error"
        error.detail = "Server dropped connection before the response was complete."
        har = self.finish(error)
        self.assertEqual(har["log"]["entries"], [])
        self.assertEqual(
            har["log"]["_red_error"],
            "Connection error (Server dropped connection before the response was complete.)",
        )

    def test_incomplete_response_without_an_error_is_still_flagged(self) -> None:
        self.assertIn("_red_error", self.finish(None)["log"])

    def test_check_that_never_ran_is_not_reported_as_failed(self) -> None:
        resource = MagicMock()
        resource.response.complete = False
        resource.fetch_error = None
        resource.fetch_started = False
        out: List[str] = []
        HarFormatter(MagicMock(), resource, out.append, {}).finish_output()
        self.assertNotIn("_red_error", json.loads("".join(out))["log"])

    def test_complete_response_has_no_error(self) -> None:
        resource = MagicMock()
        resource.response.complete = True
        resource.linked = []
        formatter = HarFormatter(MagicMock(), resource, lambda _: None, {})
        formatter.add_page = MagicMock(return_value=1)  # type: ignore[method-assign]
        formatter.add_entry = MagicMock()  # type: ignore[method-assign]
        formatter.finish_output()
        self.assertNotIn("_red_error", formatter.har["log"])


if __name__ == "__main__":
    unittest.main()
