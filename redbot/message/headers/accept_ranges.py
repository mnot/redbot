#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


description = u"""\
The `Accept-Ranges` header allows the server to indicate that it accepts range requests for a
resource."""

reference = u"%s#header.accept-ranges" % rs.rfc7233

@rh.GenericHeaderSyntax
@rh.ResponseHeader
def parse(subject, value, red):
    value = value.lower()
    if value not in ['bytes', 'none']:
        red.add_note(subject, rs.UNKNOWN_RANGE, range=value)
    return value
    
def join(subject, values, red):
    return values


class AcceptRangeTest(rh.HeaderTest):
    name = 'Accept-Ranges'
    inputs = ['bytes']
    expected_out = (['bytes'])
    expected_err = []

class NoneAcceptRangeTest(rh.HeaderTest):
    name = 'Accept-Ranges'
    inputs = ['none']
    expected_out = (['none'])
    expected_err = []

class BothAcceptRangeTest(rh.HeaderTest):
    name = 'Accept-Ranges'
    inputs = ['bytes, none']
    expected_out = (['bytes', 'none'])
    expected_err = []
    
class BadAcceptRangeTest(rh.HeaderTest):
    name = 'Accept-Ranges'
    inputs = ['foo']
    expected_out = (['foo'])
    expected_err = [rs.UNKNOWN_RANGE] 
    
class CaseAcceptRangeTest(rh.HeaderTest):
    name = 'Accept-Ranges'
    inputs = ['Bytes, NONE']
    expected_out = (['bytes', 'none'])
    expected_err = []
