#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


description = u"""\
The `Content-MD5` header is an MD5 digest of the body, and provides an end-to-end message integrity
check (MIC).

Note that while a MIC is good for detecting accidental modification of the body in transit, it is
not proof against malicious attacks."""


def parse(subject, value, red):
    # TODO: constrain value, tests
    return value
    
@rh.SingleFieldValue
def join(subject, values, red):
    return values[-1]