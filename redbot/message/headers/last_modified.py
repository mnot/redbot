#!/usr/bin/env python


import redbot.message.headers as headers
from redbot.speak import Note, c as categories, l as levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7232

class last_modified(HttpHeader):
  canonical_name = u"Last-Modified"
  description = u"""\
The `Last-Modified` header indicates the time that the origin server believes the
representation was last modified."""
  reference = u"%s#header.last_modified" % rfc7232.SPEC_URL
  syntax = rfc7232.Last_Modified
  list_header = False
  deprecated = False
  valid_in_requests = False
  valid_in_responses = True

  def parse(self, field_value, add_note):
      try:
          date = headers.parse_date(value)
      except ValueError:
          add_note(subject, rs.BAD_DATE_SYNTAX)
          return None
      return date



class BasicLMTest(rh.HeaderTest):
    name = 'Last-Modified'
    inputs = ['Mon, 04 Jul 2011 09:08:06 GMT']
    expected_out = 1309770486
    expected_err = []

class BadLMTest(rh.HeaderTest):
    name = 'Last-Modified'
    inputs = ['0']
    expected_out = None
    expected_err = [rs.BAD_DATE_SYNTAX]

class BlankLMTest(rh.HeaderTest):
    name = 'Last-Modified'
    inputs = ['']
    expected_out = None
    expected_err = [rs.BAD_DATE_SYNTAX]