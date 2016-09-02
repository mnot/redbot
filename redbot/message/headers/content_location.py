#!/usr/bin/env python


import redbot.message.headers as headers
from redbot.speak import Note, categories, levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7231

class content_location(HttpHeader):
  canonical_name = u"Content-Location"
  description = u"""\
The `Content-Location` header can used to supply an address for the
representation when it is accessible from a location separate from the request
URI."""
  reference = u"%s#header.content_location" % rfc7231.SPEC_URL
  syntax = rfc7231.Content_Location
  list_header = False
  deprecated = False
  valid_in_requests = False
  valid_in_responses = True
