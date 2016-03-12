#!/usr/bin/env python




import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


@rh.GenericHeaderSyntax
def parse(subject, value, red):
    # See #55
    pass

def join(subject, values, red):
    return values