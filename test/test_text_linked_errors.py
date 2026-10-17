"""
The text list formatter reports a failed fetch for a linked resource, rather than an empty
"HTTP/ None None" block (mnot/redbot#489).
"""

import socket
import socketserver
import subprocess
import sys
import threading
import unittest
from configparser import ConfigParser
from test.test_text_escape import BAD_CHARS, EVIL, EVIL_ESCAPED, render
from typing import Callable, List, Type

import thor.http.error as httperr

from redbot.formatter.text import (
    BaseTextFormatter,
    TextListFormatter,
    VerboseTextListFormatter,
)
from redbot.resource import HttpResource
from redbot.resource.fetch import BAD_CHUNK

FORMATTERS: List[Type[BaseTextFormatter]] = [TextListFormatter, VerboseTextListFormatter]


def linked_resource(uri: str, error: Callable[[HttpResource], None]) -> HttpResource:
    conf = ConfigParser()
    conf.read_dict({"redbot": {}})
    resource = HttpResource(conf["redbot"], active_checks_enabled=False)
    resource.set_request(uri)
    error(resource)
    return resource


def render_link(resource: HttpResource, formatter_class: Type[BaseTextFormatter]) -> str:
    page = HttpResource(resource.config, descend=True)
    page.response.process_response_topline(b"1.1", b"200", b"OK")
    page.response.complete = True
    page.linked.append((resource, "img"))
    return render(formatter_class, page)


def fail(error: httperr.HttpError) -> Callable[[HttpResource], None]:
    def set_error(resource: HttpResource) -> None:
        resource.fetch_error = error

    return set_error


def truncate(error: httperr.HttpError | None) -> Callable[[HttpResource], None]:
    "A response that has a status line and headers, but not all of its body."

    def set_error(resource: HttpResource) -> None:
        resource.response.process_response_topline(b"1.1", b"200", b"OK")
        resource.response.process_headers([(b"Content-Length", b"100")])
        resource.fetch_error = error

    return set_error


class TestLinkedFetchFailures(unittest.TestCase):
    def check(self, resource: HttpResource, expected: str) -> None:
        for formatter_class in FORMATTERS:
            with self.subTest(formatter=formatter_class.__name__):
                out = render_link(resource, formatter_class)
                self.assertNotIn("HTTP/ None", out)
                self.assertIn(f"{resource.request.uri}\n\n{expected}\n", out)

    def test_no_response(self) -> None:
        refused = httperr.ConnectError("Connection refused")
        self.check(
            linked_resource("http://127.0.0.1:1/x.png", fail(refused)),
            "Error: Connection error (Connection refused)",
        )
        self.check(
            linked_resource("http://example.com/x.png", fail(httperr.ReadTimeoutError())),
            "Error: Read Timeout",
        )

    def test_unsupported_scheme(self) -> None:
        resource = linked_resource("ftp://example.com/x.png", HttpResource.check)
        self.check(resource, "Error: Unsupported or invalid URI (Unsupported URL scheme 'ftp')")

    def test_unencodable_uri(self) -> None:
        def unencodable(resource: HttpResource) -> None:
            # Set directly, so this doesn't depend on how httplint treats a non-ASCII password.
            resource.request.uri = "http://a:\u00e9@example.com/x.png"
            resource.check()

        resource = linked_resource("http://example.com/x.png", unencodable)
        self.check(
            resource, "Error: Unsupported or invalid URI (URI contains non-ASCII characters)"
        )

    def test_no_error_recorded(self) -> None:
        out = render_link(
            linked_resource("http://example.com/x.png", lambda r: None), TextListFormatter
        )
        self.assertNotIn("HTTP/ None", out)
        self.assertNotIn("Error:", out)

    def test_incomplete_response(self) -> None:
        "An incomplete response with a status line shows it, then the error if there is one."
        failed = linked_resource(
            "http://example.com/x.png", truncate(httperr.ConnectError("Server dropped connection"))
        )
        for formatter_class in FORMATTERS:
            out = render_link(failed, formatter_class)
            self.assertIn(
                "HTTP/1.1 200 OK\nContent-Length:100\n\n"
                "Error: Connection error (Server dropped connection)\n",
                out,
            )
        quiet = linked_resource("http://example.com/x.png", truncate(None))
        quiet.response.notes.add("field-transfer-encoding", BAD_CHUNK, chunk_sample="ZZ")
        out = render_link(quiet, TextListFormatter)
        self.assertIn(
            "HTTP/1.1 200 OK\nContent-Length:100\n\n* Connection:\n  * This response has chunked",
            out,
        )
        self.assertNotIn("Error:", out)

    def test_hostile_text_is_escaped(self) -> None:
        class EvilDescError(httperr.HttpError):
            desc = EVIL

        for error in (httperr.ConnectError(EVIL), EvilDescError(EVIL), EvilDescError(None)):
            resource = linked_resource(f"http://example.com/{EVIL}", fail(error))
            for formatter_class in FORMATTERS:
                with self.subTest(error=error, formatter=formatter_class.__name__):
                    out = render_link(resource, formatter_class)
                    self.assertIsNone(BAD_CHARS.search(out), repr(out))
                    self.assertIn(f"http://example.com/{EVIL_ESCAPED}\n\nError: ", out)
                    self.assertGreaterEqual(out.count(EVIL_ESCAPED), 2)


class Server(socketserver.ThreadingTCPServer):
    "Serves a page with links that fail or misbehave in different ways."

    allow_reuse_address = True
    daemon_threads = True
    refused_port = 0

    class Handler(socketserver.BaseRequestHandler):
        def handle(self) -> None:
            path = self.request.recv(4096).split()[1]
            head = b"HTTP/1.1 200 OK\r\nConnection: close\r\n"
            if path == b"/page":
                body = (
                    f'<html><body><script src="http://127.0.0.1:{Server.refused_port}/x.js">'
                    '</script><link rel="stylesheet" href="ftp://127.0.0.1/x.css">'
                    '<img src="/truncated.png"><img src="/hostile.png"><img src="/chunked.png">'
                    '<img src="/early.png"><img src="/ok.png"></body></html>'
                ).encode()
                response = head + b"Content-Type: text/html\r\nContent-Length: %d\r\n\r\n%s" % (
                    len(body),
                    body,
                )
            elif path == b"/truncated.png":
                response = head + b"Content-Length: 100\r\n\r\nabc"
            elif path == b"/hostile.png":
                response = b"HTTP/\x1b[2J\x07 200 OK\r\n\r\n"
            elif path == b"/chunked.png":
                response = head + b"Transfer-Encoding: chunked\r\n\r\nZZ\r\nx\r\n"
            elif path == b"/early.png":
                response = (
                    b"HTTP/1.1 103 Early Hints\r\nLink: </a.css>; rel=preload\r\n\r\n"
                    + head
                    + b"Content-Length: 1\r\n\r\nx"
                )
            else:
                response = head + b"Content-Length: 1\r\n\r\nx"
            self.request.sendall(response)

    def __init__(self) -> None:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            Server.refused_port = sock.getsockname()[1]
        socketserver.ThreadingTCPServer.__init__(self, ("127.0.0.1", 0), self.Handler)
        threading.Thread(target=self.serve_forever, daemon=True).start()


class TestCommandLine(unittest.TestCase):
    "redbot -a reports failed links, and still shows what it did for the others."

    def run_redbot(self, port: int, output_format: str) -> str:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from redbot.cli import main; main()",
                "-a",
                "-o",
                output_format,
                f"http://127.0.0.1:{port}/page",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_links(self) -> None:
        server = Server()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        port = server.server_address[1]
        base = f"http://127.0.0.1:{port}"
        for output_format in ("text", "text_verbose"):
            with self.subTest(output_format):
                out = self.run_redbot(port, output_format)
                self.assertNotIn("HTTP/ None", out)
                self.assertIsNone(BAD_CHARS.search(out), repr(out))
                for uri, expected in [
                    (f"http://127.0.0.1:{Server.refused_port}/x.js", "Error: Connection error"),
                    ("ftp://127.0.0.1/x.css", "Error: Unsupported or invalid URI"),
                    (f"{base}/truncated.png", "HTTP/1.1 200 OK\nConnection: close\n"),
                    (
                        f"{base}/hostile.png",
                        "Error: Unrecognised HTTP version (HTTP/\\x1b[2J\\x07)",
                    ),
                    (f"{base}/chunked.png", "HTTP/1.1 200 OK\nConnection: close\n"),
                    (f"{base}/early.png", "HTTP/1.1 200 OK\n"),
                    (f"{base}/ok.png", "HTTP/1.1 200 OK\n"),
                ]:
                    self.assertIn(f"{uri}\n\n{expected}", out)
                self.assertIn("chunked encoding errors", out.split(f"{base}/chunked.png")[1])
                self.assertIn("Error: Connection error", out.split(f"{base}/truncated.png")[1])
                self.assertNotIn("103 Early Hints", out)


if __name__ == "__main__":
    unittest.main()
