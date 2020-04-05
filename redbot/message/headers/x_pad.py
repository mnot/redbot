#!/usr/bin/env python

from redbot.message import headers


class x_pad(headers.HttpHeader):
    canonical_name = "X-Pad"
    description = """\
  The `%(field_name)s` header is used to "pad" the response header size.

  Very old versions of the Netscape browser had a bug whereby a response whose headers were exactly
  256 or 257 bytes long, the browser would consider the response (e.g., an image) invalid.

  Since the affected browsers (specifically, Netscape 2.x, 3.x and 4.0 up to beta 2) are no longer
  widely used, it's safe to omit this header."""
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
