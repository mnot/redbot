"""
Tests for the text formatter's colour handling.
"""

import unittest
from typing import Any, Dict, Optional, cast

from httplint.note import levels

from redbot.formatter.text import BaseTextFormatter

END = "\033[0;39m"


def make_formatter(**kw: Any) -> BaseTextFormatter:
    "Build a formatter; colorize doesn't use the config, resource or output."
    return BaseTextFormatter(cast(Any, None), cast(Any, None), lambda s: None, dict(kw))


class TestColorize(unittest.TestCase):
    def test_colour_per_level(self) -> None:
        expected: Dict[Optional[levels], str] = {
            levels.GOOD: "\033[1;32m",
            levels.BAD: "\033[1;31m",
            levels.WARN: "\033[1;33m",
            levels.INFO: "\033[0;32m",
            None: "\033[1;34m",  # the URI line
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
