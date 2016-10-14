#!/usr/bin/env python


from redbot.message import headers
from redbot.speak import Note, categories, levels
from redbot.syntax import rfc7232

class etag(headers.HttpHeader):
    canonical_name = "ETag"
    description = """\
The `ETag` header provides an opaque identifier for the representation."""
    reference = "%s#header.etag" % rfc7232.SPEC_URL
    syntax = rfc7232.ETag
    list_header = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True

    def parse(self, field_value, add_note):
        if field_value[:2] == 'W/':
            return (True, headers.unquote_string(field_value[2:]))
        else:
            return (False, headers.unquote_string(field_value))



class ETagTest(headers.HeaderTest):
    name = 'ETag'
    inputs = ['"foo"']
    expected_out = (False, 'foo')
    expected_err = [] # type: ignore

class WeakETagTest(headers.HeaderTest):
    name = 'ETag'
    inputs = ['W/"foo"']
    expected_out = (True, 'foo')
    expected_err = [] # type: ignore

class UnquotedETagTest(headers.HeaderTest):
    name = 'ETag'
    inputs = ['foo']
    expected_out = (False, 'foo')
    expected_err = [headers.BAD_SYNTAX]
