#!/usr/bin/env python




import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


@rh.GenericHeaderSyntax
def parse(subject, value, red):
    return value.lower()
    
def join(subject, values, red):
    if 'deny' in values:
        red.add_note(subject, rs.FRAME_OPTIONS_DENY)
    elif 'sameorigin' in values:
        red.add_note(subject, rs.FRAME_OPTIONS_SAMEORIGIN)
    else:
        red.add_note(subject, rs.FRAME_OPTIONS_UNKNOWN)
    return values


class DenyXFOTest(rh.HeaderTest):
    name = 'X-Frame-Options'
    inputs = ['deny']
    expected_out = ['deny']
    expected_err = [rs.FRAME_OPTIONS_DENY]
    
class DenyXFOCaseTest(rh.HeaderTest):
    name = 'X-Frame-Options'
    inputs = ['DENY']
    expected_out = ['deny']
    expected_err = [rs.FRAME_OPTIONS_DENY]
    
class SameOriginXFOTest(rh.HeaderTest):
    name = 'X-Frame-Options'
    inputs = ['sameorigin']
    expected_out = ['sameorigin']
    expected_err = [rs.FRAME_OPTIONS_SAMEORIGIN]

class UnknownXFOTest(rh.HeaderTest):
    name = 'X-Frame-Options'
    inputs = ['foO']
    expected_out = ['foo']
    expected_err = [rs.FRAME_OPTIONS_UNKNOWN]

