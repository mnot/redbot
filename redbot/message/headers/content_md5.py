#!/usr/bin/env python

import redbot.message.headers as headers
from redbot.speak import Note, c as categories, l as levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7231

class content_md5(HttpHeader):
  canonical_name = u"Content-MD5"
  description = u"""\
The `Content-MD5` header is an MD5 digest of the body, and provides an end-to-end message integrity
check (MIC).

Note that while a MIC is good for detecting accidental modification of the body in transit, it is
not proof against malicious attacks."""
  reference = u"%s#header.content_md5" % rfc7231.SPEC_URL
  syntax = rfc7231.Content_MD5
  list_header = False
  deprecated = True
  valid_in_requests = True
  valid_in_responses = True
