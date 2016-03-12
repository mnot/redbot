#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


description = u"""\
The `X-Cache` header is used by some caches to indicate whether or not the response was served from
cache; if it contains `HIT`, it was."""


@rh.GenericHeaderSyntax
def parse(subject, value, red):
    # see #63
    return value
    
def join(subject, values, red):
    return values