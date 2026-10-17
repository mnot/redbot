"""
A response with whitespace before a header field's colon finishes, with the error that says why,
rather than leaving the check (and the CLI) waiting forever (mnot/redbot#503).
"""

import socketserver
import subprocess
import sys
import threading
import unittest
from configparser import ConfigParser
from typing import Any, Dict

import thor
import thor.http.error as httperr

from redbot.resource import HttpResource
from redbot.resource.active_check.conneg import CONNEG_SUBREQ_PROBLEM
from redbot.resource.fetch import HEADER_NAME_SPACE, RedFetcher

TIMEOUT = 10  # seconds; a regression should fail the test, not hang it
SETTLE = 0.2  # seconds to keep running after the first check_done, to catch late repeats
HEAD = b"HTTP/1.1 200 OK\r\nConnection: close\r\n"
GOOD = HEAD + b"Content-Length: 1\r\n\r\nx"
BAD = HEAD + b"Content-Length : 1\r\n\r\nx"
TRAILER = HEAD + b"Transfer-Encoding: chunked\r\n\r\n1\r\nx\r\n0\r\nX-T : 1\r\n\r\n"
LONG_NAME = HEAD + b"%s : 1\r\n\r\nx" % (b"X" * 100_000)
PAGE = b'<html><body><img src="/bad"><img src="/good"></body></html>'


class Server(socketserver.ThreadingTCPServer):
    "Serves responses with whitespace before a colon, and a page linking to one."

    allow_reuse_address = True
    daemon_threads = True

    class Handler(socketserver.BaseRequestHandler):
        def handle(self) -> None:
            request = self.request.recv(65536)
            path = request.split()[1]
            if path == b"/page":
                response = (HEAD + b"Content-Type: text/html\r\nContent-Length: %d\r\n\r\n%s") % (
                    len(PAGE),
                    PAGE,
                )
            elif path == b"/good":
                response = GOOD
            elif path == b"/conneg":  # only the request with Accept-Encoding gets the bad one
                response = BAD if b"accept-encoding" in request.lower() else GOOD
            else:
                response = {b"/trailer": TRAILER, b"/long": LONG_NAME}.get(path, BAD)
            self.request.sendall(response)

    def __init__(self) -> None:
        socketserver.ThreadingTCPServer.__init__(self, ("127.0.0.1", 0), self.Handler)
        threading.Thread(target=self.serve_forever, daemon=True).start()
        self.port: int = self.server_address[1]


def space_notes(resource: RedFetcher) -> list[Any]:
    return [note for note in resource.response.notes if isinstance(note, HEADER_NAME_SPACE)]


class TestHeaderSpace(unittest.TestCase):
    "The real fetcher against a server that sends the response."

    def setUp(self) -> None:
        # The fetcher's HTTP client is shared by the whole process.
        self.saved_check_ip = RedFetcher.client.check_ip
        RedFetcher.client.check_ip = None
        self.server = Server()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        conf = ConfigParser()
        conf.read_dict({"redbot": {"enable_local_access": "yes"}})
        self.config = conf["redbot"]

    def tearDown(self) -> None:
        RedFetcher.client.check_ip = self.saved_check_ip

    def fetch(self, path: str, **kwargs: Any) -> HttpResource:
        "Check the resource, and assert that the check finishes, once."
        resource = HttpResource(self.config, **kwargs)
        resource.set_request(f"http://127.0.0.1:{self.server.port}{path}")
        seen: Dict[str, Any] = {"check_done": 0, "timed_out": False}

        @thor.events.on(resource)
        def check_done() -> None:
            seen["check_done"] += 1
            thor.schedule(SETTLE, thor.stop)

        def give_up() -> None:
            seen["timed_out"] = True
            thor.stop()

        timeout = thor.schedule(TIMEOUT, give_up)
        resource.check()
        thor.run()
        timeout.delete()
        self.assertFalse(seen["timed_out"], "check_done never fired")
        self.assertEqual(seen["check_done"], 1)
        return resource

    def assert_space_error(self, resource: HttpResource) -> None:
        "Finished, incomplete, with the note and the error saying why."
        self.assertTrue(resource.fetch_done)
        self.assertFalse(resource.response.complete)
        self.assertEqual(len(space_notes(resource)), 1)
        self.assertIsInstance(resource.fetch_error, httperr.HeaderSpaceError)

    def test_header_block(self) -> None:
        resource = self.fetch("/bad")
        self.assert_space_error(resource)
        self.assertIsNone(resource.response.status_code)  # thor errors before the status line

    def test_trailer(self) -> None:
        "Here the status line, headers and body have arrived by the time of the error."
        resource = self.fetch("/trailer")
        self.assert_space_error(resource)
        self.assertEqual(resource.response.status_code, 200)

    def test_linked_resource(self) -> None:
        resource = self.fetch("/page", descend=True)
        bad, good = [linked for linked, _tag in resource.linked]
        self.assert_space_error(bad)
        self.assertTrue(good.response.complete)
        self.assertEqual(space_notes(good), [])

    def test_active_check(self) -> None:
        "A subrequest that gets the response says what went wrong, not an empty problem."
        resource = self.fetch("/conneg")
        self.assertTrue(resource.response.complete)
        problems = [n for n in resource.response.notes if isinstance(n, CONNEG_SUBREQ_PROBLEM)]
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].vars["problem"], httperr.HeaderSpaceError.desc)

    def test_long_name_is_truncated(self) -> None:
        resource = self.fetch("/long")
        (note,) = space_notes(resource)
        self.assertLessEqual(len(str(note.vars["header_name"])), 40)
        self.assertLessEqual(len(note.subject), 40 + len("field-"))


class TestCommandLine(unittest.TestCase):
    "redbot exits, and says why, instead of waiting for a timeout that never comes."

    def test_exits_with_error(self) -> None:
        server = Server()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from redbot.cli import main; main()",
                    "-o",
                    "text",
                    f"http://127.0.0.1:{server.port}/bad",
                ],
                capture_output=True,
                text=True,
                timeout=TIMEOUT * 2,
                check=False,
            )
        except subprocess.TimeoutExpired:
            self.fail("redbot did not exit")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Error: Whitespace at the end of a header field-name", result.stdout)


if __name__ == "__main__":
    unittest.main()
