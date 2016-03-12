#!/usr/bin/env python




import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


def parse(subject, value, red):
    red.add_note(subject, rs.MIME_VERSION)
    return value
    
def join(subject, values, red):
    return values