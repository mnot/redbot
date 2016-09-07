#!/usr/bin/env python


from redbot.message import headers
from redbot.speak import Note, categories, levels


class set_cookie2(headers.HttpHeader):
  canonical_name = u"Set-Cookie2"
  description = u"""\
The `Set-Cookie2` header has been deprecated; use `Set-Cookie` instead."""
  reference = headers.rfc6265
  list_header = True
  deprecated = True
  valid_in_requests = False
  valid_in_responses = True
  no_coverage = True