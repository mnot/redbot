#!/usr/bin/env python




import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


def parse(subject, value, red):
    red.add_note(subject, 
                    rs.HEADER_DEPRECATED, 
                    header_name="Content-Base",
                    ref=rh.rfc2616 % "section-19.6.3"
    )
    return value
    
@rh.SingleFieldValue
def join(subject, values, red):
    return values[-1]