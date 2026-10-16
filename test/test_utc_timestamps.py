#!/usr/bin/env python3

import unittest
import warnings
from configparser import ConfigParser

from redbot.formatter.har import isoformat
from redbot.resource import HttpResource


class TestUtcTimestamps(unittest.TestCase):
    """
    datetime.utcfromtimestamp() is deprecated since Python 3.12; these run with warnings
    as errors to catch it (or any other DeprecationWarning) coming back.
    """

    def setUp(self):
        ctx = warnings.catch_warnings()
        ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)
        warnings.simplefilter("error")

    def test_har_isoformat(self):
        self.assertEqual(isoformat(784111777), "1994-11-06T08:49:37Z")
        self.assertEqual(isoformat(784111777.5), "1994-11-06T08:49:37.500000Z")
        self.assertEqual(isoformat(0), "1970-01-01T00:00:00Z")

    def test_lm_validate_if_modified_since(self):
        conf = ConfigParser()
        conf.add_section("redbot")
        resource = HttpResource(conf["redbot"])
        resource.response.headers.parsed["last-modified"] = 784111777

        validator = resource.subreqs["lm_validate"]
        headers = validator.modify_request_headers([])

        self.assertEqual(headers, [("If-Modified-Since", "Sun, 06 Nov 1994 08:49:37 GMT")])

    def test_lm_validate_out_of_range(self):
        conf = ConfigParser()
        conf.add_section("redbot")
        resource = HttpResource(conf["redbot"])
        resource.response.headers.parsed["last-modified"] = 2**40

        validator = resource.subreqs["lm_validate"]
        self.assertEqual(validator.modify_request_headers([]), [])


if __name__ == "__main__":
    unittest.main()
