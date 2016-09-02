#!/usr/bin/env python



import redbot.message.headers as headers
from redbot.speak import Note, categories, levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7234

class tcn(HttpHeader):
  canonical_name = u"TCN"
  reference = u"https://tools.ietf.org/html/rfc2295"
  list_header = False
  deprecated = False
  valid_in_requests = False
  valid_in_responses = True
