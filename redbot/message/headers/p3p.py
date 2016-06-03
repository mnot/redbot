#!/usr/bin/env python

import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


description = u"""\
The `P3P` header field allows a server to describe its privacy policy in a
machine-readable way. It has been deprecated, because client support was poor.
"""

reference = u"http://www.w3.org/TR/P3P/#syntax_ext"


@rh.ResponseOrPutHeader
@rh.GenericHeaderSyntax
def parse(subject, value, red):
    # See #55
    pass

def join(subject, values, red):
    return values