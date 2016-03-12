#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax

description = u"""\
HTTP is not a MIME-compliant protocol. However, HTTP/1.1 messages can include a single MIME-Version
header field to indicate what version of the MIME protocol was used to construct the message. Use
of the MIME-Version header field indicates that the message is in full compliance with the MIME
protocol."""


def parse(subject, value, red):
    red.add_note(subject, rs.MIME_VERSION)
    return value
    
def join(subject, values, red):
    return values