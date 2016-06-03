#!/usr/bin/env python



import re

import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax

description = """\
The `Link` header field allows structured links to be described. A link can be viewed as a statement of the form "[context IRI] has a [relation type] resource at [target IRI], which has [target attributes]."
"""

reference = rs.rfc5988

@rh.GenericHeaderSyntax
@rh.RequestOrResponseHeader
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
        red.add_note(subject, rs.LINK_REV,
                        link=link, rev=param_dict['rev'])
    if param_dict.has_key('anchor'): # URI-Reference
        if not re.match(r"^\s*%s\s*$" % syntax.URI_reference, 
                        param_dict['anchor'], re.VERBOSE):
            red.add_note(subject, rs.LINK_BAD_ANCHOR,
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
