#!/usr/bin/env python3

"""
Packaging and container hygiene (mnot/redbot#533).
"""

import os
import re
import tomllib
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
        self.assertTrue(samples)
        for sample in samples:
            self.assertNotEqual(sample.rstrip("/"), "/tmp")
            self.assertEqual(sample, "/var/lib/redbot")  # the directory the image provides

    def test_docker_context_excludes_secrets_at_any_depth(self):
        # .dockerignore patterns use Go's filepath.Match, where * doesn't cross /, so a bare
        # *.pem only matches at the root of the build context.
        ignored = read(".dockerignore").splitlines()
        for pattern in ("/config.txt", "**/*.pem", "**/*.key", "**/.env"):
            self.assertIn(pattern, ignored)
        self.assertNotIn("*.pem", ignored)

    def test_docker_image_does_not_use_or_copy_the_root_config(self):
        dockerfile = read("Dockerfile")
        self.assertIn("extra/config-docker.txt", dockerfile)
        self.assertNotRegex(dockerfile, r"(?m)^\s*COPY\b.*\bconfig\.txt")

    def test_setuptools_is_new_enough_for_license_expressions(self):
        with open(os.path.join(ROOT, "pyproject.toml"), "rb") as fh:
            pyproject = tomllib.load(fh)
        self.assertIsInstance(pyproject["project"]["license"], str)  # PEP 639
        floors = [
            int(m.group(1))
            for requirement in pyproject["build-system"]["requires"]
            if (m := re.match(r"setuptools\s*(?:>=|~=|==)\s*(\d+)", requirement))
        ]
        self.assertEqual(len(floors), 1)
        self.assertGreaterEqual(floors[0], 77)


if __name__ == "__main__":
    unittest.main()
