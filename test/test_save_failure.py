#!/usr/bin/env python3

# pylint: disable=invalid-name,consider-using-with

import http.server
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from configparser import ConfigParser
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from redbot.formatter import find_formatter
from redbot.i18n import set_locale
from redbot.resource import HttpResource
from redbot.webui.links import WebUiLinkGenerator
from redbot.webui.saved_tests import init_save_file, save_test


def config(**values):
    parser = ConfigParser()
    parser.read_dict({"redbot": values})
    return parser["redbot"]


def make_ui(save_dir):
    return SimpleNamespace(config=config(save_dir=save_dir), save_path="", error_log=MagicMock())


def chmod_enforced():
    "Whether a 0o555 directory refuses new files here (not so for root, or on some mounts)."
    with tempfile.TemporaryDirectory() as tmp:
        os.chmod(tmp, 0o555)
        try:
            os.close(tempfile.mkstemp(dir=tmp)[0])
        except OSError:
            return True
        finally:
            os.chmod(tmp, 0o755)
        return False


CHMOD_ENFORCED = chmod_enforced()


class TestInitSaveFile(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.save_dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def test_creates_file(self):
        ui = make_ui(self.save_dir)
        test_id = init_save_file(ui)
        self.assertEqual(test_id, os.path.basename(ui.save_path))
        ui.error_log.assert_not_called()

    def test_logs_when_file_cannot_be_created(self):
        ui = make_ui(self.save_dir)
        with patch("tempfile.mkstemp", side_effect=PermissionError("denied")):
            self.assertIsNone(init_save_file(ui))
        self.assertEqual(ui.save_path, "")
        self.assertEqual(ui.error_log.call_count, 1)
        self.assertIn("denied", ui.error_log.call_args[0][0])

    @unittest.skipUnless(CHMOD_ENFORCED, "directory permissions are not enforced")
    def test_read_only_directory(self):
        os.chmod(self.save_dir, 0o555)
        self.addCleanup(os.chmod, self.save_dir, 0o755)
        ui = make_ui(self.save_dir)
        self.assertIsNone(init_save_file(ui))
        self.assertEqual(ui.error_log.call_count, 1)

    def test_unconfigured_is_silent(self):
        ui = make_ui("")
        self.assertIsNone(init_save_file(ui))
        ui.error_log.assert_not_called()


class TestSaveTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ui = make_ui(self._tmp.name)
        self.test_id = init_save_file(self.ui)

    def test_saves(self):
        save_test(self.ui, {"a": 1})  # type: ignore[arg-type]
        self.assertGreater(os.path.getsize(self.ui.save_path), 0)
        self.ui.error_log.assert_not_called()

    def test_write_error_is_logged(self):
        with patch("gzip.open", side_effect=OSError("No space left on device")):
            save_test(self.ui, {"a": 1})  # type: ignore[arg-type]
        self.assertEqual(self.ui.error_log.call_count, 1)
        self.assertIn("No space left", self.ui.error_log.call_args[0][0])
        self.assertIn("Traceback", self.ui.error_log.call_args[0][0])
        self.assertFalse(os.path.exists(self.ui.save_path))

    def test_unpicklable_resource_is_logged(self):
        save_test(self.ui, {"a": lambda: 1})  # type: ignore[arg-type]
        self.assertEqual(self.ui.error_log.call_count, 1)
        self.assertIn(str(self.test_id), self.ui.error_log.call_args[0][0])
        self.assertFalse(os.path.exists(self.ui.save_path))

    def test_failure_to_remove_the_file_is_ignored(self):
        with (
            patch("gzip.open", side_effect=OSError("boom")),
            patch("os.remove", side_effect=PermissionError),
        ):
            save_test(self.ui, {"a": 1})  # type: ignore[arg-type]
        self.assertEqual(self.ui.error_log.call_count, 1)

    def test_no_save_path_is_silent(self):
        ui = make_ui(self._tmp.name)
        save_test(ui, {"a": 1})  # type: ignore[arg-type]
        ui.error_log.assert_not_called()


class TestSaveFormRendering(unittest.TestCase):
    @staticmethod
    def render_start(test_id):
        out: list[str] = []
        ui = SimpleNamespace(config=config(), base_uri="/")
        resource = HttpResource(config())
        resource.set_request("http://example.com/")
        formatter = find_formatter("html")(
            config(),
            resource,
            out.append,
            {
                "nonce": "n",
                "test_id": test_id,
                "allow_save": test_id,
                "link_generator": WebUiLinkGenerator(ui),
            },
        )
        with set_locale("en"):
            formatter.start_output()
        return "".join(out)

    def test_no_save_form_without_test_id(self):
        page = self.render_start(None)
        self.assertNotIn("save_form", page)
        self.assertNotIn("saved/", page)

    def test_save_form_with_test_id(self):
        page = self.render_start("abc123")
        self.assertIn('id="save_form"', page)
        self.assertIn("saved/abc123", page)


class OkHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # pylint: disable=invalid-name
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):  # pylint: disable=arguments-differ
        pass


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class TestUnwritableSaveDirDaemon(unittest.TestCase):
    """Regression test for #467: an unwritable save_dir must not break or stop the daemon."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # A regular file exists but can't hold new files, for any uid.
        save_dir = os.path.join(tmp.name, "not_a_dir")
        with open(save_dir, "w", encoding="utf-8"):
            pass

        target = http.server.HTTPServer(("127.0.0.1", 0), OkHandler)
        threading.Thread(target=target.serve_forever, daemon=True).start()
        self.addCleanup(target.server_close)
        self.addCleanup(target.shutdown)
        self.target_port = target.server_address[1]

        self.port = free_port()
        conf_file = os.path.join(tmp.name, "config.txt")
        with open(conf_file, "w", encoding="utf-8") as fh:
            fh.write(
                "[redbot]\nhost = 127.0.0.1\nstatic_root = static\n"
                f"enable_local_access = True\nport = {self.port}\nsave_dir = {save_dir}\n"
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

    def test_check_completes_without_save(self):
        uri = f"http://127.0.0.1:{self.target_port}/"
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/check?uri={uri}", method="POST", data=b""
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
        self.assertIn("</html>", body)
        self.assertNotIn("saved/", body)
        self.assertIsNone(self.daemon.poll(), "daemon exited")
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/", timeout=10) as response:
            self.assertEqual(response.status, 200)
        self.stop_daemon()
        self.assertIn("save_dir", self.stderr)


if __name__ == "__main__":
    unittest.main()
