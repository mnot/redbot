import json
import unittest
from typing import List
from unittest.mock import MagicMock

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

    def test_entry_mime_type_is_string(self) -> None:
        resource = MagicMock()
        resource.request.start_time = 1.0
        resource.response.start_time = 2.0
        resource.response.finish_time = 3.0
        resource.response.notes = []
        resource.request.headers.text = []
        resource.response.headers.text = []
        resource.response.decoded.length = 10
        resource.response.content_length = 10
        resource.response_header_length = 10
        resource.response.headers.parsed = {"content-type": ("text/html", {"charset": "utf-8"})}
        formatter = make_formatter([])
        formatter.add_entry(resource)
        mime_type = formatter.har["log"]["entries"][0]["response"]["content"]["mimeType"]
        self.assertEqual(mime_type, "text/html; charset=utf-8")


class TestErrorOutput(unittest.TestCase):
    def test_error_is_valid_har_json(self) -> None:
        out: List[str] = []
        make_formatter(out).error_output('REDbot "timeout".')
        har = json.loads("".join(out))
        self.assertEqual(har["log"]["entries"], [])
        self.assertEqual(har["log"]["_red_error"], 'REDbot "timeout".')
        for field in ("version", "creator"):
            self.assertIn(field, har["log"])


if __name__ == "__main__":
    unittest.main()
