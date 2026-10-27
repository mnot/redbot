#!/usr/bin/env python3

"""
The CLI stops after --timeout seconds and shows what it has (mnot/redbot#531).
"""

import socket
import subprocess
import sys
import threading
import time
import unittest


class TestCliTimeout(unittest.TestCase):
    def setUp(self):
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        self.addCleanup(self.sock.close)
        self.port = self.sock.getsockname()[1]
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        "Sends the status line and a header, then a byte every half second, for ever."
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self.drip, args=(conn,), daemon=True).start()

    @staticmethod
    def drip(conn):
        try:
            conn.recv(65536)
            conn.sendall(
                b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 100000\r\n\r\n"
            )
            while True:
                conn.sendall(b"x")
                time.sleep(0.5)
        except OSError:
            conn.close()

    def run_cli(self, *args: str, timeout: float = 30):
        started = time.time()
        result = subprocess.run(
            [sys.executable, "-m", "redbot.cli", *args, f"http://127.0.0.1:{self.port}/"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result, time.time() - started

    def test_slow_server_cannot_keep_the_cli_alive(self):
        result, elapsed = self.run_cli("--timeout", "2")
        self.assertLess(elapsed, 15)
        self.assertIn("stopped after 2 seconds", result.stderr)
        self.assertIn("HTTP/1.1 200 OK", result.stdout)  # what was collected is shown

    def test_default_is_sixty_seconds(self):
        result = subprocess.run(
            [sys.executable, "-m", "redbot.cli", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertIn("default 60", result.stdout)


if __name__ == "__main__":
    unittest.main()
