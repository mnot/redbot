#!/usr/bin/env python


import redbot.message.headers as headers
from redbot.speak import Note, c as categories, l as levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7234

class pragma(HttpHeader):
  canonical_name = u"Pragma"
  description = u"""\
The `Pragma` header is used to include implementation-specific directives that might apply to any
recipient along the request/response chain.<p> This header is deprecated, in favour of
`Cache-Control`."""
  reference = u"%s#header.pragma" % rfc7234.SPEC_URL
  syntax = rfc7234.Pragma
  list_header = False
  deprecated = True
  valid_in_requests = False
  valid_in_responses = True

  def parse(self, field_value, add_note):
      return field_value.lower()
    
  def evaluate(self, add_note):
      if "no-cache" in values:
          add_note(subject, PRAGMA_NO_CACHE)
      others = [True for v in values if v != "no-cache"]
      if others:
          add_note(subject, PRAGMA_OTHER)
      return set(values)
      
      
class PRAGMA_NO_CACHE(Note):
  category = categories.CACHING
  level = levels.WARN
  summary = u"Pragma: no-cache is a request directive, not a response \
directive."
  text = u"""\
`Pragma` is a very old request header that is sometimes used as a response header, even though this
is not specified behaviour. `Cache-Control: no-cache` is more appropriate."""

class PRAGMA_OTHER(Note):
  category = categories.GENERAL
  level = levels.WARN
  summary = u"""\
The Pragma header is being used in an undefined way."""
  text = u"""\
HTTP only defines `Pragma: no-cache`; other uses of this header are deprecated."""
