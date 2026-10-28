#!/usr/bin/env python3

"""
The signed Web Bot Auth retry abandons the challenged connection rather than leaving it half-closed
in thor's pool (mnot/redbot#529).
"""

import os
import socket
import tempfile
import threading
import time
import unittest
from configparser import ConfigParser
from test.test_descend import check_locally
from test.test_webbotauth import AGENT, RFC9421_ED25519_KEY
from typing import List

import thor

from redbot.resource import HttpResource
from redbot.resource.fetch import ONE_XX_BAD_HEADER, RedFetcher

CHALLENGE_BODY = b"x" * 400


class ChallengeServer:
    """
    Answers an unsigned request with a 401 challenge whose body stalls half way, and a signed one
    with a 200. After REDbot closes the challenged connection, the rest of the body follows.
    """

    def __init__(self) -> None:
        self.requests: List[bool] = []  # whether each request was signed
        self.connections = 0
        self.challenge_closed = threading.Event()
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
                signed = b"signature-input:" in data.lower()
                self.requests.append(signed)
                if signed:
                    conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
                    continue
                half = len(CHALLENGE_BODY) // 2
                conn.sendall(
                    b"HTTP/1.1 401 Unauthorized\r\nContent-Length: %d\r\n" % len(CHALLENGE_BODY)
                    + b'Accept-Signature: sig1=("@authority");tag="web-bot-auth"\r\n\r\n'
                    + CHALLENGE_BODY[:half]
                )
                try:
                    while conn.recv(65536):
                        pass  # until REDbot closes its end
                except OSError:
                    pass
                self.challenge_closed.set()
                time.sleep(0.2)
                try:
                    conn.sendall(CHALLENGE_BODY[half:])
                except OSError:
                    pass
                return
        finally:
            conn.close()


class InterimChallengeServer(ChallengeServer):
    "Sends a 103 with a header it shouldn't have before the challenge, and none before the 200."

    def handle(self, conn: socket.socket) -> None:
        try:
            data = b""
            while b"\r\n\r\n" not in data:
                more = conn.recv(65536)
                if not more:
                    return
                data += more
            if b"signature-input:" in data.lower():
                conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
            else:
                conn.sendall(
                    b"HTTP/1.1 103 Early Hints\r\nContent-Length: 5\r\n\r\n"
                    b"HTTP/1.1 401 Unauthorized\r\nContent-Length: 0\r\n"
                    b'Accept-Signature: sig1=("@authority");tag="web-bot-auth"\r\n\r\n'
                )
        except OSError:
            pass
        finally:
            conn.close()


class ChallengeCase(unittest.TestCase):
    def make_server(self) -> ChallengeServer:
        return ChallengeServer()

    def setUp(self):
        fd, key_path = tempfile.mkstemp(suffix=".pem")
        with os.fdopen(fd, "wb") as fh:
            fh.write(RFC9421_ED25519_KEY)
        self.addCleanup(os.unlink, key_path)
        parser = ConfigParser()
        parser.read_dict(
            {
                "redbot": {
                    "enable_local_access": "True",
                    "web_bot_auth_key": key_path,
                    "web_bot_auth_directory": AGENT,
                }
            }
        )
        self.config = parser["redbot"]
        self.server = self.make_server()
        self.addCleanup(self.server.close)

    def resource(self) -> HttpResource:
        resource = HttpResource(self.config, active_checks_enabled=False)
        resource.set_request(f"http://127.0.0.1:{self.server.port}/")
        return resource

    def fetch(self) -> HttpResource:
        resource = self.resource()
        self.assertTrue(check_locally(resource), "check_done didn't arrive")
        return resource


class TestChallengeConnection(ChallengeCase):
    def test_challenged_connection_is_abandoned(self):
        resource = self.fetch()
        self.assertEqual(resource.response.status_code, 200)
        self.assertEqual(self.server.requests, [False, True])
        self.assertTrue(
            self.server.challenge_closed.wait(2), "the challenged connection stayed open"
        )
        self.assertEqual(resource.transfer_in, 2)  # the challenge's bytes aren't counted

    def test_next_fetch_does_not_reuse_the_challenged_connection(self):
        first, second = (self.resource() for _ in range(2))
        started: List[float] = []
        finished: List[float] = []

        def start_second() -> None:
            started.append(time.time())
            second.check()  # the rest of the challenge body has arrived by now

        first.on("check_done", lambda: thor.schedule(0.7, start_second))

        def second_done() -> None:
            finished.append(time.time())
            thor.stop()

        second.on("check_done", second_done)
        saved_check_ip = RedFetcher.client.check_ip
        RedFetcher.client.check_ip = None
        try:
            timer = thor.schedule(10, thor.stop)
            first.check()
            thor.run()
            timer.delete()
        finally:
            RedFetcher.client.check_ip = saved_check_ip
        self.assertTrue(finished, "the second fetch never finished")
        self.assertEqual(second.response.status_code, 200)
        self.assertLess(finished[0] - started[0], 1, "the fetch waited on a bad connection")
        # the second fetch is unsigned first, so it is challenged again, then signed
        self.assertEqual(self.server.requests[2:], [False, True])


class TestChallengeInterimResponses(ChallengeCase):
    def make_server(self) -> ChallengeServer:
        return InterimChallengeServer()

    def test_challenge_interim_responses_and_notes_are_dropped(self):
        resource = self.fetch()
        self.assertEqual(resource.response.status_code, 200)
        self.assertEqual(resource.nonfinal_responses, [])
        self.assertFalse([n for n in resource.response.notes if isinstance(n, ONE_XX_BAD_HEADER)])


if __name__ == "__main__":
    unittest.main()
