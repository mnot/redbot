#!/usr/bin/env python


import redbot.message.headers as headers
from redbot.speak import Note, categories, levels
from redbot.message.headers import HttpHeader, HeaderTest

class mime_version(HttpHeader):
  canonical_name = u"MIME-Version"
  description = u"""\
HTTP is not a MIME-compliant protocol. However, HTTP/1.1 messages can include a single MIME-Version
header field to indicate what version of the MIME protocol was used to construct the message. Use
of the MIME-Version header field indicates that the message is in full compliance with the MIME
protocol."""
  reference = u"%s#section-19.4.1" % headers.rfc2616
  list_header = False
  deprecated = True
  valid_in_requests = True
  valid_in_responses = True
  no_coverage = True