#!/usr/bin/env python3

"""
Extra data after a response is attributed to the right request (mnot/redbot#518).
"""

import socket
import threading
import unittest
from test.test_descend import check_locally, make_config
from typing import List

from redbot.resource import HttpResource
from redbot.resource.active_check.conneg import CONNEG_SUBREQ_PROBLEM
from redbot.resource.fetch import EXTRA_DATA

KEEP_ALIVE = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nContent-Type: text/plain\r\n\r\nokJUNK"
CLOSE = (
    b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nContent-Type: text/plain\r\n"
    b"Connection: close\r\n\r\nokJUNK"
)


class JunkServer:
    "Answers every request with the same bytes, then waits for the client to close."

    def __init__(self, response: bytes) -> None:
        self.response = response
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
            threading.Thread(target=self.handle, args=(conn,), daemon=True).start()

    def handle(self, conn: socket.socket) -> None:
        try:
            while True:
                data = b""
                while b"\r\n\r\n" not in data:
                    more = conn.recv(65536)
                    if not more:
                        return
                    data += more
                conn.sendall(self.response)
        except OSError:
            pass
        finally:
            conn.close()


class TestExtraData(unittest.TestCase):
    def check(self, response: bytes, active: bool = True) -> HttpResource:
        server = JunkServer(response)
        self.addCleanup(server.close)
        resource = HttpResource(make_config()["redbot"], active_checks_enabled=active)
        resource.set_request(f"http://127.0.0.1:{server.port}/")
        self.assertTrue(check_locally(resource), "check_done didn't arrive")
        return resource

    @staticmethod
    def types(resource) -> List[type]:
        return [type(note) for note in resource.response.notes]

    def test_keep_alive_extra_data_is_not_blamed_on_the_conneg_check(self):
        resource = self.check(KEEP_ALIVE)
        self.assertNotIn(CONNEG_SUBREQ_PROBLEM, self.types(resource))
        self.assertNotIn(EXTRA_DATA, self.types(resource.subreqs["conneg"]))
        self.assertTrue(resource.subreqs["conneg"].response.complete)

    def test_extra_data_after_a_closing_response_is_reported_by_check_done(self):
        resource = self.check(CLOSE)
        self.assertIn(EXTRA_DATA, self.types(resource))

    @unittest.expectedFailure
    def test_keep_alive_extra_data_is_reported(self):
        # thor 0.17.0 drops data that follows a keep-alive response in the same read without
        # raising an error (0.16.1 did not report it either), so there is nothing to record.
        resource = self.check(KEEP_ALIVE, active=False)
        self.assertIn(EXTRA_DATA, self.types(resource))


if __name__ == "__main__":
    unittest.main()
