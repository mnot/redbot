"""
Tests for the text formatter's colour handling.
"""

import unittest
from typing import Any, Dict, Optional

from httplint.note import levels

from redbot.formatter.text import BaseTextFormatter

END = "\033[0;39m"


def make_formatter(**kw: Any) -> BaseTextFormatter:
    "Build a formatter without the resource and config that colorize doesn't use."
    formatter = BaseTextFormatter.__new__(BaseTextFormatter)
    formatter.kw = dict(kw)
    return formatter


class TestColorize(unittest.TestCase):
    def test_colour_per_level(self) -> None:
        expected: Dict[Optional[levels], str] = {
            levels.GOOD: "\033[1;32m",
            levels.BAD: "\033[1;31m",
            levels.WARN: "\033[1;33m",
            levels.INFO: "\033[1;34m",
            None: "\033[1;34m",
        }
        formatter = make_formatter(tty_out=True)
        for level, start in expected.items():
            with self.subTest(level=level):
                self.assertEqual(formatter.colorize(level, "x"), f"{start}x{END}")

    def test_no_colour_without_tty(self) -> None:
        formatter = make_formatter()
        for level in [*levels, None]:
            with self.subTest(level=level):
                self.assertEqual(formatter.colorize(level, "x"), "x")


if __name__ == "__main__":
    unittest.main()
