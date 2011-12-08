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
@rh.CheckFieldSyntax(
    syntax.PARAMETER,
    "http://msdn.microsoft.com/en-us/library/cc288325(VS.85).aspx")
def parse(subject, value, red):
    try:
        attr, attr_value = value.split("=", 1)
    except ValueError:
        attr = directive
        attr_value = None
    return attr, attr_value


def join(subject, values, red):
    directives = {}
    warned = False
    for (attr, attr_value) in values:
        if directives.has_key(attr) and not warned:
            red.set_message(subject, rs.UA_COMPATIBLE_REPEAT)
            warned = True
        directives[attr] = attr_value

    uac_list = u"\n".join([u"<li>%s - %s</li>" % (e(k), e(v)) for
                        k, v in values])
    red.set_message(subject, rs.UA_COMPATIBLE, uac_list=uac_list)
    return directives
    
class BasicUACTest(rh.HeaderTest):
    name = 'X-UA-Compatible'
    inputs = ['foo=bar']
    expected_out = {"foo": "bar"}
    expected_err = [rs.UA_COMPATIBLE]