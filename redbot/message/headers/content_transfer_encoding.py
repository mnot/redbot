#!/usr/bin/env python

import redbot.message.headers as headers
from redbot.speak import Note, c as categories, l as levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7234

class content_transfer_encoding(HttpHeader):
  canonical_name = u"Content-Transfer-Encoding"
  description = u"""\
The `Content-Transfer-Encoding` isn't part of HTTP, but it is used in MIME protocols in a manner analogous to `Transfer-Encoding`.
"""
  reference = u"https://tools.ietf.org/html/rfc2616#section-19.4.5"
  list_header = False
  deprecated = True
  valid_in_requests = True
  valid_in_responses = True