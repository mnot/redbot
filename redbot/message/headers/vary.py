#!/usr/bin/env python




import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


@rh.GenericHeaderSyntax
@rh.ResponseHeader
@rh.CheckFieldSyntax(syntax.TOKEN, rh.rfc2616 % "section-14.44")
def parse(subject, value, red):
    return value.lower()
    
def join(subject, values, red):
    return set(values)