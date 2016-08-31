#!/usr/bin/env python

import redbot.message.headers as headers
from redbot.speak import Note, c as categories, l as levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7230

class upgrade(HttpHeader):
  canonical_name = u"Upgrade"
  description = u"""\
The `Upgrade` header allows the client to specify what additional communication
protocols it supports and would like to use if the server finds it appropriate
to switch protocols. Servers use it to confirm upgrade to a specific
protocol."""
  reference = u"%s#header.upgrade" % rfc7230.SPEC_URL
  syntax = rfc7234.Upgrade
  list_header = True
  deprecated = False
  valid_in_requests = True
  valid_in_responses = True
