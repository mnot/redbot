"""
A response whose headers arrived but whose body didn't complete is still shown, with the error
that stopped it (mnot/redbot#502).
"""

import json
import re
import socketserver
import subprocess
import sys
import threading
import unittest
from configparser import ConfigParser
from typing import List, Optional, Type

import thor.http.error as httperr

from redbot.formatter import Formatter
from redbot.formatter.har import HarFormatter
from redbot.formatter.html import SingleEntryHtmlFormatter, TableHtmlFormatter
from redbot.formatter.text import (
    TextFormatter,
    TextListFormatter,
    VerboseTextFormatter,
    VerboseTextListFormatter,
)
from redbot.i18n import set_locale
from redbot.resource import HttpResource
from redbot.resource.fetch import BAD_CHUNK

CHUNKED = b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\nZZ\r\nx\r\n"
CHUNK_ERROR = "Chunked encoding error (ZZ)"
CHUNK_NOTE = "This response has chunked encoding errors."
HEADERS = "HTTP/1.1 200 OK\nTransfer-Encoding: chunked\nConnection: close\n"


class Server(socketserver.ThreadingTCPServer):
    "Serves a bad chunked response, a truncated one, and a page linking to them."

    allow_reuse_address = True
    daemon_threads = True

    class Handler(socketserver.BaseRequestHandler):
        def handle(self) -> None:
            path = self.request.recv(4096).split()[1]
            head = b"HTTP/1.1 200 OK\r\nConnection: close\r\n"
            if path == b"/page":
                body = (
                    b'<html><body><img src="/chunked.png"><img src="/truncated.png">'
                    b"</body></html>"
                )
                response = head + b"Content-Type: text/html\r\nContent-Length: %d\r\n\r\n%s" % (
                    len(body),
                    body,
                )
            elif path.startswith(b"/truncated"):
                response = head + b"Content-Length: 100\r\n\r\nabc"
            else:
                response = CHUNKED
            self.request.sendall(response)

    def __init__(self) -> None:
        socketserver.ThreadingTCPServer.__init__(self, ("127.0.0.1", 0), self.Handler)
        threading.Thread(target=self.serve_forever, daemon=True).start()


def run_redbot(url: str, *args: str) -> str:
    result = subprocess.run(
        [sys.executable, "-c", "from redbot.cli import main; main()", *args, url],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


class TestCommandLine(unittest.TestCase):
    base: str

    @classmethod
    def setUpClass(cls) -> None:
        server = Server()
        cls.addClassCleanup(server.server_close)
        cls.addClassCleanup(server.shutdown)
        cls.base = f"http://127.0.0.1:{server.server_address[1]}"

    def test_text(self) -> None:
        for output_format in ("text", "text_verbose"):
            with self.subTest(output_format):
                out = run_redbot(f"{self.base}/", "-o", output_format)
                self.assertTrue(out.startswith(f"{HEADERS}\nError: {CHUNK_ERROR}\n"), out)
                self.assertIn(CHUNK_NOTE, out)

    def test_html(self) -> None:
        out = run_redbot(f"{self.base}/", "-o", "html")
        self.assertIn("HTTP/1.1 200 OK", out)
        self.assertIn("<p class='error'>\n            Chunked encoding error\n", out)
        self.assertIn(CHUNK_NOTE, out)
        self.assertNotIn("view HAR", out)  # there'd be no entry in it

    def test_har(self) -> None:
        har = json.loads(run_redbot(f"{self.base}/", "-o", "har"))
        self.assertEqual(har["log"]["entries"], [])

    def test_truncated(self) -> None:
        out = run_redbot(f"{self.base}/truncated", "-o", "text")
        self.assertTrue(
            out.startswith(
                "HTTP/1.1 200 OK\nConnection: close\nContent-Length: 100\n\n"
                "Error: Connection error (Server dropped connection before the response was "
                "complete.)\n"
            ),
            out,
        )

    def test_linked_text(self) -> None:
        for output_format in ("text", "text_verbose"):
            with self.subTest(output_format):
                out = run_redbot(f"{self.base}/page", "-a", "-o", output_format)
                chunked = out.split(f"{self.base}/chunked.png")[1].split(f"{self.base}/trunc")[0]
                self.assertTrue(
                    chunked.startswith(f"\n\n{HEADERS}\nError: {CHUNK_ERROR}\n"), chunked
                )
                self.assertIn(CHUNK_NOTE, chunked)

    def test_linked_html(self) -> None:
        out = run_redbot(f"{self.base}/page", "-a", "-o", "html")
        rows = re.findall(r"<tr class=\"droid\">(.*?)</tr>", out, re.S)
        text = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", row)).strip() for row in rows]
        self.assertEqual(len(text), 3)
        self.assertRegex(text[1], r"^200 Chunked encoding error \d+ ")
        self.assertEqual(text[2], "200 Connection error")
        self.assertIn(CHUNK_NOTE, out)


def incomplete_resource(
    error: Optional[httperr.HttpError], status: bool = True, note: bool = True
) -> HttpResource:
    conf = ConfigParser()
    conf.read_dict({"redbot": {}})
    resource = HttpResource(conf["redbot"], active_checks_enabled=False)
    resource.set_request("http://example.com/x")
    if status:
        resource.response.process_response_topline(b"1.1", b"200", b"OK")
        resource.response.process_headers([(b"Content-Length", b"100")])
    if note:
        resource.response.notes.add("field-transfer-encoding", BAD_CHUNK, chunk_sample="ZZ")
    resource.fetch_error = error
    resource.response.start_time = resource.request.start_time = 1.0
    resource.response.finish_time = 2.0
    return resource


def render(formatter_class: Type[Formatter], resource: HttpResource, descend: bool = False) -> str:
    chunks: List[str] = []
    formatter = formatter_class(
        resource.config, resource, chunks.append, {"descend": descend, "nonce": "n"}
    )
    formatter.bind_resource(resource)
    with set_locale("en"):
        formatter.finish_output()
    return "".join(chunks)


class TestFormatterDecision(unittest.TestCase):
    "What's shown depends on whether there's a status line, not on whether the body finished."

    text_formatters = [TextFormatter, VerboseTextFormatter]

    def test_text_no_error(self) -> None:
        for formatter_class in self.text_formatters:
            out = render(formatter_class, incomplete_resource(None))
            self.assertTrue(out.startswith("HTTP/1.1 200 OK\nContent-Length:100\n\n* Connection:"))
            self.assertNotIn("Error:", out)

    def test_text_with_error(self) -> None:
        error = httperr.ChunkError("ZZ")
        for formatter_class in self.text_formatters:
            out = render(formatter_class, incomplete_resource(error))
            self.assertTrue(
                out.startswith(
                    f"HTTP/1.1 200 OK\nContent-Length:100\n\nError: {CHUNK_ERROR}\n* Connection:"
                ),
                out,
            )
            self.assertIn(CHUNK_NOTE, out)

    def test_text_no_status_line(self) -> None:
        error = httperr.ConnectError("refused")
        for formatter_class in self.text_formatters:
            out = render(formatter_class, incomplete_resource(error, status=False, note=False))
            self.assertEqual(out, "Error: Connection error (refused)\n")
        for formatter_class in self.text_formatters:
            self.assertEqual(
                render(formatter_class, incomplete_resource(None, status=False, note=False)), ""
            )

    def test_text_list_matches_page(self) -> None:
        "A link is shown the same way as the page itself."
        for page_class, list_class in [
            (TextFormatter, TextListFormatter),
            (VerboseTextFormatter, VerboseTextListFormatter),
        ]:
            for error in (None, httperr.ChunkError("ZZ")):
                resource = incomplete_resource(error)
                page = HttpResource(resource.config, descend=True)
                page.response.process_response_topline(b"1.1", b"200", b"OK")
                page.response.complete = True
                page.linked.append((resource, "img"))
                linked = render(list_class, page, descend=True)
                self.assertIn(
                    f"http://example.com/x\n\n{render(page_class, resource).rstrip()}", linked
                )

    def test_html(self) -> None:
        resource = incomplete_resource(httperr.ChunkError("ZZ"))
        out = render(SingleEntryHtmlFormatter, resource)
        self.assertIn("HTTP/1.1 200 OK", out)
        self.assertIn("Chunked encoding error", out)
        self.assertIn(CHUNK_NOTE, out)
        self.assertNotIn("view HAR", out)
        self.assertNotIn("validate content", out)

    def test_html_no_status_line(self) -> None:
        out = render(
            SingleEntryHtmlFormatter, incomplete_resource(httperr.ConnectError("refused"), False)
        )
        self.assertIn("Connection error (refused)", out)
        self.assertNotIn("HTTP/1.1", out)
        self.assertNotIn("view HAR", out)

    def test_html_table_rows(self) -> None:
        page = HttpResource(incomplete_resource(None).config, descend=True)
        page.set_request("http://example.com/")
        page.response.process_response_topline(b"1.1", b"200", b"OK")
        page.response.finish_content(True)
        page.linked.append((incomplete_resource(httperr.ChunkError("ZZ")), "img"))
        page.linked.append(
            (incomplete_resource(httperr.ConnectError("refused"), status=False, note=False), "img")
        )
        out = render(TableHtmlFormatter, page, descend=True)
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", out))
        self.assertIn("200 Chunked encoding error", text)
        self.assertIn("Connection error", text)
        self.assertNotIn("HTTP/ None", text)
        self.assertIn(CHUNK_NOTE, out)

    def test_har_skips_incomplete(self) -> None:
        out = render(HarFormatter, incomplete_resource(httperr.ChunkError("ZZ")))
        self.assertEqual(json.loads(out)["log"]["entries"], [])


class TestRecordedError(unittest.TestCase):
    "Every way a response can end up incomplete leaves a fetch error saying why."

    def fetch(self, error: httperr.HttpError, status: bool = True) -> HttpResource:
        resource = incomplete_resource(None, status=status, note=False)
        resource._response_error(error)  # pylint: disable=protected-access
        return resource

    def test_chunk_errors(self) -> None:
        for error in (httperr.ChunkError("ZZ"), httperr.ChunkTerminatorError("xx")):
            with self.subTest(error=error):
                resource = self.fetch(error)
                self.assertIs(resource.fetch_error, error)
                self.assertTrue(resource.fetch_done)
                self.assertEqual(
                    [n.subject for n in resource.response.notes], ["field-transfer-encoding"]
                )

    def test_extra_data_is_not_an_error(self) -> None:
        resource = incomplete_resource(None, note=False)
        resource.response.complete = True
        resource._response_error(httperr.ExtraDataError("junk"))  # pylint: disable=protected-access
        self.assertIsNone(resource.fetch_error)

    def test_other_errors(self) -> None:
        for error in (httperr.ConnectError("dropped"), httperr.HeaderNameError("x")):
            with self.subTest(error=error):
                self.assertIs(self.fetch(error).fetch_error, error)


if __name__ == "__main__":
    unittest.main()
