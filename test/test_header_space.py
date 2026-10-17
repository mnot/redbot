"""
A response with whitespace before a header field's colon finishes, rather than leaving the check
(and the CLI) waiting forever (mnot/redbot#503).
"""

import socketserver
import subprocess
import sys
import threading
import unittest
from configparser import ConfigParser
from typing import Any, Dict, List
from unittest import mock

import thor
import thor.http.error as httperr

from redbot.resource import HttpResource
from redbot.resource.fetch import HEADER_NAME_SPACE, RedFetcher

TIMEOUT = 10  # seconds; a regression should fail the test, not hang it
SETTLE = 0.5  # seconds to keep running after the first check_done, to catch late repeats
BAD = b"HTTP/1.1 200 OK\r\nContent-Length : 1\r\nConnection: close\r\n\r\nx"
GOOD = b"HTTP/1.1 200 OK\r\nContent-Length: 1\r\nConnection: close\r\n\r\nx"
PAGE = b'<html><body><img src="/bad.png"><img src="/good.png"></body></html>'


def make_config() -> ConfigParser:
    conf = ConfigParser()
    conf.read_dict({"redbot": {"enable_local_access": "yes"}})
    return conf


class Server(socketserver.ThreadingTCPServer):
    "Answers /bad.png with a space before a header's colon, and /page with links to it."

    allow_reuse_address = True
    daemon_threads = True

    class Handler(socketserver.BaseRequestHandler):
        def handle(self) -> None:
            path = self.request.recv(4096).split()[1]
            if path == b"/page":
                response = (
                    b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n"
                    b"Content-Length: %d\r\n\r\n%s" % (len(PAGE), PAGE)
                )
            elif path == b"/good.png":
                response = GOOD
            else:
                response = BAD
            self.request.sendall(response)

    def __init__(self) -> None:
        socketserver.ThreadingTCPServer.__init__(self, ("127.0.0.1", 0), self.Handler)
        threading.Thread(target=self.serve_forever, daemon=True).start()
        self.port: int = self.server_address[1]


def has_space_note(resource: RedFetcher) -> bool:
    return any(isinstance(note, HEADER_NAME_SPACE) for note in resource.response.notes)


class TestResponseError(unittest.TestCase):
    "A fake exchange reports the error that thor does for this response."

    def setUp(self) -> None:
        self.config = make_config()["redbot"]
        self.log: List[str] = []

    def error(self, resource: HttpResource, err: httperr.HttpError) -> None:
        resource.on("fetch_done", lambda: self.log.append("fetch_done"))
        resource.on("check_done", lambda: self.log.append("check_done"))
        resource.set_request("http://example.com/")
        resource.exchange = mock.Mock()
        resource.exchange.conn = None
        # pylint: disable=protected-access
        resource._response_error(err)

    def test_header_space_finishes(self) -> None:
        resource = HttpResource(self.config)
        self.error(resource, httperr.HeaderSpaceError("Content-Length "))
        self.assertEqual(sorted(self.log), ["check_done", "fetch_done"])
        self.assertTrue(has_space_note(resource))
        self.assertTrue(resource.fetch_done)

    def test_linked_finishes(self) -> None:
        resource = HttpResource(self.config, active_checks_enabled=False)
        self.error(resource, httperr.HeaderSpaceError("Content-Length "))
        self.assertEqual(sorted(self.log), ["check_done", "fetch_done"])
        self.assertTrue(has_space_note(resource))

    def test_other_errors_finish(self) -> None:
        "Every kind of error ends the fetch, not just this one."
        for err in [
            httperr.ExtraDataError("x"),
            httperr.ChunkError("ZZ"),
            httperr.HeaderSpaceError(None),
            httperr.HeaderNoColonError("x"),
            httperr.HeaderNameError("empty field-name"),
            httperr.ConnectError("refused"),
            httperr.ReadTimeoutError(),
        ]:
            with self.subTest(error=repr(err)):
                self.log.clear()
                self.error(HttpResource(self.config), err)
                self.assertEqual(sorted(self.log), ["check_done", "fetch_done"])


class TestRealFetch(unittest.TestCase):
    "The real fetcher against a server that sends the response."

    def setUp(self) -> None:
        # The fetcher's HTTP client is shared by the whole process.
        self.saved_check_ip = RedFetcher.client.check_ip
        RedFetcher.client.check_ip = None
        self.server = Server()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.config = make_config()["redbot"]

    def tearDown(self) -> None:
        RedFetcher.client.check_ip = self.saved_check_ip

    def run_resource(self, resource: HttpResource) -> Dict[str, Any]:
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
        return seen

    def test_header_space(self) -> None:
        resource = HttpResource(self.config)
        resource.set_request(f"http://127.0.0.1:{self.server.port}/bad.png")
        seen = self.run_resource(resource)
        self.assertEqual(seen["check_done"], 1)
        self.assertTrue(resource.fetch_done)
        self.assertTrue(has_space_note(resource))

    def test_linked_resource(self) -> None:
        resource = HttpResource(self.config, descend=True)
        resource.set_request(f"http://127.0.0.1:{self.server.port}/page")
        seen = self.run_resource(resource)
        self.assertEqual(seen["check_done"], 1)
        bad, good = [linked for linked, _tag in resource.linked]
        self.assertTrue(bad.fetch_done)
        self.assertTrue(has_space_note(bad))
        self.assertTrue(good.response.complete)
        self.assertFalse(has_space_note(good))


class TestCommandLine(unittest.TestCase):
    "redbot exits for this response, instead of waiting for a timeout that never comes."

    def setUp(self) -> None:
        self.server = Server()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def run_redbot(self, path: str, *options: str) -> None:
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from redbot.cli import main; main()",
                    *options,
                    f"http://127.0.0.1:{self.server.port}{path}",
                ],
                capture_output=True,
                text=True,
                timeout=TIMEOUT * 3,
                check=False,
            )
        except subprocess.TimeoutExpired:
            self.fail("redbot did not exit")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_resource(self) -> None:
        self.run_redbot("/bad.png", "-o", "text")

    def test_linked_resource(self) -> None:
        self.run_redbot("/page", "-a", "-o", "text")


if __name__ == "__main__":
    unittest.main()
