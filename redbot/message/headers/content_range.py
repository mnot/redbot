#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


description = u"""\
The `Content-Range` header is sent with a partial body to specify where in the full body the
partial body should be applied."""

reference = u"%s#header.content-range" % rs.rfc7233

@rh.ResponseHeader
def parse(subject, value, red):
    # #53: check syntax, values?
    if red.status_code not in ["206", "416"]:
        red.add_note(subject, rs.CONTENT_RANGE_MEANINGLESS)
    return value

@rh.SingleFieldValue    
def join(subject, values, red):
    return values