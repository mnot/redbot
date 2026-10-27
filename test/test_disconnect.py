#!/usr/bin/env python3

"""
A client that goes away stops the test it started (mnot/redbot#516).
"""

import os
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from configparser import ConfigParser
from unittest.mock import MagicMock, patch

from redbot.webui.handlers.run_test import RunTestHandler

CLOSE_WAIT = 5  # seconds; max_runtime is far longer, so the timeout can't be what closes it


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
        self.connected = threading.Event()  # set when a client has sent a request
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
                self.connected.set()
        except OSError:
            pass
        self.closed.set()
        conn.close()

    def close(self):
        self.sock.close()


class TestClientDisconnect(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        save_dir = os.path.join(tmp.name, "save")
        os.mkdir(save_dir)
        self.target = HangingServer()
        self.addCleanup(self.target.close)

        self.port = free_port()
        conf_file = os.path.join(tmp.name, "config.txt")
        with open(conf_file, "w", encoding="utf-8") as fh:
            fh.write(
                "[redbot]\nhost = 127.0.0.1\nstatic_root = static\nenable_local_access = True\n"
                f"max_runtime = 60\nport = {self.port}\nsave_dir = {save_dir}\n"
            )
        self.daemon = subprocess.Popen(
            [sys.executable, "-m", "redbot.daemon", conf_file],
            stderr=subprocess.PIPE,
            text=True,
        )
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
        if self.daemon.poll() is None:
            self.daemon.terminate()
        try:
            _, err = self.daemon.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            self.daemon.kill()
            _, err = self.daemon.communicate()
        return err or ""

    def test_disconnect_closes_upstream_connection(self):
        uri = f"http://127.0.0.1:{self.target.port}/"
        client = socket.create_connection(("127.0.0.1", self.port), timeout=10)
        self.addCleanup(client.close)
        # Close with a reset: thor holds on for request_timeout after a client's clean FIN.
        client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        client.sendall(
            f"POST /check?uri={uri} HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Length: 0\r\n\r\n".encode()
        )
        self.assertTrue(self.target.connected.wait(10), "REDbot never contacted the target")
        client.close()
        self.assertTrue(
            self.target.closed.wait(CLOSE_WAIT),
            "REDbot kept testing after the client disconnected",
        )
        self.assertIsNone(self.daemon.poll(), "daemon exited")
        err = self.stop_daemon()
        self.assertNotIn("Traceback", err)


class TestDisconnectBeforeTheTestStarts(unittest.TestCase):
    "The client goes away while a captcha is pending; the test must not start afterwards."

    def test_error_during_captcha_stops_and_prevents_the_test(self):
        conf = ConfigParser()
        conf.add_section("redbot")
        ui = MagicMock()
        ui.config = conf["redbot"]
        ui.query_string = {"uri": ["http://example.com/"]}
        ui.response_done = False
        with (
            patch("redbot.webui.handlers.run_test.thor.schedule"),
            patch("redbot.webui.handlers.run_test.HttpResource") as resource_class,
            patch("redbot.webui.handlers.run_test.find_formatter") as find_formatter,
            patch("redbot.webui.handlers.run_test.ratelimiter.process"),
            patch("redbot.webui.handlers.run_test.CaptchaHandler") as captcha,
        ):
            top_resource = resource_class.return_value
            find_formatter.return_value.return_value.resource = top_resource
            captcha.return_value.configured.return_value = True
            RunTestHandler.handle(ui)
        listeners = {call[0][0]: call[0][1] for call in ui.exchange.on.call_args_list}
        listeners["error"](Exception("client went away"))
        top_resource.stop.assert_called_once()
        self.assertTrue(ui.response_done)
        captcha.call_args[0][1]()  # the captcha completes afterwards
        ui.exchange.response_start.assert_not_called()
        top_resource.check.assert_not_called()


if __name__ == "__main__":
    unittest.main()
