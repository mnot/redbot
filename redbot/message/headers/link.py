#!/usr/bin/env python

import re

from redbot.message import headers
from redbot.speak import Note, categories, levels
from redbot.syntax import rfc3986, rfc7231

class link(headers.HttpHeader):
    canonical_name = "Link"
    description = """\
The `Link` header field allows structured links to be described. A link can be viewed as a
statement of the form "[context IRI] has a [relation type] resource at [target IRI], which has
[target attributes]."""
    reference = "%s#header.link" % headers.rfc5988
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
        if 'rel' in param_dict: # relation_types
            pass # TODO: check relation type
        if 'rev' in param_dict:
            add_note(LINK_REV, link=link, rev=param_dict['rev'])
        if 'anchor' in param_dict: # URI-Reference
            if not re.match(r"^\s*%s\s*$" % rfc3986.URI_reference,
                            param_dict['anchor'], re.VERBOSE):
                add_note(LINK_BAD_ANCHOR, link=link, anchor=param_dict['anchor'])
        # TODO: check media-type in 'type'
        # TODO: check language tag in 'hreflang'
        return link, param_dict



class LINK_REV(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = "The 'rev' parameter on the Link header is deprecated."
    text = """\
The `Link` header, defined by [RFC5988](http://tools.ietf.org/html/rfc5988#section-5), uses the
`rel` parameter to communicate the type of a link. `rev` is deprecated by that specification
because it is often confusing.

Use `rel` and an appropriate relation."""

class LINK_BAD_ANCHOR(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = "The 'anchor' parameter on the %(link)s Link header isn't a URI."
    text = """\
The `Link` header, defined by [RFC5988](http://tools.ietf.org/html/rfc5988#section-5), uses the
`anchor` parameter to define the context URI for the link.

This parameter can be an absolute or relative URI; however, `%(anchor)s` is neither."""



class BasicLinkTest(headers.HeaderTest):
    name = 'Link'
    inputs = ['<http://www.example.com/>; rel=example']
    expected_out = [('http://www.example.com/', {'rel': 'example'})]
    expected_err = []

class QuotedLinkTest(headers.HeaderTest):
    name = 'Link'
    inputs = ['"http://www.example.com/"; rel=example']
    expected_out = [('http://www.example.com/', {'rel': 'example'})]
    expected_err = [headers.BAD_SYNTAX]

class QuotedRelationLinkTest(headers.HeaderTest):
    name = 'Link'
    inputs = ['<http://www.example.com/>; rel="example"']
    expected_out = [('http://www.example.com/', {'rel': 'example'})]
    expected_err = []

class RelativeLinkTest(headers.HeaderTest):
    name = 'Link'
    inputs = ['</foo>; rel="example"']
    expected_out = [('/foo', {'rel': 'example'})]
    expected_err = []

class RepeatingRelationLinkTest(headers.HeaderTest):
    name = 'Link'
    inputs = ['</foo>; rel="example"; rel="another"']
    expected_out = [('/foo', {'rel': 'another'})]
    expected_err = [headers.PARAM_REPEATS]

class RevLinkTest(headers.HeaderTest):
    name = 'Link'
    inputs = ['</foo>; rev="bar"']
    expected_out = [('/foo', {'rev': 'bar'})]
    expected_err = [LINK_REV]

class BadAnchorLinkTest(headers.HeaderTest):
    name = 'Link'
    inputs = ['</foo>; rel="bar"; anchor="{blah}"']
    expected_out = [('/foo', {'rel': 'bar', 'anchor': '{blah}'})]
    expected_err = [LINK_BAD_ANCHOR]
