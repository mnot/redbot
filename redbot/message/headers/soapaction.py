#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


description = u"""\
The `SOAPAction` header is used by SOAP, which isn't really HTTP. Stop it.
"""

reference = u"http://www.w3.org/TR/2000/NOTE-SOAP-20000508/#_Toc478383528"


@rh.RequestHeader
def parse(subject, value, red):
    return value
    
@rh.SingleFieldValue
def join(subject, values, red):
    return values[-1]