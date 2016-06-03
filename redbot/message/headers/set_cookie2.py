#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax

description = u"""\
The `Set-Cookie2` header has been deprecated; use `Set-Cookie` instead."""

reference = rs.rfc6265


@rh.ResponseHeader
def parse(subject, value, red):
    red.add_note(subject, 
                    rs.HEADER_DEPRECATED, 
                    header_name="Set-Cookie2",
                    ref=rh.rfc6265 % "section-9.4"
    )
    return value
    
@rh.SingleFieldValue
def join(subject, values, red):
    return values[-1]