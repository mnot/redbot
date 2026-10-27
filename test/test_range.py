#!/usr/bin/env python3

"""
The partial content check asks for the right bytes and doesn't misreport correct servers
(mnot/redbot#517).
"""

import re
import socket
import threading
import time
import unittest
from test.test_descend import check_locally, make_config
from typing import List, Optional, Tuple

from redbot.resource import HttpResource
from redbot.resource.active_check.range import RANGE_CL_FULL, RANGE_CORRECT, RANGE_INCORRECT

BODY = bytes(range(33, 127)) * 11  # 1034 bytes of printable ASCII


class RangeServer:
    """
    A server that handles Range correctly. Full responses are sent either with Content-Length or
    as separate HTTP chunks, each in its own write so the client sees them as separate reads.
    """

    def __init__(self, body: bytes, chunk_size: Optional[int], corrupt_ranges: bool = False):
        self.body = body
        self.chunk_size = chunk_size
        self.corrupt_ranges = corrupt_ranges
        self.ranges: List[str] = []
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
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        data = b""
        while b"\r\n\r\n" not in data:
            more = conn.recv(65536)
            if not more:
                conn.close()
                return
            data += more
        match = re.search(rb"(?im)^range:\s*bytes=(\d+)-(\d+)\s*$", data)
        head = (
            b'Content-Type: text/plain\r\nETag: "abc"\r\nAccept-Ranges: bytes\r\n'
            b"Cache-Control: max-age=60\r\nConnection: close\r\n"
        )
        if match:
            start, end = int(match.group(1)), min(int(match.group(2)), len(self.body) - 1)
            self.ranges.append(f"{start}-{end}")
            part = self.body[start : end + 1]
            if self.corrupt_ranges:
                part = part[::-1]
            conn.sendall(
                b"HTTP/1.1 206 Partial Content\r\n"
                + head
                + b"Content-Range: bytes %d-%d/%d\r\nContent-Length: %d\r\n\r\n"
                % (start, end, len(self.body), len(part))
                + part
            )
        elif self.chunk_size:
            conn.sendall(b"HTTP/1.1 200 OK\r\n" + head + b"Transfer-Encoding: chunked\r\n\r\n")
            for i in range(0, len(self.body), self.chunk_size):
                chunk = self.body[i : i + self.chunk_size]
                conn.sendall(b"%x\r\n%s\r\n" % (len(chunk), chunk))
                time.sleep(0.02)
            conn.sendall(b"0\r\n\r\n")
        else:
            conn.sendall(
                b"HTTP/1.1 200 OK\r\n"
                + head
                + b"Content-Length: %d\r\n\r\n" % len(self.body)
                + self.body
            )
        conn.close()


class TestRangeCheck(unittest.TestCase):
    def check(
        self, body: bytes, chunk_size: Optional[int], corrupt_ranges: bool = False
    ) -> Tuple[HttpResource, RangeServer]:
        server = RangeServer(body, chunk_size, corrupt_ranges)
        self.addCleanup(server.close)
        resource = HttpResource(make_config()["redbot"])
        resource.set_request(f"http://127.0.0.1:{server.port}/")
        self.assertTrue(check_locally(resource), "check_done didn't arrive")
        self.assertTrue(server.ranges, "no ranged request was made")
        return resource, server

    @staticmethod
    def note_types(resource: HttpResource) -> List[type]:
        return [type(note) for note in resource.response.notes]

    def assert_correct(self, body: bytes, chunk_size: Optional[int]) -> RangeServer:
        resource, server = self.check(body, chunk_size)
        types = self.note_types(resource)
        self.assertIn(RANGE_CORRECT, types)
        self.assertNotIn(RANGE_INCORRECT, types)
        self.assertNotIn(RANGE_CL_FULL, types)
        self.assertTrue(resource.partial_support)
        return server

    def test_large_chunk(self):
        server = self.assert_correct(BODY, None)
        start, end = (int(n) for n in server.ranges[0].split("-"))
        self.assertEqual(end - start + 1, 96)

    def test_small_chunks(self):
        server = self.assert_correct(BODY, 50)
        start, end = (int(n) for n in server.ranges[0].split("-"))
        self.assertEqual((start % 50, end - start + 1), (0, 50))

    def test_body_shorter_than_the_range(self):
        server = self.assert_correct(BODY[:60], None)
        self.assertEqual(server.ranges, ["0-59"])

    def test_wrong_bytes_are_still_flagged(self):
        resource, _ = self.check(BODY, None, corrupt_ranges=True)
        self.assertIn(RANGE_INCORRECT, self.note_types(resource))
        self.assertFalse(resource.partial_support)


if __name__ == "__main__":
    unittest.main()
