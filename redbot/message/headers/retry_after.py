#!/usr/bin/env python




import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


@rh.GenericHeaderSyntax
@rh.CheckFieldSyntax(
  r"(?:%s|%s)" % (syntax.DIGITS, syntax.DATE), rh.rfc2616 % "section-14.37")
def parse(subject, value, red):
    pass
    
@rh.SingleFieldValue
def join(subject, values, red):
    return values