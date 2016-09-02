#!/usr/bin/env python

import redbot.message.headers as headers
from redbot.speak import Note, c as categories, l as levels
from redbot.message.headers import HttpHeader, HeaderTest

class x_cache(HttpHeader):
  canonical_name = u"X-Cache"
  description = u"""\
The `X-Cache` header is used by some caches to indicate whether or not the response was served from
cache; if it contains `HIT`, it was."""
  list_header = True
  deprecated = False
  valid_in_requests = False
  valid_in_responses = True