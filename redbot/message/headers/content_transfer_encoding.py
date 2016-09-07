#!/usr/bin/env python

from redbot.message import headers
from redbot.speak import Note, categories, levels
from redbot.syntax import rfc7234

class content_transfer_encoding(headers.HttpHeader):
  canonical_name = u"Content-Transfer-Encoding"
  description = u"""\
The `Content-Transfer-Encoding` isn't part of HTTP, but it is used in MIME protocols in a manner analogous to `Transfer-Encoding`.
"""
  reference = u"https://tools.ietf.org/html/rfc2616#section-19.4.5"
  list_header = False
  deprecated = True
  valid_in_requests = True
  valid_in_responses = True
  no_coverage = True