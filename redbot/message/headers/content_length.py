#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


description = u"""\
The `Content-Length` header indicates the size of the body, in number of bytes. In responses to the
HEAD method, it indicates the size of the body that would have been sent had the request been a GET.

If Content-Length is incorrect, persistent connections will not work, and caches may not store the
response (since they can't be sure if they have the whole response)."""

reference = u"%s#header.content-length" % rs.rfc7230        

@rh.GenericHeaderSyntax
@rh.CheckFieldSyntax(syntax.DIGITS, rh.rfc2616 % "section-14.13")
def parse(subject, value, red):
    return int(value)

@rh.SingleFieldValue
def join(subject, values, red):
    return values[-1]

    
class ContentLengthTest(rh.HeaderTest):
    name = 'Content-Length'
    inputs = ['1']
    expected_out = 1
    expected_err = []

class ContentLengthTextTest(rh.HeaderTest):
    name = 'Content-Length'
    inputs = ['a']
    expected_out = None
    expected_err = [rs.BAD_SYNTAX]

class ContentLengthSemiTest(rh.HeaderTest):
    name = 'Content-Length'
    inputs = ['1;']
    expected_out = None
    expected_err = [rs.BAD_SYNTAX]

class ContentLengthSpaceTest(rh.HeaderTest):
    name = 'Content-Length'
    inputs = [' 1 ']
    expected_out = 1
    expected_err = []

class ContentLengthBigTest(rh.HeaderTest):
    name = 'Content-Length'
    inputs = ['9' * 999]
    expected_out = long('9' * 999)
    expected_err = []
