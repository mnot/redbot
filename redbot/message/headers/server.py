#!/usr/bin/env python




import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax

@rh.ResponseHeader
def parse(subject, value, red):
    # TODO: check syntax, flag servers?
    pass
    
def join(subject, values, red):
    return values