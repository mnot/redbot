#!/usr/bin/env python




import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax

reference = u"https://tools.ietf.org/html/rfc2295"

@rh.ResponseHeader
@rh.GenericHeaderSyntax
def parse(subject, value, red):
    # See #57
    pass
    
def join(subject, values, red):
    return values