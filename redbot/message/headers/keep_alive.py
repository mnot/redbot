#!/usr/bin/env python


import redbot.message.headers as headers
from redbot.speak import Note, categories, levels
from redbot.message.headers import HttpHeader, HeaderTest

class keep_alive(HttpHeader):
  canonical_name = u"Keep-Alive"
  description = u"""\
The `Keep-Alive` header is completely optional; it is defined primarily because the `keep-alive`
connection token implies that such a header exists, not because anyone actually uses it.

Some implementations (e.g., [Apache](http://httpd.apache.org/)) do generate a `Keep-Alive` header
to convey how many requests they're willing to serve on a single connection, what the connection
timeout is and other information. However, this isn't usually used by clients.

It's safe to remove this header if you wish to save a few bytes in the response."""
  reference = u"https://tools.ietf.org/html/rfc2068#section-19.7.1"
  list_header = True
  deprecated = True
  valid_in_requests = True
  valid_in_responses = True
  
  def parse(self, field_value, add_note):
      try:
          attr, attr_val = field._alue.split("=", 1)
          attr_val = headers.unquote_string(attr_val)
      except ValueError:
          attr = value
          attr_val = None
      return (attr.lower(), attr_val)
