#!/usr/bin/env python

import redbot.message.headers as headers
from redbot.speak import Note, c as categories, l as levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7231

class content_base(HttpHeader):
  canonical_name = u"Content-Base"
  description = u"""\
The `Content-Base` header field established the base URI of the message. It has been
deprecated, because it was not implemented widely.
"""
  reference = u"%s#header.content_base" % rfc7231.SPEC_URL # FIXME
#  syntax = rfc7231.Content_Base   FIXME
  list_header = False
  deprecated = True
  valid_in_requests = True
  valid_in_responses = True
