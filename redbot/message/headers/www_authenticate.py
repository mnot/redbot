#!/usr/bin/env python

import redbot.message.headers as headers
from redbot.speak import Note, c as categories, l as levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7235

class www_authenticate(HttpHeader):
  canonical_name = u"WWW-Authenticate"
  description = u"""\
The `WWW-Authenticate` response header consists of at least one challenge that
indicates the authentication scheme(s) and parameters applicable."""
  reference = u"%s#header.www-authenticate" % rfc7235.SPEC_URL
  syntax = rfc7234.WWW_Authenticate
  list_header = True
  deprecated = False
  valid_in_requests = False
  valid_in_responses = True