#!/usr/bin/env python3

import http.server
import re
import subprocess
import sys
import threading
import unittest
from configparser import ConfigParser
from typing import Any, Dict, List

from redbot.formatter.html import SingleEntryHtmlFormatter
from redbot.resource import HttpResource


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"hi")

    do_HEAD = do_GET

    def log_message(self, format: str, *args: Any) -> None:  # pylint: disable=redefined-builtin
        pass


class TestHtmlNonce(unittest.TestCase):
    """
    Regression tests for #441: the HTML formatter required a CSP nonce that only the
    Web UI supplies, so `redbot -o html` died with KeyError: 'nonce'.
    """

    def _render(self, kw: Dict[str, Any]) -> str:
        conf = ConfigParser()
        conf.add_section("redbot")
        resource = HttpResource(conf["redbot"])
        resource.set_request("http://example.com/")
        out: List[str] = []
        formatter = SingleEntryHtmlFormatter(conf["redbot"], resource, out.append, kw)
        formatter.start_output()
        formatter.status("checking")
        formatter.debug("hello")
        formatter.finish_output()
        return "".join(out)

    def test_no_nonce(self) -> None:
        html = self._render({})
        self.assertIn("<title>", html)
        self.assertIn("#red_status", html)
        self.assertNotIn("nonce", html)

    def test_nonce(self) -> None:
        html = self._render({"nonce": "abc123"})
        # every script tag except the JSON-LD data block carries the nonce
        tags = re.findall(r"<script[^>]*>", html)
        self.assertTrue(tags)
        for tag in tags:
            if "ld+json" not in tag:
                self.assertIn('nonce="abc123"', tag)

    def test_cli_html_output(self) -> None:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "redbot.cli",
                    "-o",
                    "html",
                    f"http://127.0.0.1:{server.server_port}/",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("KeyError", result.stderr)
        self.assertIn("<!DOCTYPE html>", result.stdout)
        self.assertNotIn("nonce", result.stdout)


if __name__ == "__main__":
    unittest.main()
