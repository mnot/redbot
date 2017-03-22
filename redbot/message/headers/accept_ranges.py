#!/usr/bin/env python

from redbot.message import headers
from redbot.speak import Note, categories, levels
from redbot.syntax import rfc7233
from redbot.type import AddNoteMethodType


class accept_ranges(headers.HttpHeader):
    canonical_name = "Accept-Ranges"
    description = """\
The `Accept-Ranges` header allows the server to indicate that it accepts range requests for a
resource."""
    reference = "%s#header.accept-ranges" % rfc7233.SPEC_URL
    syntax = rfc7233.Accept_Ranges
    list_header = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        field_value = field_value.lower()
        if field_value not in ['bytes', 'none']:
            add_note(UNKNOWN_RANGE, range=field_value)
        return field_value


class UNKNOWN_RANGE(Note):
    category = categories.RANGE
    level = levels.WARN
    summary = "%(response)s advertises support for non-standard range-units."
    text = """\
The `Accept-Ranges` response header tells clients what `range-unit`s a resource is willing to
process in future requests. HTTP only defines two: `bytes` and `none`.

Clients who don't know about the non-standard range-unit will not be able to use it."""


class AcceptRangeTest(headers.HeaderTest):
    name = 'Accept-Ranges'
    inputs = [b'bytes']
    expected_out = (['bytes'])
    expected_err = [] # type: ignore

class NoneAcceptRangeTest(headers.HeaderTest):
    name = 'Accept-Ranges'
    inputs = [b'none']
    expected_out = (['none'])
    expected_err = [] # type: ignore

class BothAcceptRangeTest(headers.HeaderTest):
    name = 'Accept-Ranges'
    inputs = [b'bytes, none']
    expected_out = (['bytes', 'none'])
    expected_err = [] # type: ignore

class BadAcceptRangeTest(headers.HeaderTest):
    name = 'Accept-Ranges'
    inputs = [b'foo']
    expected_out = (['foo'])
    expected_err = [UNKNOWN_RANGE]

class CaseAcceptRangeTest(headers.HeaderTest):
    name = 'Accept-Ranges'
    inputs = [b'Bytes, NONE']
    expected_out = (['bytes', 'none'])
    expected_err = [] # type: ignore
