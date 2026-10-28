#!/usr/bin/env python3

"""
Interim (1xx) responses from a retried request are listed once, not once per attempt
(mnot/redbot#513).
"""

import socket
import threading
import unittest
from configparser import ConfigParser
from test.test_descend import check_locally, make_config
from types import SimpleNamespace
from typing import Callable, List, Optional

from redbot.resource import HttpResource
from redbot.resource.fetch import ONE_XX_BAD_HEADER, RedFetcher

EARLY_HINTS = b"HTTP/1.1 103 Early Hints\r\nLink: </x>; rel=preload\r\n\r\n"
BAD_EARLY_HINTS = b"HTTP/1.1 103 Early Hints\r\nContent-Length: 5\r\n\r\n"
CONTINUE = b"HTTP/1.1 100 Continue\r\n\r\n"
OK = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nContent-Type: text/plain\r\n\r\nok"


class ScriptedServer:
    "Answers the nth connection with script(n), then closes it."

    def __init__(self, script: Callable[[int], bytes]) -> None:
        self.script = script
        self.connections = 0
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(10)
        self.port = self.sock.getsockname()[1]
        threading.Thread(target=self.serve, daemon=True).start()

    def close(self) -> None:
        self.sock.close()

    def serve(self) -> None:
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            self.connections += 1
            threading.Thread(
                target=self.handle, args=(conn, self.connections), daemon=True
            ).start()

    def handle(self, conn: socket.socket, number: int) -> None:
        try:
            data = b""
            while b"\r\n\r\n" not in data:
                more = conn.recv(65536)
                if not more:
                    return
                data += more
            conn.sendall(self.script(number))
        except OSError:
            pass
        finally:
            conn.close()


class TestRetriedNonfinal(unittest.TestCase):
    def setUp(self) -> None:
        self.retry_delay = RedFetcher.client.retry_delay
        RedFetcher.client.retry_delay = 0.01

    def tearDown(self) -> None:
        RedFetcher.client.retry_delay = self.retry_delay

    def check(self, script: Callable[[int], bytes]) -> HttpResource:
        server = ScriptedServer(script)
        self.addCleanup(server.close)
        resource = HttpResource(make_config()["redbot"], active_checks_enabled=False)
        resource.set_request(f"http://127.0.0.1:{server.port}/")
        self.assertTrue(check_locally(resource), "check_done didn't arrive")
        return resource

    @staticmethod
    def statuses(resource: HttpResource) -> List[Optional[int]]:
        return [r.status_code for r in resource.nonfinal_responses]

    def test_retry_lists_the_interim_response_once(self) -> None:
        resource = self.check(lambda n: EARLY_HINTS if n == 1 else EARLY_HINTS + OK)
        self.assertEqual(self.statuses(resource), [103])
        self.assertEqual(resource.response.status_code, 200)

    def test_retry_that_sends_no_interim_response_lists_none(self) -> None:
        resource = self.check(lambda n: EARLY_HINTS if n == 1 else OK)
        self.assertEqual(self.statuses(resource), [])
        self.assertEqual(resource.response.status_code, 200)

    def test_failed_retries_list_the_last_attempt_only(self) -> None:
        resource = self.check(lambda n: CONTINUE)
        self.assertEqual(self.statuses(resource), [100])
        self.assertIsNotNone(resource.fetch_error)

    def test_failed_retries_that_end_without_one_list_none(self) -> None:
        resource = self.check(lambda n: CONTINUE if n == 1 else b"")
        self.assertEqual(self.statuses(resource), [])
        self.assertIsNotNone(resource.fetch_error)

    def test_notes_are_not_repeated_per_attempt(self) -> None:
        resource = self.check(lambda n: BAD_EARLY_HINTS if n == 1 else BAD_EARLY_HINTS + OK)
        bad = [n for n in resource.response.notes if isinstance(n, ONE_XX_BAD_HEADER)]
        self.assertEqual(len(bad), 1)

    def test_notes_from_a_dropped_attempt_are_removed(self) -> None:
        resource = self.check(lambda n: BAD_EARLY_HINTS if n == 1 else OK)
        self.assertFalse([n for n in resource.response.notes if isinstance(n, ONE_XX_BAD_HEADER)])


class TestForgetStale(unittest.TestCase):
    "The bookkeeping, without a network."

    def resource(self) -> HttpResource:
        conf = ConfigParser()
        conf.add_section("redbot")
        return HttpResource(conf["redbot"])

    @staticmethod
    def arrive(resource: HttpResource, conn: object, data: bytes = BAD_EARLY_HINTS) -> None:
        resource.exchange = SimpleNamespace(res_version=b"1.1", conn=conn)  # type: ignore
        resource._response_nonfinal(b"103", b"Early Hints", [(b"Content-Length", b"5")])

    def test_same_connection_keeps_what_it_sent(self) -> None:
        resource = self.resource()
        conn = object()
        self.arrive(resource, conn)
        self.arrive(resource, conn)
        self.assertEqual(len(resource.nonfinal_responses), 2)

    def test_new_connection_starts_again(self) -> None:
        resource = self.resource()
        self.arrive(resource, object())
        self.arrive(resource, object())
        self.assertEqual(len(resource.nonfinal_responses), 1)
        bad = [n for n in resource.response.notes if isinstance(n, ONE_XX_BAD_HEADER)]
        self.assertEqual(len(bad), 1)

    def test_reset_keeps_other_notes(self) -> None:
        resource = self.resource()
        other = resource.response.notes.add("body", ONE_XX_BAD_HEADER, response="x", header_name="y")
        self.arrive(resource, object())
        resource._reset_nonfinal()
        self.assertEqual([n for n in resource.response.notes], [other])
        self.assertEqual(resource.nonfinal_responses, [])


if __name__ == "__main__":
    unittest.main()
