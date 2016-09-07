#!/usr/bin/env python

from redbot.message import headers
from redbot.speak import Note, categories, levels


class content_base(headers.HttpHeader):
  canonical_name = u"Content-Base"
  description = u"""\
The `Content-Base` header field established the base URI of the message. It has been
deprecated, because it was not implemented widely.
"""
  reference = u"https://tools.ietf.org/html/rfc2068#section-14.11"
#  syntax = rfc7231.Content_Base   FIXME
  list_header = False
  deprecated = True
  valid_in_requests = True
  valid_in_responses = True
  no_coverage = True