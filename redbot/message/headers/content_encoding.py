#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax

description = u"""\
The `Content-Encoding` header's value indicates what additional content codings have
been applied to the body, and thus what decoding mechanisms must be applied in order to obtain the
media-type referenced by the Content-Type header field.

Content-Encoding is primarily used to allow a document to be compressed without losing the identity
of its underlying media type; e.g., `gzip` and `deflate`."""



@rh.GenericHeaderSyntax
@rh.CheckFieldSyntax(syntax.TOKEN, rh.rfc2616 % "section-14.11")
def parse(subject, value, red):
    # check to see if there are any non-gzip encodings, because
    # that's the only one we ask for.
    if value.lower() != 'gzip':
        red.add_note(subject, 
            rs.ENCODING_UNWANTED, 
            unwanted_codings=value
        )
    return value.lower()
    
def join(subject, values, red):
    return values

    
class ContentEncodingTest(rh.HeaderTest):
    name = 'Content-Encoding'
    inputs = ['gzip']
    expected_out = ['gzip']
    expected_err = []

class ContentEncodingCaseTest(rh.HeaderTest):
    name = 'Content-Encoding'
    inputs = ['GZip']
    expected_out = ['gzip']
    expected_err = []

class UnwantedContentEncodingTest(rh.HeaderTest):
    name = 'Content-Encoding'
    inputs = ['gzip', 'foo']
    expected_out = ['gzip', 'foo']
    expected_err = [rs.ENCODING_UNWANTED]

