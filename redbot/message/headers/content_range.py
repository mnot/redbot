#!/usr/bin/env python

import redbot.message.headers as headers
from redbot.speak import Note, c as categories, l as levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7233

class content_range(HttpHeader):
  canonical_name = u"Content-Range"
  description = u"""\
The `Content-Range` header is sent with a partial body to specify where in the full body the
partial body should be applied."""
  reference = u"%s#header.content_range" % rfc7233.SPEC_URL
  syntax = rfc7230.Content_Range
  list_header = False
  deprecated = False
  valid_in_requests = False
  valid_in_responses = True

  def parse(self, field_value, add_note):
      # #53: check syntax, values?
      if red.status_code not in ["206", "416"]:
          add_note(subject, CONTENT_RANGE_MEANINGLESS)
      return value


class CONTENT_RANGE_MEANINGLESS(Note):
    category = categories.RANGE
    level = levels.WARN
    summary = u"%(response)s shouldn't have a Content-Range header."
    text = u"""\
HTTP only defines meaning for the `Content-Range` header in responses with a `206 Partial Content`
or `416 Requested Range Not Satisfiable` status code.

Putting a `Content-Range` header in this response may confuse caches and clients."""
