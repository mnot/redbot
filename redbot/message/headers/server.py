#!/usr/bin/env python


import redbot.message.headers as headers
from redbot.speak import Note, c as categories, l as levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7231

class server(HttpHeader):
  canonical_name = u"Server"
  description = u"""\
The `Server` header contains information about the software used by the origin server to handle the
request."""
  reference = u"%s#header.server" % rfc7231.SPEC_URL
  syntax = rfc7231.Server
  list_header = True
  deprecated = False
  valid_in_requests = False
  valid_in_responses = True
