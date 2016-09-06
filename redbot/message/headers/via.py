#!/usr/bin/env python

import redbot.message.headers as headers
from redbot.speak import Note, categories, levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7230

class via(HttpHeader):
  canonical_name = u"Via"
  description = u"""\
The `Via` header is added to requests and responses by proxies and other HTTP intermediaries. It
can be used to help avoid request loops and identify the protocol capabilities of all senders along
the request/response chain."""
  reference = u"%s#header.Via" % rfc7230.SPEC_URL
  syntax = rfc7230.Via
  list_header = True
  deprecated = False
  valid_in_requests = True
  valid_in_responses = True

  def evaluate(self, add_note):
      via_list = u"<ul>" + u"\n".join(
             [u"<li><code>%s</code></li>" % v for v in self.value]
                         ) + u"</ul>"
      add_note(VIA_PRESENT, via_list=via_list)
    

class VIA_PRESENT(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = u"One or more intermediaries are present."
    text = u"""\
The `Via` header indicates that one or more intermediaries are present between RED and the origin
server for the resource.

This may indicate that a proxy is in between RED and the server, or that the server uses a "reverse
proxy" or CDN in front of it.

There field has three space-separated components; first, the HTTP version of the message that the
intermediary received, then the identity of the intermediary (usually but not always its hostname),
and then optionally a product identifier or comment (usually used to identify the software being
used)."""


class ViaTest(HeaderTest):
    name = 'Via'
    inputs = ['1.1 test']
    expected_out = [u'1.1 test']
    expected_err = [VIA_PRESENT]