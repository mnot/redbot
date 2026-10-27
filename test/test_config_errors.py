#!/usr/bin/env python3

"""
A missing or unusable configuration file is reported in one line, not as a traceback
(mnot/redbot#534).
"""

import os
import subprocess
import sys
import tempfile
import unittest


def run(module: str, path: str):
    return subprocess.run(
        [sys.executable, "-m", module, path],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


class TestConfigErrors(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name

    def write(self, name: str, content: str) -> str:
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path

    def assert_one_line(self, module: str, path: str, expected: str) -> None:
        result = run(module, path)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(len(result.stderr.strip().splitlines()), 1, result.stderr)
        self.assertIn(expected, result.stderr)

    def test_missing_file(self):
        for module in ("redbot.gc", "redbot.daemon"):
            with self.subTest(module=module):
                self.assert_one_line(module, os.path.join(self.dir, "nope.txt"), "was not found")

    def test_no_redbot_section(self):
        path = self.write("other.txt", "[other]\nx = 1\n")
        for module in ("redbot.gc", "redbot.daemon"):
            with self.subTest(module=module):
                self.assert_one_line(module, path, "no [redbot] section")

    def test_malformed_file(self):
        path = self.write("bad.txt", "[redbot\nsave_dir = /tmp\n")
        for module in ("redbot.gc", "redbot.daemon"):
            with self.subTest(module=module):
                self.assert_one_line(module, path, "can't parse")

    def test_directory_instead_of_a_file(self):
        for module in ("redbot.gc", "redbot.daemon"):
            with self.subTest(module=module):
                self.assert_one_line(module, self.dir, "configuration file")

    def test_valid_file_still_works(self):
        save_dir = os.path.join(self.dir, "save")
        os.mkdir(save_dir)
        path = self.write("ok.txt", f"[redbot]\nsave_dir = {save_dir}\n")
        result = run("redbot.gc", path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("redbot_gc: 0 files", result.stdout)


if __name__ == "__main__":
    unittest.main()
