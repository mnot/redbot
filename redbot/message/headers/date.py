#!/usr/bin/env python

from redbot.message import headers
from redbot.syntax import rfc7231
from redbot.type import AddNoteMethodType


class date(headers.HttpHeader):
    canonical_name = "Date"
    description = """\
The `Date` header represents the time when the message was generated, regardless of caching that
happened since.

It is used by caches as input to expiration calculations, and to detect clock drift."""
    reference = f"{rfc7231.SPEC_URL}#header.date"
    syntax = False  # rfc7231.Date
    list_header = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> int:
        try:
            date_value = headers.parse_date(field_value, add_note)
        except ValueError:
            raise
        return date_value


class BasicDateTest(headers.HeaderTest):
    name = "Date"
    inputs = [b"Mon, 04 Jul 2011 09:08:06 GMT"]
    expected_out = 1309770486


class BadDateTest(headers.HeaderTest):
    name = "Date"
    inputs = [b"0"]
    expected_out = None
    expected_err = [headers.BAD_DATE_SYNTAX]


class BlankDateTest(headers.HeaderTest):
    name = "Date"
    inputs = [b""]
    expected_out = None
    expected_err = [headers.BAD_DATE_SYNTAX]
