#!/usr/bin/env python3

# pylint: disable=invalid-name,consider-using-with

import gzip
import http.server
import os
import pickle
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from configparser import ConfigParser
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from redbot.formatter import find_formatter
from redbot.i18n import set_locale
from redbot.resource import HttpResource
from redbot.webui import RedWebUi
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


MISSING_CLASS = b"credbot.resource\nNoSuchClass\n."
MISSING_MODULE = b"cno_such_module_xyz\nThing\n."


def write_saved(save_dir, test_id, payload, compress=True):
    "Write payload (bytes) as a saved test file."
    opener = gzip.open if compress else open
    with opener(os.path.join(save_dir, test_id), "wb") as fh:
        fh.write(payload)


def stale_resource(cfg, drop):
    "Pickle of an HttpResource that has lost an attribute, as from an older version."
    resource = HttpResource(cfg)
    resource.set_request("http://example.com/")
    resource.check_done = True
    delattr(resource, drop)
    return pickle.dumps(resource)


class TestLoadSavedTest(unittest.TestCase):
    """Regression tests for #483: a saved test that can't be used gets a 500, not a crash."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.save_dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)
        self.cfg = config(save_dir=self.save_dir)
        self.log: list[str] = []

    def get(self, test_id="abc123", query=b""):
        "Run a GET for the saved test; returns the exchange mock."
        exchange = MagicMock()
        RedWebUi(
            self.cfg,
            "GET",
            f"/saved/{test_id}".encode("ascii"),
            query,
            [],
            b"",
            exchange,
            "127.0.0.1",
            self.log.append,
        )
        return exchange

    def assert_status(self, exchange, status):
        self.assertEqual(exchange.response_start.call_args[0][0], status)
        self.assertEqual(exchange.response_start.call_count, 1)

    def assert_load_failure(self, exchange, expected):
        self.assert_status(exchange, b"500")
        exchange.response_done.assert_called_once()
        self.assertEqual(len(self.log), 1)
        self.assertIn("abc123", self.log[0])
        self.assertIn("Traceback", self.log[0])
        self.assertIn(expected, self.log[0])

    def test_valid_file_loads(self):
        resource = HttpResource(self.cfg)
        resource.set_request("http://example.com/")
        resource.check_done = True
        write_saved(self.save_dir, "abc123", pickle.dumps(resource))
        exchange = self.get()
        self.assert_status(exchange, b"200")
        self.assertEqual(self.log, [])

    def test_missing_class(self):
        write_saved(self.save_dir, "abc123", MISSING_CLASS)
        self.assert_load_failure(self.get(), "NoSuchClass")

    def test_missing_module(self):
        write_saved(self.save_dir, "abc123", MISSING_MODULE)
        self.assert_load_failure(self.get(), "no_such_module_xyz")

    def test_wrong_object_type(self):
        write_saved(self.save_dir, "abc123", pickle.dumps({"a": 1}))
        exchange = self.get()
        self.assert_status(exchange, b"500")
        self.assertEqual(len(self.log), 1)
        self.assertIn("dict", self.log[0])

    def test_attribute_missing_before_response(self):
        write_saved(self.save_dir, "abc123", stale_resource(self.cfg, "descend"))
        self.assert_load_failure(self.get(), "descend")

    def test_attribute_missing_for_check_name(self):
        write_saved(self.save_dir, "abc123", stale_resource(self.cfg, "subreqs"))
        self.assert_load_failure(self.get(query=b"check_name=x"), "subreqs")

    def test_attribute_missing_while_rendering(self):
        write_saved(self.save_dir, "abc123", stale_resource(self.cfg, "request"))
        self.assert_load_failure(self.get(), "request")

    def test_unfinished_test(self):
        write_saved(self.save_dir, "abc123", stale_resource(self.cfg, "check_done"))
        self.assert_load_failure(self.get(), "check_done")

    def test_corrupt_files(self):
        for name, payload, compress in [
            ("empty", b"", True),
            ("truncated", pickle.dumps({"a": 1})[:5], True),
            ("notpickle", b"this is not a pickle", True),
        ]:
            with self.subTest(name):
                self.log.clear()
                write_saved(self.save_dir, name, payload, compress)
                self.assert_status(self.get(name), b"500")
                self.assertEqual(len(self.log), 1)

    def test_not_gzip_is_not_found(self):
        write_saved(self.save_dir, "plain", b"plain text", compress=False)
        self.assert_status(self.get("plain"), b"404")

    def test_absent_file_is_not_found(self):
        self.assert_status(self.get("nothere"), b"404")
        self.assertEqual(self.log, [])


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


class TestUnusableSavedTestDaemon(unittest.TestCase):
    """Regression test for #483: loading a stale saved test must not stop the daemon."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        save_dir = os.path.join(tmp.name, "save")
        os.mkdir(save_dir)
        write_saved(save_dir, "missingclass", MISSING_CLASS)
        write_saved(save_dir, "missingmodule", MISSING_MODULE)
        write_saved(save_dir, "norender", stale_resource(config(), "request"))

        self.port = free_port()
        conf_file = os.path.join(tmp.name, "config.txt")
        with open(conf_file, "w", encoding="utf-8") as fh:
            fh.write(
                "[redbot]\nhost = 127.0.0.1\nstatic_root = static\n"
                f"port = {self.port}\nsave_dir = {save_dir}\n"
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

    def fetch(self, path):
        "Returns (status, Cache-Control, body)."
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=10) as r:
                return r.status, r.headers.get("Cache-Control"), r.read()
        except urllib.error.HTTPError as why:
            return why.code, why.headers.get("Cache-Control"), why.read()

    def status(self, path):
        return self.fetch(path)[0]

    def test_daemon_survives(self):
        for test_id in ["missingclass", "missingmodule"]:
            self.assertEqual(self.status(f"/saved/{test_id}"), 500)
            self.assertIsNone(self.daemon.poll(), "daemon exited")
        self.assertEqual(self.status("/saved/nothere"), 404)
        self.assertEqual(self.status("/"), 200)
        self.stop_daemon()
        self.assertIn("NoSuchClass", self.stderr)
        self.assertNotIn("FATAL", self.stderr)

    def test_render_failure_is_an_error_not_a_cacheable_page(self):
        for query in ["", "?format=txt"]:
            with self.subTest(query):
                status, cache_control, body = self.fetch(f"/saved/norender{query}")
                self.assertEqual(status, 500)
                self.assertNotIn("3600", cache_control or "")
                self.assertIn(b"problem loading", body)
                self.assertIsNone(self.daemon.poll(), "daemon exited")
        self.assertEqual(self.status("/"), 200)
        self.stop_daemon()
        self.assertIn("has no attribute 'request'", self.stderr)
        self.assertNotIn("FATAL", self.stderr)


if __name__ == "__main__":
    unittest.main()
