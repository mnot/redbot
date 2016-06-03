#!/usr/bin/env python




import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax

description = u"""\
The `Content-Transfer-Encoding` isn't part of HTTP, but it is used in MIME protocols in a manner analogous to `Transfer-Encoding`.
"""

reference = u"https://tools.ietf.org/html/rfc2616#section-19.4.5"


@rh.RequestOrResponseHeader
def parse(subject, value, red):
    red.add_note(subject, rs.CONTENT_TRANSFER_ENCODING)
    return value
    
def join(subject, values, red):
    return values