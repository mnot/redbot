#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


description = u"""\
The `Keep-Alive` header is completely optional; it is defined primarily because the `keep-alive`
connection token implies that such a header exists, not because anyone actually uses it.

Some implementations (e.g., [Apache](http://httpd.apache.org/)) do generate a `Keep-Alive` header
to convey how many requests they're willing to serve on a single connection, what the connection
timeout is and other information. However, this isn't usually used by clients.

It's safe to remove this header if you wish to save a few bytes in the response."""


@rh.GenericHeaderSyntax
def parse(subject, value, red):
    try:
        attr, attr_val = value.split("=", 1)
        attr_val = rh.unquote_string(attr_val)
    except ValueError:
        attr = value
        attr_val = None
    return (attr.lower(), attr_val)
    
def join(subject, values, red):
    return set(values)