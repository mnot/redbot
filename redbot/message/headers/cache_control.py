#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax

description = u"""\
The `Cache-Control` header is used to specify directives that must be obeyed by all caches along
the request/response chain. Cache directives are unidirectional in that the presence of a directive
in a request does not imply that the same directive is in effect in the response."""


@rh.GenericHeaderSyntax
@rh.CheckFieldSyntax(syntax.PARAMETER, rh.rfc2616 % "section-14.9")
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
            red.add_note(subject, rs.BAD_CC_SYNTAX,
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
