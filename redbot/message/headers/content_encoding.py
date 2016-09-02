#!/usr/bin/env python


import redbot.speak as rs
import redbot.message.headers as headers
from redbot.speak import Note, categories, levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7231

class content_encoding(HttpHeader):
  canonical_name = u"Content-Encoding"
  description = u"""\
The `Content-Encoding` header's value indicates what additional content codings have
been applied to the body, and thus what decoding mechanisms must be applied in order to obtain the
media-type referenced by the Content-Type header field.

Content-Encoding is primarily used to allow a document to be compressed without losing the identity
of its underlying media type; e.g., `gzip` and `deflate`."""
  reference = u"%s#header.content_encoding" % rfc7231.SPEC_URL
  syntax = rfc7231.Content_Encoding
  list_header = True
  deprecated = False
  valid_in_requests = True
  valid_in_responses = True

  def parse(self, field_value, add_note):
    # check to see if there are any non-gzip encodings, because
    # that's the only one we ask for.
    if field_value.lower() != 'gzip':
        add_note(ENCODING_UNWANTED, unwanted_codings=field_value)
    return field_value.lower()


class ENCODING_UNWANTED(Note):
    category = categories.CONNEG
    level = levels.WARN
    summary = u"%(response)s contained unwanted content-codings."
    text = u"""\
%(response)s's `Content-Encoding` header indicates it has content-codings applied
(`%(unwanted_codings)s`) that RED didn't ask for.

Normally, clients ask for the encodings they want in the `Accept-Encoding` request header. Using
encodings that the client doesn't explicitly request can lead to interoperability problems."""


class ContentEncodingTest(HeaderTest):
    name = 'Content-Encoding'
    inputs = ['gzip']
    expected_out = ['gzip']
    expected_err = []

class ContentEncodingCaseTest(HeaderTest):
    name = 'Content-Encoding'
    inputs = ['GZip']
    expected_out = ['gzip']
    expected_err = []

class UnwantedContentEncodingTest(HeaderTest):
    name = 'Content-Encoding'
    inputs = ['gzip', 'foo']
    expected_out = ['gzip', 'foo']
    expected_err = [ENCODING_UNWANTED]

