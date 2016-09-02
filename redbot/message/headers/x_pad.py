#!/usr/bin/env python

import redbot.message.headers as headers
from redbot.speak import Note, c as categories, l as levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7234

class x_pad(HttpHeader):
  canonical_name = u"X-Pad"
  description = u"""\
The `%(field_name)s` header is used to "pad" the response header size.
     
Very old versions of the Netscape browser had a bug whereby a response whose headers were exactly
256 or 257 bytes long, the browser would consider the response (e.g., an image) invalid.
 
Since the affected browsers (specifically, Netscape 2.x, 3.x and 4.0 up to beta 2) are no longer
widely used, it's probably safe to omit this header."""
  list_header = False
  deprecated = False
  valid_in_requests = False
  valid_in_responses = True