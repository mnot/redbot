#!/usr/bin/env python

import re
import redbot.message.headers as headers
from redbot.speak import Note, categories, levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc3986, rfc7231

class link(HttpHeader):
  canonical_name = u"Link"
  description = u"""\
The `Link` header field allows structured links to be described. A link can be viewed as a statement of the form "[context IRI] has a [relation type] resource at [target IRI], which has [target attributes]."
"""
  reference = u"%s#header.link" % headers.rfc5988
  syntax = r'(?:<%s>(?:\s*;\s*%s)*)' % (rfc3986.URI_reference, rfc7231.parameter)
  list_header = True
  deprecated = False
  valid_in_requests = True
  valid_in_responses = True

  def parse(self, field_value, add_note):
    try:
        link, param_str = field_value.split(";", 1)
    except ValueError:
        link, param_str = field_value, ''
    link = link.strip()[1:-1] # trim the angle brackets
    param_dict = headers.parse_params(param_str, add_note, 
      ['rel', 'rev', 'anchor', 'hreflang', 'type', 'media'])
    if param_dict.has_key('rel'): # relation_types
        pass # TODO: check relation type
    if param_dict.has_key('rev'):
        add_note(LINK_REV, link=link, rev=param_dict['rev'])
    if param_dict.has_key('anchor'): # URI-Reference
        if not re.match(r"^\s*%s\s*$" % rfc3986.URI_reference, 
                        param_dict['anchor'], re.VERBOSE):
            add_note(LINK_BAD_ANCHOR, link=link, anchor=param_dict['anchor'])
    # TODO: check media-type in 'type'
    # TODO: check language tag in 'hreflang'            
    return link, param_dict



class LINK_REV(Note):
    category = categories.GENERAL
    level=levels.WARN
    summary = u"The 'rev' parameter on the Link header is deprecated."
    text = u"""\
The `Link` header, defined by [RFC5988](http://tools.ietf.org/html/rfc5988#section-5), uses the
`rel` parameter to communicate the type of a link. `rev` is deprecated by that specification
because it is often confusing.

Use `rel` and an appropriate relation."""

class LINK_BAD_ANCHOR(Note):
    category = categories.GENERAL
    level=levels.WARN
    summary = u"The 'anchor' parameter on the %(link)s Link header isn't a URI."
    text = u"""\
The `Link` header, defined by [RFC5988](http://tools.ietf.org/html/rfc5988#section-5), uses the
`anchor` parameter to define the context URI for the link.

This parameter can be an absolute or relative URI; however, `%(anchor)s` is neither."""


    
class BasicLinkTest(HeaderTest):
    name = 'Link'
    inputs = ['<http://www.example.com/>; rel=example']
    expected_out = [('http://www.example.com/', {'rel': 'example'})]
    expected_err = []

class QuotedLinkTest(HeaderTest):
    name = 'Link'
    inputs = ['"http://www.example.com/"; rel=example']
    expected_out = [('http://www.example.com/', {'rel': 'example'})]
    expected_err = [headers.BAD_SYNTAX]

class QuotedRelationLinkTest(HeaderTest):
    name = 'Link'
    inputs = ['<http://www.example.com/>; rel="example"']
    expected_out = [('http://www.example.com/', {'rel': 'example'})]
    expected_err = []    

class RelativeLinkTest(HeaderTest):
    name = 'Link'
    inputs = ['</foo>; rel="example"']
    expected_out = [('/foo', {'rel': 'example'})]
    expected_err = []    
    
class RepeatingRelationLinkTest(HeaderTest):
    name = 'Link'
    inputs = ['</foo>; rel="example"; rel="another"']
    expected_out = [('/foo', {'rel': 'another'})]
    expected_err = [headers.PARAM_REPEATS]

class RevLinkTest(HeaderTest):
    name = 'Link'
    inputs = ['</foo>; rev="bar"']
    expected_out = [('/foo', {'rev': 'bar'})]
    expected_err = [LINK_REV]

class BadAnchorLinkTest(HeaderTest):
    name = 'Link'
    inputs = ['</foo>; rel="bar"; anchor="{blah}"']
    expected_out = [('/foo', {'rel': 'bar', 'anchor': '{blah}'})]
    expected_err = [LINK_BAD_ANCHOR]
