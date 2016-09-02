#!/usr/bin/env python

import redbot.message.headers as headers
from redbot.speak import Note, categories, levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7234

class warning(HttpHeader):
  canonical_name = u"Warning"
  description = u"""\
The `Warning` header is used to carry additional information about the status or transformation of
a message that might not be reflected in it. This information is typically used to warn about
possible incorrectness introduced by caching operations or transformations applied to the body of
the message."""
  reference = u"%s#header.warning" % rfc7234.SPEC_URL
  syntax = rfc7234.Warning
  list_header = True
  deprecated = False
  valid_in_requests = False
  valid_in_responses = True
