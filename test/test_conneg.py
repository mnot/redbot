#!/usr/bin/env python3

"""
The content negotiation check copes with servers that compress whether or not they're asked to
(mnot/redbot#521).
"""

import gzip
import socket
import threading
import unittest
from test.test_descend import check_locally, make_config
from typing import List

from redbot.resource import HttpResource
from redbot.resource.active_check.conneg import (
    CONNEG_GZIP_GOOD,
    CONNEG_UNCONDITIONAL_GZIP,
    VARY_BODY_MISMATCH,
    VARY_ETAG_DOESNT_CHANGE,
)

BODY = b"hello, world. " * 200


class GzipServer:
    "Serves BODY with a strong ETag, gzipped always or only when the client asks."

    def __init__(self, always: bool, bare_coding: bytes = b"") -> None:
        self.always = always
        self.bare_coding = bare_coding
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
        data = b""
        while b"\r\n\r\n" not in data:
            more = conn.recv(65536)
            if not more:
                conn.close()
                return
            data += more
        compress = self.always or b"accept-encoding: gzip" in data.lower()
        body = gzip.compress(BODY, mtime=0) if compress else BODY
        head = b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nETag: "abc"\r\n'
        if compress:
            head += b"Content-Encoding: gzip\r\n"
        else:
            head += self.bare_coding
        if not self.always:
            head += b"Vary: Accept-Encoding\r\n"
        conn.sendall(head + b"Connection: close\r\nContent-Length: %d\r\n\r\n" % len(body) + body)
        conn.close()


class TestConnegCheck(unittest.TestCase):
    def note_types(self, always: bool) -> List[type]:
        server = GzipServer(always)
        self.addCleanup(server.close)
        resource = HttpResource(make_config()["redbot"])
        resource.set_request(f"http://127.0.0.1:{server.port}/")
        self.assertTrue(check_locally(resource), "check_done didn't arrive")
        return [type(note) for note in resource.response.notes]

    def test_negotiating_server(self):
        types = self.note_types(always=False)
        self.assertIn(CONNEG_GZIP_GOOD, types)
        self.assertNotIn(CONNEG_UNCONDITIONAL_GZIP, types)

    def test_identity_coding_is_not_compression(self):
        server = GzipServer(always=False, bare_coding=b"Content-Encoding: identity\r\n")
        self.addCleanup(server.close)
        resource = HttpResource(make_config()["redbot"])
        resource.set_request(f"http://127.0.0.1:{server.port}/")
        self.assertTrue(check_locally(resource), "check_done didn't arrive")
        types = [type(note) for note in resource.response.notes]
        self.assertNotIn(CONNEG_UNCONDITIONAL_GZIP, types)
        self.assertIn(CONNEG_GZIP_GOOD, types)

    def test_server_that_always_compresses(self):
        types = self.note_types(always=True)
        self.assertIn(CONNEG_UNCONDITIONAL_GZIP, types)
        self.assertNotIn(VARY_ETAG_DOESNT_CHANGE, types)
        self.assertNotIn(VARY_BODY_MISMATCH, types)
        self.assertNotIn(CONNEG_GZIP_GOOD, types)


if __name__ == "__main__":
    unittest.main()
