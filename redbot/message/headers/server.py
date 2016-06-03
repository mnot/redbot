#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax

description = u"""\
The `Server` header contains information about the software used by the origin server to handle the
request."""

reference = u"%s#header.server" % rs.rfc7231


@rh.ResponseHeader
def parse(subject, value, red):
    # TODO: check syntax, flag servers?
    pass
    
def join(subject, values, red):
    return values