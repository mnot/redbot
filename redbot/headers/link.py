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
import re

import redbot.speak as rs
import redbot.headers as rh
import redbot.http_syntax as syntax


@rh.GenericHeaderSyntax
@rh.CheckFieldSyntax(
    r'(?:<%(URI_reference)s>(?:\s*;\s*%(PARAMETER)s)*)' % syntax.__dict__,
    rh.rfc5988
)
def parse(name, values, red):
    try:
        link, params = values[-1].split(";", 1)
    except ValueError:
        link, params = values[-1], ''
    link = link[1:-1] # trim the angle brackets
    param_dict = rh.parse_params(red, name, params, 
      ['rel', 'rev', 'anchor', 'hreflang', 'type', 'media'])
    if param_dict.has_key('rel'): # relation_types
        pass # TODO: check relation type
    if param_dict.has_key('rev'):
        red.set_message(name, rs.LINK_REV,
                        link=e(link), rev=e(param_dict['rev']))
    if param_dict.has_key('anchor'): # URI-Reference
        if not re.match(r"^\s*%s\s*$" % syntax.URI_reference, 
                        param_dict['anchor'], re.VERBOSE):
            red.set_message(name, rs.LINK_BAD_ANCHOR,
                            link=e(link),
                            anchor=e(param_dict['anchor']))
    # TODO: check media-type in 'type'
    # TODO: check language tag in 'hreflang'            
    return link, param_dict
    

    
class BasicLinkTest(rh.HeaderTest):
    name = 'Link'
    inputs = ['<http://www.example.com/>; rel=example']
    expected_out = ('http://www.example.com/', {'rel': 'example'})
    expected_err = []    

class QuotedRelationLinkTest(rh.HeaderTest):
    name = 'Link'
    inputs = ['<http://www.example.com/>; rel="example"']
    expected_out = ('http://www.example.com/', {'rel': 'example'})
    expected_err = []    

class RelativeLinkTest(rh.HeaderTest):
    name = 'Link'
    inputs = ['</foo>; rel="example"']
    expected_out = ('/foo', {'rel': 'example'})
    expected_err = []    
    
class RepeatingRelationLinkTest(rh.HeaderTest):
    name = 'Link'
    inputs = ['</foo>; rel="example"; rel="another"']
    expected_out = ('/foo', {'rel': 'another'})
    expected_err = [rs.PARAM_REPEATS]

class BadQuoteLinkTest(rh.HeaderTest):
    name = 'Link'
    inputs = ['"/foo", rel="example"']
    expected_out = None
    expected_err = [rs.BAD_SYNTAX]

class RevLinkTest(rh.HeaderTest):
    name = 'Link'
    inputs = ['</foo>; rev="bar"']
    expected_out = ('/foo', {'rev': 'bar'})
    expected_err = [rs.LINK_REV]

class BadAnchorLinkTest(rh.HeaderTest):
    name = 'Link'
    inputs = ['</foo>; rel="bar"; anchor="{blah}"']
    expected_out = ('/foo', {'rel': 'bar', 'anchor': '{blah}'})
    expected_err = [rs.LINK_BAD_ANCHOR]
