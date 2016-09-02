#!/usr/bin/env python

import redbot.message.headers as headers
from redbot.speak import Note, categories, levels
from redbot.message.headers import HttpHeader, HeaderTest

class x_cache_lookup(HttpHeader):
  canonical_name = u"X-Cache-Lookup"
  description = u"""\
The `X-Cache-Lookup` header is used by some caches to show whether there was a response in cache
for this URL; if it contains `HIT`, it was in cache (but not necessarily used). """
  list_header = True
  deprecated = False
  valid_in_requests = False
  valid_in_responses = True