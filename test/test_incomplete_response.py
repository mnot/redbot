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
from html.parser import HTMLParser
from typing import Any, List, Optional, Tuple, Type

import thor.http.error as httperr

from redbot.formatter import Formatter
from redbot.formatter.html import SingleEntryHtmlFormatter, TableHtmlFormatter
from redbot.formatter.null_links import NullLinkGenerator
from redbot.formatter.text import TextFormatter, VerboseTextFormatter
from redbot.i18n import set_locale
from redbot.resource import HttpResource
from redbot.resource.fetch import BAD_CHUNK

CHUNKED = b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\nZZ\r\nx\r\n"
CHUNK_ERROR = "Chunked encoding error (ZZ)"
CHUNK_NOTE = "This response has chunked encoding errors."
HEADERS = "HTTP/1.1 200 OK\nTransfer-Encoding: chunked\nConnection: close\n"
DROPPED = "Server dropped connection before the response was complete."


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


class HarLinks(NullLinkGenerator):
    "Unlike the CLI's, this generates a HAR link."

    def har_link(self, *args: Any, **kw: Any) -> str:
        return "HARLINK"


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


def squash(markup: str) -> str:
    "The text of some markup, with whitespace collapsed."
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", markup)).strip()


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
        self.assertIn(CHUNK_ERROR, squash(out))
        self.assertIn(CHUNK_NOTE, out)
        self.assertRegex(out, r"response headers: [1-9]\d* bytes")
        self.assertNotIn("content:", out)  # only part of the body arrived

    def test_har(self) -> None:
        har = json.loads(run_redbot(f"{self.base}/", "-o", "har"))
        self.assertEqual(har["log"]["entries"], [])

    def test_truncated(self) -> None:
        out = run_redbot(f"{self.base}/truncated", "-o", "text")
        self.assertTrue(
            out.startswith(
                "HTTP/1.1 200 OK\nConnection: close\nContent-Length: 100\n\n"
                f"Error: Connection error ({DROPPED})\n"
            ),
            out,
        )
        out = run_redbot(f"{self.base}/truncated", "-o", "html")
        self.assertIn(f"Connection error ({DROPPED})", squash(out))

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
        rows = [squash(row) for row in re.findall(r"<tr class=\"droid\">(.*?)</tr>", out, re.S)]
        self.assertEqual(len(rows), 3)
        self.assertRegex(rows[1], r"^200 Chunked encoding error \d+ ")
        self.assertEqual(rows[2], "200 Connection error")
        self.assertIn(CHUNK_NOTE, out)


def make_resource(
    error: Optional[httperr.HttpError] = None,
    status: bool = True,
    complete: bool = False,
    note: bool = True,
) -> HttpResource:
    "A resource whose fetch is over; its body is complete only if asked."
    conf = ConfigParser()
    conf.read_dict({"redbot": {}})
    resource = HttpResource(conf["redbot"], active_checks_enabled=False)
    resource.set_request("http://example.com/x")
    if status:
        resource.response.process_response_topline(b"1.1", b"200", b"OK")
        resource.response.process_headers([(b"Content-Length", b"100")])
    if complete:
        resource.response.finish_content(True)
    if note:
        resource.response.notes.add("field-transfer-encoding", BAD_CHUNK, chunk_sample="ZZ")
    resource.fetch_error = error
    resource.response.start_time = resource.request.start_time = 1.0
    resource.response.finish_time = 2.0
    return resource


def render(formatter_class: Type[Formatter], resource: HttpResource, descend: bool = False) -> str:
    chunks: List[str] = []
    formatter = formatter_class(
        resource.config,
        resource,
        chunks.append,
        {"descend": descend, "nonce": "n", "link_generator": HarLinks()},
    )
    formatter.bind_resource(resource)
    with set_locale("en"):
        formatter.finish_output()
    return "".join(chunks)


class RowWidths(HTMLParser):
    "The width in columns of each table row, counting colspans."

    def __init__(self) -> None:
        HTMLParser.__init__(self)
        self.widths: List[int] = []
        self.row: Optional[int] = None

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag == "tr":
            self.row = 0
        elif tag in ("td", "th") and self.row is not None:
            self.row += int(dict(attrs).get("colspan") or 1)

    def handle_endtag(self, tag: str) -> None:
        if tag == "tr" and self.row is not None:
            self.widths.append(self.row)
            self.row = None


class TestFormatters(unittest.TestCase):
    "What's shown depends on whether there's a status line, not on whether the body finished."

    def test_text(self) -> None:
        for formatter_class in (TextFormatter, VerboseTextFormatter):
            with self.subTest(formatter=formatter_class.__name__):
                out = render(formatter_class, make_resource(httperr.ChunkError("ZZ")))
                self.assertTrue(
                    out.startswith(
                        "HTTP/1.1 200 OK\nContent-Length:100\n\n"
                        f"Error: {CHUNK_ERROR}\n* Connection:"
                    ),
                    out,
                )
                self.assertIn(CHUNK_NOTE, out)
                out = render(formatter_class, make_resource())  # nothing says why
                self.assertTrue(out.startswith("HTTP/1.1 200 OK\nContent-Length:100\n\n* Conn"))
                no_status = make_resource(httperr.ConnectError("refused"), False, note=False)
                self.assertEqual(
                    render(formatter_class, no_status), "Error: Connection error (refused)\n"
                )

    def test_html_page(self) -> None:
        resource = make_resource(httperr.ConnectError("dropped"))
        resource.response_header_length = 55
        out = render(SingleEntryHtmlFormatter, resource)
        self.assertIn("HTTP/1.1 200 OK", out)
        self.assertIn("Connection error (dropped)", squash(out))
        self.assertIn(CHUNK_NOTE, out)
        self.assertIn("response headers: 55 bytes", squash(out))
        for absent in ("content:", "transfer overhead", "HARLINK", "validate content"):
            self.assertNotIn(absent, out)
        complete = squash(render(SingleEntryHtmlFormatter, make_resource(complete=True)))
        self.assertIn("content: 0 bytes", complete)
        self.assertIn("HARLINK", complete)

    def test_html_error_is_escaped(self) -> None:
        evil = "<script>x</script>\x1b[2J\x07"
        for status in (True, False):
            with self.subTest(status=status):
                resource = make_resource(httperr.ConnectError(evil), status, note=False)
                out = render(SingleEntryHtmlFormatter, resource)
                self.assertIn("Connection error (&lt;script&gt;x&lt;/script&gt;", out)
                self.assertNotIn("<script>x", out)

    def test_html_no_status_line(self) -> None:
        resource = make_resource(httperr.ConnectError("refused"), status=False, note=False)
        out = render(SingleEntryHtmlFormatter, resource)
        self.assertIn("Connection error (refused)", out)
        self.assertNotIn("HTTP/1.1", out)
        self.assertNotIn("HARLINK", out)

    def test_table(self) -> None:
        "Every row is as wide as the header, however the response ended."
        for page_complete in (True, False):
            with self.subTest(page_complete=page_complete):
                page = make_resource(complete=page_complete, note=False)
                for link in (
                    make_resource(complete=True, note=False),
                    make_resource(httperr.ChunkError("ZZ")),
                    make_resource(httperr.ConnectError("refused"), False, note=False),
                ):
                    page.linked.append((link, "img"))
                out = render(TableHtmlFormatter, page, descend=True)
                rows = RowWidths()
                rows.feed(out)
                self.assertEqual(rows.widths, [12] * 6)  # a header and a page, a header and 3 links
                self.assertIn("Chunked encoding error", squash(out))
                self.assertIn(CHUNK_NOTE, out)
                self.assertNotIn("HTTP/ None", out)
                self.assertEqual("HARLINK" in out, page_complete)


class TestRecordedError(unittest.TestCase):
    "A chunk error ends the response, so it's recorded as the fetch error."

    @staticmethod
    def end_with(resource: HttpResource, error: httperr.HttpError) -> None:
        resource._response_error(error)  # pylint: disable=protected-access

    def test_chunk_errors(self) -> None:
        for error in (httperr.ChunkError("ZZ"), httperr.ChunkTerminatorError("xx")):
            with self.subTest(error=error):
                resource = make_resource(note=False)
                self.end_with(resource, error)
                self.assertIs(resource.fetch_error, error)
                self.assertTrue(resource.fetch_done)
                self.assertEqual(
                    [n.subject for n in resource.response.notes], ["field-transfer-encoding"]
                )

    def test_extra_data_is_not_an_error(self) -> None:
        resource = make_resource(complete=True, note=False)
        self.end_with(resource, httperr.ExtraDataError("junk"))
        self.assertIsNone(resource.fetch_error)


if __name__ == "__main__":
    unittest.main()
