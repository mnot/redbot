#!/usr/bin/env python

import redbot.message.headers as headers
from redbot.speak import Note, categories, levels
from redbot.message.headers import HttpHeader, HeaderTest

class content_md5(HttpHeader):
  canonical_name = u"Content-MD5"
  description = u"""\
The `Content-MD5` header is an MD5 digest of the body, and provides an end-to-end message integrity
check (MIC).

Note that while a MIC is good for detecting accidental modification of the body in transit, it is
not proof against malicious attacks."""
  reference = u"https://tools.ietf.org/html/rfc1864"
  syntax = r"(?: [A-Za-z0-9+/]{22} ={2} )"
  list_header = False
  deprecated = True
  valid_in_requests = True
  valid_in_responses = True


class ContentMD5Test(HeaderTest):
    name = 'Content-MD5'
    inputs = ['Q2hlY2sgSW50ZWdyaXR5IQ==']
    expected_out = 'Q2hlY2sgSW50ZWdyaXR5IQ=='
    expected_err = []