#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


description = u"""\
The `ETag` header provides an opaque identifier for the representation."""

    
    
@rh.GenericHeaderSyntax
@rh.CheckFieldSyntax(
  r'\*|(?:W/)?%s' % syntax.QUOTED_STRING, rh.rfc2616 % "section-14.19")
def parse(subject, value, red):
    if value[:2] == 'W/':
        return (True, rh.unquote_string(value[2:]))
    else:
        return (False, rh.unquote_string(value))

@rh.SingleFieldValue
def join(subject, values, red):
    return values[-1]
        
class ETagTest(rh.HeaderTest):
    name = 'ETag'
    inputs = ['"foo"']
    expected_out = (False, 'foo')
    expected_err = []

class WeakETagTest(rh.HeaderTest):
    name = 'ETag'
    inputs = ['W/"foo"']
    expected_out = (True, 'foo')
    expected_err = []

class UnquotedETagTest(rh.HeaderTest):
    name = 'ETag'
    inputs = ['foo']
    expected_out = None
    expected_err = [rs.BAD_SYNTAX]
