#!/usr/bin/env python

import redbot.message.headers as headers
from redbot.speak import Note, categories, levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7234

class x_download_options(HttpHeader):
  canonical_name = u"X-Download-Options"
  list_header = True
  deprecated = False
  valid_in_requests = False
  valid_in_responses = True

  def evaluate(self, add_note):
      if 'noopen' in values:
          add_note(DOWNLOAD_OPTIONS)
      else:
          add_note(DOWNLOAD_OPTIONS_UNKNOWN)


class DOWNLOAD_OPTIONS(Note):
    category = categories.SECURITY
    level = levels.INFO
    summary = u"%(response)s can't be directly opened directly by Internet Explorer when downloaded."
    text = u"""\
When the `X-Download-Options` header is present with the value `noopen`, Internet Explorer users
are prevented from directly opening a file download; instead, they must first save the file
locally. When the locally saved file is later opened, it no longer executes in the security context
of your site, helping to prevent script injection.

This header probably won't have any effect in other clients.

See [this blog article](http://bit.ly/sfuxWE) for more details."""

class DOWNLOAD_OPTIONS_UNKNOWN(Note):
    category = categories.SECURITY
    level = levels.WARN
    summary = u"%(response)s contains an X-Download-Options header with an unknown value."
    text = u"""\
Only one value is currently defined for this header, `noopen`. Using other values here won't
necessarily cause problems, but they probably won't have any effect either.

See [this blog article](http://bit.ly/sfuxWE) for more details."""

