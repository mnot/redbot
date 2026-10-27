#!/usr/bin/env python3

"""
A server can't make REDbot keep an unbounded number of 1xx responses (mnot/redbot#530).
"""

import unittest
from configparser import ConfigParser
from types import SimpleNamespace

from redbot.resource import HttpResource
from redbot.resource.fetch import MAX_NONFINAL_RESPONSES, ONE_XX_TOO_MANY


class TestNonfinalResponses(unittest.TestCase):
    def resource(self) -> HttpResource:
        conf = ConfigParser()
        conf.add_section("redbot")
        resource = HttpResource(conf["redbot"])
        resource.exchange = SimpleNamespace(res_version=b"1.1", conn=None)  # type: ignore
        return resource

    def test_only_the_first_few_are_kept(self):
        resource = self.resource()
        extra = 5
        for _ in range(MAX_NONFINAL_RESPONSES + extra):
            resource._response_nonfinal(
                b"103", b"Early Hints", [(b"Link", b"</a.css>; rel=preload")]
            )
        self.assertEqual(len(resource.nonfinal_responses), MAX_NONFINAL_RESPONSES)
        self.assertEqual(resource.nonfinal_overflow, extra)
        too_many = [n for n in resource.response.notes if isinstance(n, ONE_XX_TOO_MANY)]
        self.assertEqual(len(too_many), 1)

    def test_few_responses_raise_no_note(self):
        resource = self.resource()
        for _ in range(3):
            resource._response_nonfinal(b"100", b"Continue", [])
        self.assertEqual(len(resource.nonfinal_responses), 3)
        self.assertFalse([n for n in resource.response.notes if isinstance(n, ONE_XX_TOO_MANY)])


if __name__ == "__main__":
    unittest.main()
