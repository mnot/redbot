#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


description = u"""\
The `Pragma` header is used to include implementation-specific directives that might apply to any
recipient along the request/response chain.<p> This header is deprecated, in favour of
`Cache-Control`."""

reference = u"%s#header.pragma" % rs.rfc7234


@rh.GenericHeaderSyntax
def parse(subject, value, red):
    return value.lower()
    
def join(subject, values, red):
    if "no-cache" in values:
        red.add_note(subject, rs.PRAGMA_NO_CACHE)
    others = [True for v in values if v != "no-cache"]
    if others:
        red.add_note(subject, rs.PRAGMA_OTHER)
    return set(values)