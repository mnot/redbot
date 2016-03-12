#!/usr/bin/env python




import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


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