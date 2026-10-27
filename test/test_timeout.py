#!/usr/bin/env python3

"""
The runtime timeout stops the whole test, even when the request names a check (mnot/redbot#515).
"""

import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request

MAX_RUNTIME = 2  # seconds
CLOSE_WAIT = 8  # seconds; well under thor's 60 s inactivity timeout


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class HangingServer:
    "Accepts connections, reads the request, and never answers."

    def __init__(self):
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        self.port = self.sock.getsockname()[1]
        self.closed = threading.Event()  # set when a client closes its end
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._hold, args=(conn,), daemon=True).start()

    def _hold(self, conn):
        try:
            while conn.recv(65536):
                pass
        except OSError:
            pass
        self.closed.set()
        conn.close()

    def close(self):
        self.sock.close()


class TestTimeoutStopsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        save_dir = self.save_dir = os.path.join(tmp.name, "save")
        os.mkdir(save_dir)
        self.target = HangingServer()
        self.addCleanup(self.target.close)

        self.port = free_port()
        conf_file = os.path.join(tmp.name, "config.txt")
        with open(conf_file, "w", encoding="utf-8") as fh:
            fh.write(
                "[redbot]\nhost = 127.0.0.1\nstatic_root = static\nenable_local_access = True\n"
                f"max_runtime = {MAX_RUNTIME}\nport = {self.port}\nsave_dir = {save_dir}\n"
            )
        self.daemon = subprocess.Popen(
            [sys.executable, "-m", "redbot.daemon", conf_file],
            stderr=subprocess.PIPE,
            text=True,
        )
        self.stderr = ""
        self.addCleanup(self.stop_daemon)
        deadline = time.time() + 20
        while time.time() < deadline:
            self.assertIsNone(self.daemon.poll(), "daemon exited during startup")
            try:
                socket.create_connection(("127.0.0.1", self.port), timeout=1).close()
                return
            except OSError:
                time.sleep(0.1)
        self.fail("daemon did not start")

    def stop_daemon(self):
        "Stop the daemon and collect its stderr; safe to call twice."
        if self.daemon.poll() is None:
            self.daemon.terminate()
        try:
            _, err = self.daemon.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            self.daemon.kill()
            _, err = self.daemon.communicate()
        self.stderr = self.stderr or err or ""

    def check(self, query):
        uri = f"http://127.0.0.1:{self.target.port}/"
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/check?uri={uri}{query}", method="POST", data=b""
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8")

    def test_timeout_closes_upstream_connection(self):
        for query in ("", "&check_name=range"):
            with self.subTest(query=query):
                self.target.closed.clear()
                self.assertIn("REDbot timeout.", self.check(query))
                self.assertTrue(
                    self.target.closed.wait(CLOSE_WAIT),
                    "REDbot kept its connection to the target open after the timeout",
                )

    def test_timeout_logs_the_test_uri(self):
        self.check("&check_name=range")
        self.stop_daemon()
        self.assertIn(f"timeout <http://127.0.0.1:{self.target.port}/>", self.stderr)

    def test_saved_test_loads_after_timeout(self):
        self.check("&check_name=range")
        time.sleep(1)  # the formatter finishes, and saves, a moment after the timeout
        saved = os.listdir(self.save_dir)
        self.assertEqual(len(saved), 1)
        url = f"http://127.0.0.1:{self.port}/saved/{saved[0]}?check_name=range"
        with urllib.request.urlopen(url, timeout=10) as response:
            self.assertEqual(response.status, 200)
        with urllib.request.urlopen(url.split("?")[0], timeout=10) as response:
            self.assertEqual(response.status, 200)


if __name__ == "__main__":
    unittest.main()
