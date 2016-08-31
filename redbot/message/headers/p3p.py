#!/usr/bin/env python

import redbot.message.headers as headers
from redbot.speak import Note, c as categories, l as levels
from redbot.message.headers import HttpHeader, HeaderTest

class p3p(HttpHeader):
  canonical_name = u"P3P"
  description = u"""\
The `P3P` header field allows a server to describe its privacy policy in a
machine-readable way. It has been deprecated, because client support was poor.
"""
  reference = u"http://www.w3.org/TR/P3P/#syntax_ext"
  list_header = False
  deprecated = True
  valid_in_requests = False
  valid_in_responses = True

