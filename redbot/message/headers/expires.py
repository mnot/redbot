#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax

description = u"""\
The `Expires` header gives a time after which the response is considered stale."""

reference = u"%s#header.expires" % rs.rfc7234


def parse(subject, value, red):
    try:
        date = rh.parse_date(value)
    except ValueError:
        red.add_note(subject, rs.BAD_DATE_SYNTAX)
        return None
    return date
    
@rh.SingleFieldValue
def join(subject, values, red):
    return values[-1]

    
class BasicExpiresTest(rh.HeaderTest):
    name = 'Expires'
    inputs = ['Mon, 04 Jul 2011 09:08:06 GMT']
    expected_out = 1309770486
    expected_err = []

class BadExpiresTest(rh.HeaderTest):
    name = 'Expires'
    inputs = ['0']
    expected_out = None
    expected_err = [rs.BAD_DATE_SYNTAX]

class BlankExpiresTest(rh.HeaderTest):
    name = 'Expires'
    inputs = ['']
    expected_out = None
    expected_err = [rs.BAD_DATE_SYNTAX]