#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax

description = u"""\
The `Via` header is added to requests and responses by proxies and other HTTP intermediaries. It
can be used to help avoid request loops and identify the protocol capabilities of all senders along
the request/response chain."""

reference = u"%s#header.via" % rs.rfc7230

@rh.GenericHeaderSyntax
@rh.CheckFieldSyntax(
    r'(?:%s/)?%s\s+[^,\s]+(?:\s+%s)?' % (
      syntax.TOKEN, syntax.TOKEN, syntax.COMMENT),
    rh.rfc2616 % "section-14.45")
def parse(subject, value, red):
    return value
    
def join(subject, values, red):
    via_list = u"<ul>" + u"\n".join(
           [u"<li><code>%s</code></li>" % v for v in values]
                       ) + u"</ul>"
    red.add_note(subject, rs.VIA_PRESENT, via_list=via_list)
    