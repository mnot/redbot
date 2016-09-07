#!/usr/bin/env python

from redbot.message import headers
from redbot.speak import Note, categories, levels


class x_cache(headers.HttpHeader):
  canonical_name = u"X-Cache"
  description = u"""\
The `X-Cache` header is used by some caches to indicate whether or not the response was served from
cache; if it contains `HIT`, it was."""
  list_header = True
  deprecated = False
  valid_in_requests = False
  valid_in_responses = True