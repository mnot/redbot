#!/usr/bin/env python

from redbot.message import headers
from redbot.speak import Note, categories, levels
from redbot.syntax import rfc7231

class allow(headers.HttpHeader):
    canonical_name = u"Allow"
    description = u"""\
The `Allow` header advertises the set of methods that are supported by the resource."""
    reference = u"%s#header.allow" % rfc7231.SPEC_URL
    syntax = rfc7231.Allow
    list_header = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

class AllowTest(headers.HeaderTest):
    name = 'Allow'
    inputs = ['GET, POST']
    expected_out = ['GET', 'POST']
    expected_err = []