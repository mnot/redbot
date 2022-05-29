#!/usr/bin/env python


from redbot.message import headers
from redbot.syntax import rfc7232
from redbot.type import AddNoteMethodType


class last_modified(headers.HttpHeader):
    canonical_name = "Last-Modified"
    description = """\
The `Last-Modified` header indicates the time that the origin server believes the
representation was last modified."""
    reference = f"{rfc7232.SPEC_URL}#header.last_modified"
    syntax = False  # rfc7232.Last_Modified
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> int:
        try:
            date = headers.parse_date(field_value, add_note)
        except ValueError:
            raise
        return date


class BasicLMTest(headers.HeaderTest):
    name = "Last-Modified"
    inputs = [b"Mon, 04 Jul 2011 09:08:06 GMT"]
    expected_out = 1309770486


class BadLMTest(headers.HeaderTest):
    name = "Last-Modified"
    inputs = [b"0"]
    expected_out = None
    expected_err = [headers.BAD_DATE_SYNTAX]


class BlankLMTest(headers.HeaderTest):
    name = "Last-Modified"
    inputs = [b""]
    expected_out = None
    expected_err = [headers.BAD_DATE_SYNTAX]
