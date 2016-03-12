#!/usr/bin/env python




import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


@rh.GenericHeaderSyntax
def parse(subject, value, red):
    return value

def join(subject, values, red):
    red.add_note(subject, rs.SMART_TAG_NO_WORK)
    return values