#!/usr/bin/env python

import redbot.message.headers as headers
from redbot.speak import Note, categories, levels
from redbot.message.headers import HttpHeader, HeaderTest

class content_base(HttpHeader):
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