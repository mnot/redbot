#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


description = u"""\
The `Last-Modified` header indicates the time that the origin server believes the
representation was last modified."""

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


class BasicLMTest(rh.HeaderTest):
    name = 'Last-Modified'
    inputs = ['Mon, 04 Jul 2011 09:08:06 GMT']
    expected_out = 1309770486
    expected_err = []

class BadLMTest(rh.HeaderTest):
    name = 'Last-Modified'
    inputs = ['0']
    expected_out = None
    expected_err = [rs.BAD_DATE_SYNTAX]

class BlankLMTest(rh.HeaderTest):
    name = 'Last-Modified'
    inputs = ['']
    expected_out = None
    expected_err = [rs.BAD_DATE_SYNTAX]