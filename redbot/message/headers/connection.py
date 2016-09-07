#!/usr/bin/env python


from redbot.message import headers
from redbot.speak import Note, categories, levels
from redbot.syntax import rfc7230


class connection(headers.HttpHeader):
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


class ConnectionTest(headers.HeaderTest):
    name = 'Connection'
    inputs = ['close']
    expected_out = ['close']
    expected_err = []