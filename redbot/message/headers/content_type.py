#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax

description = u"""\
The `Content-Type` header indicates the media type of the body sent to the recipient or, in the
case of responses to the HEAD method, the media type that would have been sent had the request been
a GET."""

reference = u"%s#header.content-type" % rs.rfc7231


@rh.RequestOrResponseHeader
@rh.GenericHeaderSyntax
@rh.CheckFieldSyntax(
    r'(?:%(TOKEN)s/%(TOKEN)s(?:\s*;\s*%(PARAMETER)s)*)' % syntax.__dict__,
    rh.rfc2616 % "section-14.17"
)
def parse(subject, value, red):
    try:
        media_type, params = value.split(";", 1)
    except ValueError:
        media_type, params = value, ''
    media_type = media_type.lower()
    param_dict = rh.parse_params(red, subject, params, ['charset'])
    # TODO: check charset to see if it's known
    return (media_type, param_dict)
    
@rh.SingleFieldValue
def join(subject, values, red):
    return values[-1]
    
class BasicCTTest(rh.HeaderTest):
    name = 'Content-Type'
    inputs = ['text/plain; charset=utf-8']
    expected_out = ("text/plain", {"charset": "utf-8"})
    expected_err = []