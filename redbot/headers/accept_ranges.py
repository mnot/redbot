#!/usr/bin/env python

__author__ = "Mark Nottingham <mnot@mnot.net>"
__copyright__ = """\
Copyright (c) 2008-2011 Mark Nottingham

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

from cgi import escape as e

import redbot.speak as rs
import redbot.headers as rh
import redbot.http_syntax as syntax


@rh.GenericHeaderSyntax
def parse(name, values, red):
    values = [v.lower() for v in values]
    for value in values:
        if value not in ['bytes', 'none']:
            red.set_message(name, rs.UNKNOWN_RANGE)
            break
    return values

class AcceptRangeTest(rh.HeaderTest):
    name = 'Accept-Ranges'
    inputs = ['bytes']
    expected_out = (['bytes'])
    expected_err = []

class NoneAcceptRangeTest(rh.HeaderTest):
    name = 'Accept-Ranges'
    inputs = ['none']
    expected_out = (['none'])
    expected_err = []

class BothAcceptRangeTest(rh.HeaderTest):
    name = 'Accept-Ranges'
    inputs = ['bytes, none']
    expected_out = (['bytes', 'none'])
    expected_err = []
    
class BadAcceptRangeTest(rh.HeaderTest):
    name = 'Accept-Ranges'
    inputs = ['foo']
    expected_out = (['foo'])
    expected_err = [rs.UNKNOWN_RANGE] 
    
class CaseAcceptRangeTest(rh.HeaderTest):
    name = 'Accept-Ranges'
    inputs = ['Bytes, NONE']
    expected_out = (['bytes', 'none'])
    expected_err = []
