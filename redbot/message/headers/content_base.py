#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax

description = u"""\
The `Content-Base` header field established the base URI of the message. It has been
deprecated, because it was not implemented widely.
"""

reference = u"https://tools.ietf.org/html/rfc2616#section-19.6.3"

@rh.DeprecatedHeader(rh.rfc2616 % "section-19.6.3")
@rh.ResponseOrPutHeader
def parse(subject, value, red):
    return value
    
@rh.SingleFieldValue
def join(subject, values, red):
    return values[-1]