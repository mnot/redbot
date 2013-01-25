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

import re

import redbot.speak as rs
from redbot.message_check import headers as rh
import redbot.http_syntax as syntax


@rh.GenericHeaderSyntax
@rh.CheckFieldSyntax(
    r'(?:<%(URI_reference)s>(?:\s*;\s*%(PARAMETER)s)*)' % syntax.__dict__,
    rh.rfc5988
)
def parse(subject, value, red):
    try:
        link, params = value.split(";", 1)
    except ValueError:
        link, params = value, ''
    link = link[1:-1] # trim the angle brackets
    param_dict = rh.parse_params(red, subject, params, 
      ['rel', 'rev', 'anchor', 'hreflang', 'type', 'media'])
    if param_dict.has_key('rel'): # relation_types
        pass # TODO: check relation type
    if param_dict.has_key('rev'):
        red.set_message(subject, rs.LINK_REV,
                        link=link, rev=param_dict['rev'])
    if param_dict.has_key('anchor'): # URI-Reference
        if not re.match(r"^\s*%s\s*$" % syntax.URI_reference, 
                        param_dict['anchor'], re.VERBOSE):
            red.set_message(subject, rs.LINK_BAD_ANCHOR,
                            link=link,
                            anchor=param_dict['anchor'])
    # TODO: check media-type in 'type'
    # TODO: check language tag in 'hreflang'            
    return link, param_dict
    
def join(subject, values, red):
    return values

    
class BasicLinkTest(rh.HeaderTest):
    name = 'Link'
    inputs = ['<http://www.example.com/>; rel=example']
    expected_out = [('http://www.example.com/', {'rel': 'example'})]
    expected_err = []

class QuotedLinkTest(rh.HeaderTest):
    name = 'Link'
    inputs = ['"http://www.example.com/"; rel=example']
    expected_out = []
    expected_err = [rs.BAD_SYNTAX]

class QuotedRelationLinkTest(rh.HeaderTest):
    name = 'Link'
    inputs = ['<http://www.example.com/>; rel="example"']
    expected_out = [('http://www.example.com/', {'rel': 'example'})]
    expected_err = []    

class RelativeLinkTest(rh.HeaderTest):
    name = 'Link'
    inputs = ['</foo>; rel="example"']
    expected_out = [('/foo', {'rel': 'example'})]
    expected_err = []    
    
class RepeatingRelationLinkTest(rh.HeaderTest):
    name = 'Link'
    inputs = ['</foo>; rel="example"; rel="another"']
    expected_out = [('/foo', {'rel': 'another'})]
    expected_err = [rs.PARAM_REPEATS]

class RevLinkTest(rh.HeaderTest):
    name = 'Link'
    inputs = ['</foo>; rev="bar"']
    expected_out = [('/foo', {'rev': 'bar'})]
    expected_err = [rs.LINK_REV]

class BadAnchorLinkTest(rh.HeaderTest):
    name = 'Link'
    inputs = ['</foo>; rel="bar"; anchor="{blah}"']
    expected_out = [('/foo', {'rel': 'bar', 'anchor': '{blah}'})]
    expected_err = [rs.LINK_BAD_ANCHOR]
