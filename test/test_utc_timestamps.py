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

    def test_har_isoformat_pre_1970(self):
        self.assertEqual(isoformat(-1), "1969-12-31T23:59:59Z")
        self.assertEqual(isoformat(-86400.25), "1969-12-30T23:59:59.750000Z")

    def test_har_isoformat_out_of_range(self):
        with self.assertRaises(ValueError):
            isoformat(2**40)
        with self.assertRaises(OverflowError):
            isoformat(1e20)

    def test_lm_validate_if_modified_since(self):
        conf = ConfigParser()
        conf.add_section("redbot")
        resource = HttpResource(conf["redbot"])
        resource.response.headers.parsed["last-modified"] = 784111777

        validator = resource.subreqs["lm_validate"]
        headers = validator.modify_request_headers([])

        self.assertEqual(headers, [("If-Modified-Since", "Sun, 06 Nov 1994 08:49:37 GMT")])

    def test_lm_validate_pre_1970(self):
        conf = ConfigParser()
        conf.add_section("redbot")
        resource = HttpResource(conf["redbot"])
        resource.response.headers.parsed["last-modified"] = -1

        validator = resource.subreqs["lm_validate"]
        headers = validator.modify_request_headers([])

        self.assertEqual(headers, [("If-Modified-Since", "Wed, 31 Dec 1969 23:59:59 GMT")])

    def test_lm_validate_out_of_range(self):
        conf = ConfigParser()
        conf.add_section("redbot")
        resource = HttpResource(conf["redbot"])
        validator = resource.subreqs["lm_validate"]

        # ValueError is swallowed; OverflowError was never caught and still isn't.
        resource.response.headers.parsed["last-modified"] = 2**40
        self.assertEqual(validator.modify_request_headers([]), [])
        resource.response.headers.parsed["last-modified"] = 1e20
        with self.assertRaises(OverflowError):
            validator.modify_request_headers([])


if __name__ == "__main__":
    unittest.main()
