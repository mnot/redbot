#!/usr/bin/env python3

import unittest
from configparser import ConfigParser

from redbot.resource import HttpResource
from redbot.resource.active_check.etag_validate import INM_DUP_ETAG_STRONG


class TestEtagValidate(unittest.TestCase):
    def test_strong_duplicate_etag_note_uses_plain_etag_string(self):
        """
        Regression test for #432: the strong-duplicate-ETag note must render the plain
        ETag value, not a repr of the (weak, etag) tuple returned by headers.parsed.
        """
        conf = ConfigParser()
        conf.add_section("redbot")
        resource = HttpResource(conf["redbot"])

        resource.response.status_code = 200
        resource.response.content_hash = b"hash-a"
        resource.response.headers.parsed["etag"] = (False, "abc123")

        validator = resource.subreqs["etag_validate"]
        validator.response.complete = True
        validator.response.status_code = 200
        validator.response.content_hash = b"hash-b"  # different body, same strong ETag
        validator.response.headers.parsed["etag"] = (False, "abc123")

        validator.done()

        notes = [n for n in resource.response.notes if isinstance(n, INM_DUP_ETAG_STRONG)]
        self.assertEqual(len(notes), 1)
        note = notes[0]
        self.assertEqual(note.vars["etag"], "abc123")
        self.assertIn("abc123", note.detail)
        self.assertNotIn("False", note.detail)


if __name__ == "__main__":
    unittest.main()
