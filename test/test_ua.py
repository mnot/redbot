#!/usr/bin/env python3

import unittest
from configparser import ConfigParser

from redbot import __version__
from redbot.resource.fetch import DEFAULT_UI_URI, ua_string


class TestUaString(unittest.TestCase):
    def _config(self, **values):
        parser = ConfigParser()
        parser.read_dict({"redbot": {k: v for k, v in values.items()}})
        return parser["redbot"]

    def test_defaults_when_ui_uri_unset(self):
        self.assertEqual(
            ua_string(self._config()).decode("ascii"),
            f"RED/{__version__} ({DEFAULT_UI_URI})",
        )

    def test_uses_ui_uri(self):
        self.assertEqual(
            ua_string(self._config(ui_uri="https://red.example/app/")).decode("ascii"),
            f"RED/{__version__} (https://red.example/app/)",
        )

    def test_blank_ui_uri_falls_back(self):
        self.assertEqual(
            ua_string(self._config(ui_uri="   ")).decode("ascii"),
            f"RED/{__version__} ({DEFAULT_UI_URI})",
        )


if __name__ == "__main__":
    unittest.main()
