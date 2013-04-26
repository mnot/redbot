#!/usr/bin/env python

__author__ = "Mark Nottingham <mnot@mnot.net>"
__copyright__ = """\
Copyright (c) 2008-2013 Mark Nottingham

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
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


@rh.GenericHeaderSyntax
@rh.CheckFieldSyntax(
    r'(?:[10](?:\s*;\s*%(PARAMETER)s)*)' % syntax.__dict__, 'http://blogs.msdn.com/b/ieinternals/archive/2011/01/31/controlling-the-internet-explorer-xss-filter-with-the-x-xss-protection-http-header.aspx'
)
def parse(subject, value, red):
    try:
        protect, param_str = value.split(';', 1)
    except ValueError:
        protect, param_str = value, ""
    protect = int(protect)
    params = rh.parse_params(red, subject, param_str, True)
    if protect == 0:
        red.add_note(subject, rs.XSS_PROTECTION_OFF)
    else: # 1
        if params.get('mode', None) == "block":
            red.add_note(subject, rs.XSS_PROTECTION_BLOCK)
        else:
            red.add_note(subject, rs.XSS_PROTECTION_ON)
    return protect, params

@rh.SingleFieldValue
def join(subject, values, red):
    return values[-1]


class OneXXSSTest(rh.HeaderTest):
    name = 'X-XSS-Protection'
    inputs = ['1']
    expected_out = (1, {})
    expected_err = [rs.XSS_PROTECTION_ON]

class ZeroXXSSTest(rh.HeaderTest):
    name = 'X-XSS-Protection'
    inputs = ['0']
    expected_out = (0, {})
    expected_err = [rs.XSS_PROTECTION_OFF]

class OneBlockXXSSTest(rh.HeaderTest):
    name = 'X-XSS-Protection'
    inputs = ['1; mode=block']
    expected_out = (1, {'mode': 'block'})
    expected_err = [rs.XSS_PROTECTION_BLOCK]
    
class BadXXSSTest(rh.HeaderTest):
    name = 'X-XSS-Protection'
    inputs = ['foo']
    expected_out = None
    expected_err = [rs.BAD_SYNTAX]
