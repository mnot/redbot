#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax

description = u"""\
The `Retry-After` header can be used with a `503 Service Unavailable` response to indicate how long
the service is expected to be unavailable to the requesting client.

The value of this field can be either a date or an integer number of seconds."""


@rh.GenericHeaderSyntax
@rh.CheckFieldSyntax(
  r"(?:%s|%s)" % (syntax.DIGITS, syntax.DATE), rh.rfc2616 % "section-14.37")
def parse(subject, value, red):
    pass
    
@rh.SingleFieldValue
def join(subject, values, red):
    return values