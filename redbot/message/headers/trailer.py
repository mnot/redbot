#!/usr/bin/env python


import redbot.message.headers as headers
from redbot.speak import Note, categories, levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7230

class trailer(HttpHeader):
  canonical_name = u"Trailer"
  description = u"""\
The `Trailer` header indicates that the given set of header fields will be
present in the trailer of the message, after the body."""
  reference = u"%s#header.trailer" % rfc7230.SPEC_URL
  syntax = rfc7230.Trailer
  list_header = True
  deprecated = False
  valid_in_requests = True
  valid_in_responses = True
