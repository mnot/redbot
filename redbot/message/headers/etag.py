#!/usr/bin/env python

from typing import Tuple

from redbot.message import headers
from redbot.syntax import rfc7232
from redbot.type import AddNoteMethodType


class etag(headers.HttpHeader):
    canonical_name = "ETag"
    description = """\
The `ETag` header provides an opaque identifier for the representation."""
    reference = "%s#header.etag" % rfc7232.SPEC_URL
    syntax = rfc7232.ETag
    list_header = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Tuple[bool, str]:
        if field_value[:2] == "W/":
            return (True, headers.unquote_string(field_value[2:]))
        return (False, headers.unquote_string(field_value))


class ETagTest(headers.HeaderTest):
    name = "ETag"
    inputs = [b'"foo"']
    expected_out = (False, "foo")
    expected_err = []  # type: ignore


class WeakETagTest(headers.HeaderTest):
    name = "ETag"
    inputs = [b'W/"foo"']
    expected_out = (True, "foo")
    expected_err = []  # type: ignore


class UnquotedETagTest(headers.HeaderTest):
    name = "ETag"
    inputs = [b"foo"]
    expected_out = (False, "foo")
    expected_err = [headers.BAD_SYNTAX]
