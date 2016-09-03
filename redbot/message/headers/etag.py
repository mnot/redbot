#!/usr/bin/env python


import redbot.message.headers as headers
from redbot.speak import Note, categories, levels
from redbot.message.headers import HttpHeader, HeaderTest, BAD_SYNTAX
from redbot.syntax import rfc7232

class etag(HttpHeader):
  canonical_name = u"ETag"
  description = u"""\
The `ETag` header provides an opaque identifier for the representation."""
  reference = u"%s#header.etag" % rfc7232.SPEC_URL
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


        
class ETagTest(HeaderTest):
    name = 'ETag'
    inputs = ['"foo"']
    expected_out = (False, 'foo')
    expected_err = []

class WeakETagTest(HeaderTest):
    name = 'ETag'
    inputs = ['W/"foo"']
    expected_out = (True, 'foo')
    expected_err = []

class UnquotedETagTest(HeaderTest):
    name = 'ETag'
    inputs = ['foo']
    expected_out = (False, 'foo')
    expected_err = [BAD_SYNTAX]
