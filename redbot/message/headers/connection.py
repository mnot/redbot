#!/usr/bin/env python


import redbot.message.headers as headers
from redbot.speak import Note, c as categories, l as levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7230

class connection(HttpHeader):
  canonical_name = u"Connection"
  description = u"""\
The `Connection` header allows senders to specify which headers are hop-by-hop; that is, those that
are not forwarded by intermediaries.

It also indicates options that are desired for this particular connection; e.g., `close` means that
it should not be reused."""
  reference = u"%s#header.connection" % rfc7230.SPEC_URL
  syntax = rfc7230.Connection
  list_header = True
  deprecated = False
  valid_in_requests = True
  valid_in_responses = True