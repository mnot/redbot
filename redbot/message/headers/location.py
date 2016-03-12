#!/usr/bin/env python

import re
from urlparse import urljoin

import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax

description = u"""\
The `Location` header is used in `3xx` responses to redirect the recipient to a different location
to complete the request.
        
In `201 Created``` responses, it identifies a newly created resource."""


# The most common problem with Location is a non-absolute URI, 
# so we separate that from the syntax check.
@rh.CheckFieldSyntax(syntax.URI_reference, rh.rfc2616 % "section-14.30")
@rh.ResponseHeader
def parse(subject, value, msg):
    if msg.status_code not in [
        "201", "300", "301", "302", "303", "305", "307", "308"
    ]:
        msg.add_note(subject, rs.LOCATION_UNDEFINED)
    if not re.match(r"^\s*%s\s*$" % syntax.URI, value, re.VERBOSE):
        msg.add_note(subject, rs.LOCATION_NOT_ABSOLUTE,
                        full_uri=urljoin(msg.base_uri, value))
    return value

@rh.SingleFieldValue
def join(subject, values, msg):
    return values[-1]