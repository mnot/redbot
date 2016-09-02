#!/usr/bin/env python


import redbot.message.headers as headers
from redbot.speak import Note, categories, levels
from redbot.message.headers import HttpHeader, HeaderTest

class set_cookie2(HttpHeader):
  canonical_name = u"Set-Cookie2"
  description = u"""\
The `Set-Cookie2` header has been deprecated; use `Set-Cookie` instead."""
  reference = headers.rfc6265
  list_header = True
  deprecated = True
  valid_in_requests = False
  valid_in_responses = True
  no_coverage = True