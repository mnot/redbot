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
@rh.SingleFieldValue
@rh.CheckFieldSyntax(
    r'(?:[10](?:\s*;\s*%(PARAMETER)s)*)' % syntax.__dict__, 'http://blogs.msdn.com/b/ieinternals/archive/2011/01/31/controlling-the-internet-explorer-xss-filter-with-the-x-xss-protection-http-header.aspx'
)
def parse(name, values, red):
    try:
        protect, params = values[-1].split(';', 1)
    except ValueError:
        protect, params = values[-1], ""
    protect = int(protect)
    params = rh.parse_params(red, name, params, True)
    if protect == 0:
        red.set_message(name, rs.XSS_PROTECTION_OFF)
    else: # 1
        if params.get('mode', None) == "block":
            red.set_message(name, rs.XSS_PROTECTION_BLOCK)
        else:
            red.set_message(name, rs.XSS_PROTECTION_ON)
    return protect, params

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
