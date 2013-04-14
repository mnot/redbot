#!/usr/bin/env python

__author__ = "Mark Nottingham <mnot@mnot.net>"
__copyright__ = """\
Copyright (c) 2008-2012 Mark Nottingham

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""


import redbot.speak as rs
from redbot.message_check import headers as rh
import redbot.http_syntax as syntax


def parse(subject, value, red):
    try:
        date = rh.parse_date(value)
    except ValueError:
        red.set_message(subject, rs.BAD_DATE_SYNTAX)
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
