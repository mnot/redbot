#!/usr/bin/env python

from redbot.message import headers
from redbot.speak import Note, categories, levels
from redbot.syntax import rfc7230

class te(headers.HttpHeader):
    canonical_name = u"TE"
    description = u"""\
The `TE` header indicates what transfer-codings the client is willing to accept in the response,
and whether or not it is willing to accept trailer fields after the body when the response uses
chunked transfer-coding.

The most common transfer-coding, `chunked`, doesn't need to be listed in `TE`."""
    reference = u"%s#header.te" % rfc7230.SPEC_URL
    syntax = rfc7230.TE
    list_header = True
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True
