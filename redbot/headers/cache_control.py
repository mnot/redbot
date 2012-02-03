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


import redbot.speak as rs
import redbot.headers as rh
import redbot.http_syntax as syntax


@rh.GenericHeaderSyntax
@rh.CheckFieldSyntax(syntax.PARAMETER, rh.rfc2616 % "sec-14.9")
def parse(subject, value, red):
    try:
        directive_name, directive_val = value.split("=", 1)
        directive_val = rh.unquote_string(directive_val)
    except ValueError:
        directive_name = value
        directive_val = None
    directive_name = directive_name.lower()
    # TODO: warn on upper-cased directives?
    if directive_name in ['max-age', 's-maxage']:
        try:
            directive_val = int(directive_val)
        except (ValueError, TypeError):
            red.set_message(subject, rs.BAD_CC_SYNTAX,
                            bad_cc_attr=directive_name
            )
            return None
    return (directive_name, directive_val)

def join(subject, values, red):
    return set(values)

    
class CacheControlTest(rh.HeaderTest):
    name = 'Cache-Control'
    inputs = ['a=b, c=d', 'e=f', 'g']
    expected_out = set([('a', 'b'), ('c', 'd'), ('e', 'f'), ('g', None)])
    expected_err = []

class CacheControlCaseTest(rh.HeaderTest):
    name = 'Cache-Control'
    inputs = ['A=b, c=D']
    expected_out = set([('a', 'b'), ('c', 'D')])
    expected_err = []

class CacheControlQuotedTest(rh.HeaderTest):
    name = 'Cache-Control'
    inputs = ['a="b,c", c=d']
    expected_out = set([('a', 'b,c'), ('c', 'd')])
    expected_err = []

class CacheControlMaxAgeTest(rh.HeaderTest):
    name = 'Cache-Control'
    inputs = ['max-age=5']
    expected_out = set([('max-age', 5)])
    expected_err = []

class CacheControlBadMaxAgeTest(rh.HeaderTest):
    name = 'Cache-Control'
    inputs = ['max-age=foo']
    expected_out = set([])
    expected_err = [rs.BAD_CC_SYNTAX]
