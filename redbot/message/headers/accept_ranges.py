#!/usr/bin/env python

import redbot.message.headers as headers
from redbot.speak import Note, categories, levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7233


class accept_ranges(HttpHeader):
    canonical_name = u"Accept-Ranges"
    description = u"""\
The `Accept-Ranges` header allows the server to indicate that it accepts range requests for a
resource."""
    reference = u"%s#header.accept-ranges" % rfc7233.SPEC_URL
    syntax = rfc7233.Accept_Ranges
    list_header = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value, add_note):
        value = field_value.lower()
        if field_value not in ['bytes', 'none']:
            add_note(UNKNOWN_RANGE, range=value)
        return value


class UNKNOWN_RANGE(Note):
    category = categories.RANGE
    level = levels.WARN
    summary = u"%(response)s advertises support for non-standard range-units."
    text = u"""\
The `Accept-Ranges` response header tells clients what `range-unit`s a resource is willing to
process in future requests. HTTP only defines two: `bytes` and `none`.

Clients who don't know about the non-standard range-unit will not be able to use it."""


class AcceptRangeTest(HeaderTest):
    name = 'Accept-Ranges'
    inputs = ['bytes']
    expected_out = (['bytes'])
    expected_err = []

class NoneAcceptRangeTest(HeaderTest):
    name = 'Accept-Ranges'
    inputs = ['none']
    expected_out = (['none'])
    expected_err = []

class BothAcceptRangeTest(HeaderTest):
    name = 'Accept-Ranges'
    inputs = ['bytes, none']
    expected_out = (['bytes', 'none'])
    expected_err = []
    
class BadAcceptRangeTest(HeaderTest):
    name = 'Accept-Ranges'
    inputs = ['foo']
    expected_out = (['foo'])
    expected_err = [UNKNOWN_RANGE]
    
class CaseAcceptRangeTest(HeaderTest):
    name = 'Accept-Ranges'
    inputs = ['Bytes, NONE']
    expected_out = (['bytes', 'none'])
    expected_err = []
