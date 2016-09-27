#!/usr/bin/env python


from redbot.message import headers
from redbot.speak import Note, categories, levels
from redbot.syntax import rfc7231

class content_location(headers.HttpHeader):
    canonical_name = "Content-Location"
    description = """\
The `Content-Location` header can used to supply an address for the
representation when it is accessible from a location separate from the request
URI."""
    reference = "%s#header.content_location" % rfc7231.SPEC_URL
    syntax = rfc7231.Content_Location
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True



class ContentLocationTest(headers.HeaderTest):
    name = 'Content-Location'
    inputs = ['/foo']
    expected_out = '/foo'
    expected_err = []
