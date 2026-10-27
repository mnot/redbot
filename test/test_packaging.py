#!/usr/bin/env python3

"""
Packaging and container hygiene (mnot/redbot#533).
"""

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*path: str) -> str:
    with open(os.path.join(ROOT, *path), encoding="utf-8") as fh:
        return fh.read()


class TestPackaging(unittest.TestCase):
    def test_docker_sample_does_not_suggest_a_shared_directory_for_save_dir(self):
        samples = re.findall(
            r"^#?\s*save_dir\s*=\s*(\S+)", read("extra", "config-docker.txt"), re.M
        )
        self.assertEqual(samples, ["/var/lib/redbot"])

    def test_docker_context_excludes_secrets(self):
        ignored = read(".dockerignore").splitlines()
        for pattern in ("/config.txt", "*.pem", "*.key"):
            self.assertIn(pattern, ignored)

    def test_docker_image_does_not_use_the_root_config(self):
        self.assertIn("extra/config-docker.txt", read("Dockerfile"))

    def test_setuptools_is_new_enough_for_license_expressions(self):
        pyproject = read("pyproject.toml")
        self.assertIn('license = "MIT"', pyproject)  # PEP 639, needs setuptools 77
        floor = re.search(r'"setuptools>=(\d+)', pyproject)
        self.assertIsNotNone(floor)
        self.assertGreaterEqual(int(floor.group(1)), 77)


if __name__ == "__main__":
    unittest.main()
