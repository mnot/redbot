#!/usr/bin/env python

import redbot.message.headers as headers
from redbot.speak import Note, categories, levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7231

class vary(HttpHeader):
  canonical_name = u"Vary"
  description = u"""\
The `Vary` header indicates the set of request headers that determines whether a cache is permitted
to use the response to reply to a subsequent request without validation.

In uncacheable or stale responses, the Vary field value advises the user agent about the criteria
that were used to select the representation."""
  reference = u"%s#header.vary" % rfc7231.SPEC_URL
  syntax = rfc7231.Vary
  list_header = True
  deprecated = False
  valid_in_requests = False
  valid_in_responses = True

  def parse(self, field_value, add_note):
      return field_value.lower()
    
  def evaluate(self, add_note):
      return set(values)