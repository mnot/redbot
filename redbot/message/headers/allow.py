#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


description = u"""\
The `Allow` header advertises the set of methods that are supported by the resource."""

reference = u"%s#header.allow" % rs.rfc7231

@rh.GenericHeaderSyntax
@rh.ResponseHeader
@rh.CheckFieldSyntax(syntax.TOKEN, rh.rfc2616 % "section-14.7")
def parse(subject, value, red):
    return value
    
def join(subject, values, red):
    return values