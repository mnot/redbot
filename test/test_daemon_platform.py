#!/usr/bin/env python3

import os
import signal
import tempfile
import unittest
from configparser import ConfigParser
from unittest.mock import patch

from redbot.daemon import RedBotServer


def make_config():
    conf = ConfigParser()
    conf.add_section("redbot")
    conf["redbot"]["port"] = "0"
    conf["redbot"]["static_root"] = "static"
    return conf["redbot"]


def make_server():
    with (
        patch("redbot.daemon.thor.http.HttpServer"),
        patch("redbot.daemon.signal.signal") as install,
        patch.object(RedBotServer, "console"),
    ):
        server = RedBotServer(make_config())
    return server, install


class TestSignalHandlers(unittest.TestCase):
    def test_constructs_without_sigbus(self):
        """
        Regression test for #444: SIGBUS is absent on Windows, which used to make
        RedBotServer raise AttributeError at startup.
        """
        sigbus = signal.SIGBUS
        del signal.SIGBUS
        self.addCleanup(setattr, signal, "SIGBUS", sigbus)

        _, install = make_server()

        installed = {call.args[0] for call in install.call_args_list}
        self.assertIn(signal.SIGSEGV, installed)
        self.assertIn(signal.SIGINT, installed)
        self.assertNotIn(sigbus, installed)


class TestWalkFiles(unittest.TestCase):
    def test_nested_files_use_forward_slashes(self):
        server, _ = make_server()
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "sub", "deep"))
            with open(os.path.join(tmp, "sub", "deep", "index.html"), "wb") as fh:
                fh.write(b"deep")
            with open(os.path.join(tmp, "top.txt"), "wb") as fh:
                fh.write(b"top")
            files = server.walk_files(tmp)

        self.assertEqual(
            files,
            {
                b"/top.txt": b"top",
                b"/sub/deep/index.html": b"deep",
                b"/sub/deep": b"deep",
            },
        )

    def test_windows_separators_are_normalised(self):
        """
        Simulate os.path.relpath returning backslash-separated paths, as on Windows.
        """
        server, _ = make_server()
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "sub"))
            with open(os.path.join(tmp, "sub", "index.html"), "wb") as fh:
                fh.write(b"idx")
            with (
                patch("redbot.daemon.os.sep", "\\"),
                patch("redbot.daemon.os.path.relpath", return_value="sub\\index.html"),
            ):
                files = server.walk_files(tmp)

        self.assertEqual(files, {b"/sub/index.html": b"idx", b"/sub": b"idx"})


if __name__ == "__main__":
    unittest.main()
