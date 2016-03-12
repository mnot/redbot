#!/usr/bin/env python




import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


def parse(subject, value, red):
    # TODO: constrain value, tests
    return value
    
@rh.SingleFieldValue
def join(subject, values, red):
    return values[-1]