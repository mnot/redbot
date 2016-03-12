#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax

description = u"""\
The `Date` header represents the time when the message was generated, regardless of caching that
happened since.

It is used by caches as input to expiration calculations, and to detect clock drift."""


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

class BasicDateTest(rh.HeaderTest):
    name = 'Date'
    inputs = ['Mon, 04 Jul 2011 09:08:06 GMT']
    expected_out = 1309770486
    expected_err = []

class BadDateTest(rh.HeaderTest):
    name = 'Date'
    inputs = ['0']
    expected_out = None
    expected_err = [rs.BAD_DATE_SYNTAX]

class BlankDateTest(rh.HeaderTest):
    name = 'Date'
    inputs = ['']
    expected_out = None
    expected_err = [rs.BAD_DATE_SYNTAX]
