#!/usr/bin/env python

import redbot.message.headers as headers
from redbot.speak import Note, c as categories, l as levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7235

class proxy_authenticate(HttpHeader):
  canonical_name = u"Proxy-Authenticate"
  description = u"""\
The `Proxy-Authenticate` response header consists of a challenge that indicates the authentication
scheme and parameters applicable to the proxy for this request-target."""
  reference = u"%s#header.proxy-authenticate" % rfc7235.SPEC_URL
  syntax = rfc7235.Proxy_Authenticate
  list_header = True
  deprecated = False
  valid_in_requests = False
  valid_in_responses = True

