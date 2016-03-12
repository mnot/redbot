#!/usr/bin/env python




import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


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
    