#!/usr/bin/env python

from redbot.message import headers
from redbot.speak import Note, categories, levels


class p3p(headers.HttpHeader):
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
  no_coverage = True
