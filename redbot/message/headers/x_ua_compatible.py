#!/usr/bin/env python




import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


@rh.GenericHeaderSyntax
@rh.CheckFieldSyntax(
    syntax.PARAMETER,
    "http://msdn.microsoft.com/en-us/library/cc288325(VS.85).aspx")
def parse(subject, value, red):
    try:
        attr, attr_value = value.split("=", 1)
    except ValueError:
        attr = value
        attr_value = None
    return attr, attr_value


def join(subject, values, red):
    directives = {}
    warned = False
    for (attr, attr_value) in values:
        if directives.has_key(attr) and not warned:
            red.add_note(subject, rs.UA_COMPATIBLE_REPEAT)
            warned = True
        directives[attr] = attr_value
    red.add_note(subject, rs.UA_COMPATIBLE)
    return directives
    
class BasicUACTest(rh.HeaderTest):
    name = 'X-UA-Compatible'
    inputs = ['foo=bar']
    expected_out = {"foo": "bar"}
    expected_err = [rs.UA_COMPATIBLE]