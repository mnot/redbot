#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


description = u"""\
The `Vary` header indicates the set of request headers that determines whether a cache is permitted
to use the response to reply to a subsequent request without validation.

In uncacheable or stale responses, the Vary field value advises the user agent about the criteria
that were used to select the representation."""

reference = u"%s#header.vary" % rs.rfc7231


@rh.GenericHeaderSyntax
@rh.ResponseHeader
@rh.CheckFieldSyntax(syntax.TOKEN, rh.rfc2616 % "section-14.44")
def parse(subject, value, red):
    return value.lower()
    
def join(subject, values, red):
    return set(values)