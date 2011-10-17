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
@rh.CheckFieldSyntax(syntax.PARAMETER, rh.rfc2616 % "sec-14.9")
def parse(name, values, red):
    directives = set()
    for directive in values:
        try:
            attr, value = directive.split("=", 1)
            value = rh.unquote_string(value)
        except ValueError:
            attr = directive
            value = None
        if attr in ['max-age', 's-maxage']:
            try:
                value = int(value)
            except (ValueError, TypeError):
                red.set_message(name, rs.BAD_CC_SYNTAX, bad_cc_attr=attr)
                continue
        directives.add((attr, value))
    return directives
    
class CacheControlTest(rh.HeaderTest):
    name = 'Cache-Control'
    inputs = ['a=b, c=d', 'e=f', 'g']
    expected_out = (set([('a', 'b'), ('c', 'd'), ('e', 'f'), ('g', None)]))
    expected_err = []

class CacheControlCaseTest(rh.HeaderTest):
    name = 'Cache-Control'
    inputs = ['A=b, c=D']
    expected_out = (set([('a', 'b'), ('c', 'D')]))
    expected_err = []

class CacheControlQuotedTest(rh.HeaderTest):
    name = 'Cache-Control'
    inputs = ['a="b,c", c=d']
    expected_out = (set([('a', 'b,c'), ('c', 'd')]))
    expected_err = []

class CacheControlMaxAgeTest(rh.HeaderTest):
    name = 'Cache-Control'
    inputs = ['max-age=5']
    expected_out = (set([('max-age', 5)]))
    expected_err = []

class CacheControlBadMaxAgeTest(rh.HeaderTest):
    name = 'Cache-Control'
    inputs = ['max-age=foo']
    expected_out = (set([]))
    expected_err = [rs.BAD_CC_SYNTAX]
