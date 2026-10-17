"""
The text list formatter reports a failed fetch for a linked resource, rather than an empty
"HTTP/ None None" block (mnot/redbot#489).
"""

import re
import socket
import socketserver
import subprocess
import sys
import threading
import unittest
from configparser import ConfigParser
from typing import List, Type
from unittest import mock

import thor.http.error as httperr

from redbot.formatter.text import (
    BaseTextFormatter,
    TextListFormatter,
    VerboseTextListFormatter,
)
from redbot.resource import HttpResource
from redbot.resource.fetch import RedFetcher

EVIL = "a\x1b]52;c;ZXZpbA==\x07\x1b[2Jb"
EVIL_ESCAPED = "a\\x1b]52;c;ZXZpbA==\\x07\\x1b[2Jb"
BAD_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")

FORMATTERS: List[Type[BaseTextFormatter]] = [TextListFormatter, VerboseTextListFormatter]


def make_config() -> ConfigParser:
    conf = ConfigParser()
    conf.read_dict({"redbot": {"enable_local_access": "yes"}})
    return conf


def render(page: HttpResource, formatter_class: Type[BaseTextFormatter]) -> str:
    chunks: List[str] = []
    formatter = formatter_class(page.config, page, chunks.append, {"descend": True})
    formatter.bind_resource(page)
    formatter.finish_output()
    return "".join(chunks)


def make_page(*linked: HttpResource) -> HttpResource:
    page = HttpResource(make_config()["redbot"], descend=True)
    page.set_request("http://example.com/page")
    page.response.process_response_topline(b"1.1", b"200", b"OK")
    page.response.process_headers([(b"Content-Type", b"text/html")])
    page.response.complete = True
    for resource in linked:
        page.linked.append((resource, "img"))
    return page


def linked_resource(uri: str) -> HttpResource:
    resource = HttpResource(make_config()["redbot"], active_checks_enabled=False)
    resource.set_request(uri)
    return resource


def unsupported_resource() -> HttpResource:
    resource = linked_resource("ftp://example.com/x.png")
    resource.check()  # thor rejects the scheme without opening a connection
    return resource


def good_resource(uri: str) -> HttpResource:
    resource = linked_resource(uri)
    resource.response.process_response_topline(b"1.1", b"200", b"OK")
    resource.response.process_headers([(b"Content-Type", b"image/png")])
    resource.response.complete = True
    return resource


def unencodable_resource() -> HttpResource:
    resource = linked_resource("http://example.com/x.png")
    # httplint used to leave a non-ASCII password in the URI (mnot/httplint#200); set it directly
    # so this doesn't depend on its behaviour.
    resource.request.uri = "http://a:\u00e9@example.com/x.png"
    with mock.patch.object(RedFetcher.client, "exchange") as exchange:
        resource.check()
    exchange.assert_not_called()
    return resource


class TestLinkedFetchFailures(unittest.TestCase):
    def check(self, resource: HttpResource, expected: str) -> None:
        for formatter_class in FORMATTERS:
            with self.subTest(formatter=formatter_class.__name__):
                out = render(make_page(resource), formatter_class)
                self.assertNotIn("HTTP/ None", out)
                self.assertIn(f"{resource.request.uri}\n\n{expected}\n\n", out)

    def test_connection_refused(self) -> None:
        resource = linked_resource("http://127.0.0.1:1/refused.png")
        resource.fetch_error = httperr.ConnectError("Connection refused")
        self.check(resource, "Error: Connection error (Connection refused)")

    def test_unsupported_scheme(self) -> None:
        resource = unsupported_resource()
        self.assertIsInstance(resource.fetch_error, httperr.UrlError)
        self.check(resource, "Error: Unsupported or invalid URI (Unsupported URL scheme 'ftp')")

    def test_unencodable_uri(self) -> None:
        resource = unencodable_resource()
        self.check(
            resource, "Error: Unsupported or invalid URI (URI contains non-ASCII characters)"
        )

    def test_incomplete_response(self) -> None:
        resource = linked_resource("http://example.com/x.png")
        resource.response.process_response_topline(b"1.1", b"200", b"OK")
        resource.response.process_headers([(b"Content-Length", b"100")])
        resource.fetch_error = httperr.ConnectError("Server dropped connection")
        self.assertFalse(resource.response.complete)
        self.check(resource, "Error: Connection error (Server dropped connection)")

    def test_error_without_detail(self) -> None:
        resource = linked_resource("http://example.com/x.png")
        resource.fetch_error = httperr.ReadTimeoutError()
        self.check(resource, "Error: Read Timeout")

    def test_no_error_recorded(self) -> None:
        "Nothing is known about why it failed, so only the URI is shown."
        resource = linked_resource("http://example.com/x.png")
        for formatter_class in FORMATTERS:
            out = render(make_page(resource), formatter_class)
            self.assertNotIn("HTTP/ None", out)
            self.assertNotIn("Error:", out)
            self.assertIn("http://example.com/x.png\n", out)

    def test_other_links_unaffected(self) -> None:
        failed = unsupported_resource()
        good = good_resource("http://example.com/b.png")
        out = render(make_page(failed, good), TextListFormatter)
        self.assertIn("Error: Unsupported or invalid URI", out)
        self.assertIn(
            "http://example.com/b.png\n\nHTTP/1.1 200 OK\nContent-Type:image/png\n\n", out
        )

    def test_error_text_is_escaped(self) -> None:
        class EvilDescError(httperr.HttpError):
            desc = EVIL

        for error in (httperr.ConnectError(EVIL), EvilDescError(EVIL), EvilDescError(None)):
            resource = linked_resource("http://example.com/x.png")
            resource.fetch_error = error
            for formatter_class in FORMATTERS:
                with self.subTest(error=error, formatter=formatter_class.__name__):
                    out = render(make_page(resource), formatter_class)
                    self.assertIsNone(BAD_CHARS.search(out), repr(out))
                    self.assertIn(EVIL_ESCAPED, out)


class FakeServer(socketserver.ThreadingTCPServer):
    "Serves a page with several links that fail in different ways."

    allow_reuse_address = True
    daemon_threads = True

    class Handler(socketserver.BaseRequestHandler):
        def handle(self) -> None:
            path = self.request.recv(4096).split()[1]
            if path == b"/page":
                refused = self.server.refused_port  # type: ignore[attr-defined]
                body = (
                    "<html><head>"
                    f'<script src="http://127.0.0.1:{refused}/refused.js"></script>'
                    '<link rel="stylesheet" href="ftp://127.0.0.1/x.css">'
                    "</head><body>"
                    '<img src="/truncated.png">'
                    '<img src="/hostile.png">'
                    '<img src="/ok.png">'
                    "</body></html>"
                ).encode("utf-8")
                self.reply(b"text/html", body)
            elif path == b"/ok.png":
                self.reply(b"image/png", b"x")
            elif path == b"/truncated.png":
                self.request.sendall(
                    b"HTTP/1.1 200 OK\r\nContent-Type: image/png\r\nContent-Length: 100\r\n"
                    b"Connection: close\r\n\r\nabc"
                )
            else:
                self.request.sendall(b"HTTP/\x1b[2J\x07 200 OK\r\n\r\n")

        def reply(self, content_type: bytes, body: bytes) -> None:
            self.request.sendall(
                b"HTTP/1.1 200 OK\r\nContent-Type: %s\r\nContent-Length: %d\r\n"
                b"Connection: close\r\n\r\n%s" % (content_type, len(body), body)
            )

    def __init__(self) -> None:
        self.refused_port = unused_port()
        socketserver.ThreadingTCPServer.__init__(self, ("127.0.0.1", 0), self.Handler)
        threading.Thread(target=self.serve_forever, daemon=True).start()


def unused_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class TestCommandLine(unittest.TestCase):
    "redbot -a -o text reports failed links."

    server: FakeServer
    port: int

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = FakeServer()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def run_redbot(self, output_format: str) -> str:
        code = "from redbot.cli import main; main()"
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                code,
                "-a",
                "-o",
                output_format,
                f"http://127.0.0.1:{self.port}/page",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_failed_links(self) -> None:
        for output_format in ("text", "text_verbose"):
            with self.subTest(output_format):
                out = self.run_redbot(output_format)
                self.assertNotIn("HTTP/ None", out)
                for uri, error in [
                    (
                        f"http://127.0.0.1:{self.server.refused_port}/refused.js",
                        "Error: Connection error",
                    ),
                    ("ftp://127.0.0.1/x.css", "Error: Unsupported or invalid URI"),
                    (
                        f"http://127.0.0.1:{self.port}/truncated.png",
                        "Error: Connection error",
                    ),
                    (
                        f"http://127.0.0.1:{self.port}/hostile.png",
                        "Error: Unrecognised HTTP version",
                    ),
                ]:
                    self.assertIn(f"{uri}\n\n{error}", out)
                self.assertIn(f"http://127.0.0.1:{self.port}/ok.png\n\nHTTP/1.1 200 OK\n", out)
                self.assertIsNone(BAD_CHARS.search(out), repr(out))


if __name__ == "__main__":
    unittest.main()
