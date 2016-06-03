#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax

description = u"""\
The `Warning` header is used to carry additional information about the status or transformation of
a message that might not be reflected in it. This information is typically used to warn about
possible incorrectness introduced by caching operations or transformations applied to the body of
the message."""

reference = u"%s#header.warning" % rs.rfc7234

@rh.GenericHeaderSyntax
@rh.ResponseHeader
def parse(subject, value, red):
    # See #58
    return value
    
def join(subject, values, red):
    return values