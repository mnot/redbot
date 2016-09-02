#!/usr/bin/env python


import redbot.message.headers as headers
from redbot.speak import Note, categories, levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7234

class expires(HttpHeader):
  canonical_name = u"Expires"
  description = u"""\
The `Expires` header gives a time after which the response is considered stale."""
  reference = u"%s#header.expires" % rfc7234.SPEC_URL
  syntax = rfc7234.Expires
  list_header = False
  deprecated = False
  valid_in_requests = False
  valid_in_responses = True

  def parse(self, field_value, add_note):
      try:
          date = headers.parse_date(field_value)
      except ValueError:
          add_note(subject, headers.BAD_DATE_SYNTAX)
          return None
      return date

  def evaluate(self, add_note):
      return values[-1]

    
class BasicExpiresTest(HeaderTest):
    name = 'Expires'
    inputs = ['Mon, 04 Jul 2011 09:08:06 GMT']
    expected_out = 1309770486
    expected_err = []

class BadExpiresTest(HeaderTest):
    name = 'Expires'
    inputs = ['0']
    expected_out = None
    expected_err = [headers.BAD_DATE_SYNTAX]

class BlankExpiresTest(HeaderTest):
    name = 'Expires'
    inputs = ['']
    expected_out = None
    expected_err = [headers.BAD_DATE_SYNTAX]