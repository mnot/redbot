#!/usr/bin/env python

import redbot.message.headers as headers
from redbot.speak import Note, c as categories, l as levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7231

class location(HttpHeader):
  canonical_name = u"Location"
  description = u"""\
The `Location` header is used in `3xx` responses to redirect the recipient to a different location
to complete the request.
        
In `201 Created``` responses, it identifies a newly created resource."""
  reference = u"%s#header.location" % rfc7231.SPEC_URL
  syntax = rfc7231.Location
  list_header = False
  deprecated = False
  valid_in_requests = False
  valid_in_responses = True

  def parse(self, field_value, add_note):
      if msg.status_code not in [
          "201", "300", "301", "302", "303", "305", "307", "308"
      ]:
          add_note(subject, LOCATION_UNDEFINED)
      if not re.match(r"^\s*%s\s*$" % syntax.URI, value, re.VERBOSE):
          add_note(subject, LOCATION_NOT_ABSOLUTE,
                          full_uri=urljoin(msg.base_uri, value))
      return value



class LOCATION_UNDEFINED(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = u"%(response)s doesn't define any meaning for the Location header."
    text = u"""\
The `Location` header is used for specific purposes in HTTP; mostly to indicate the URI of another
resource (e.g., in redirection, or when a new resource is created).

In other status codes (such as this one) it doesn't have a defined meaning, so any use of it won't
be interoperable.

Sometimes `Location` is confused with `Content-Location`, which indicates a URI for the payload of
the message that it appears in."""

class LOCATION_NOT_ABSOLUTE(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = u"The Location header contains a relative URI."
    text = u"""\
`Location` was originally specified to contain an absolute, not relative, URI.

It is in the process of being updated, and most clients will work around this.

The correct absolute URI is (probably): `%(full_uri)s`"""
