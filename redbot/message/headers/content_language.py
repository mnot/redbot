#!/usr/bin/env python


import redbot.message.headers as headers
from redbot.speak import Note, categories, levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7231

class content_language(HttpHeader):
  canonical_name = u"Content-Language"
  description = u"""\
The `Content-Language` header describes the natural language(s) of the intended audience. Note that
this might not convey all of the languages used within the body."""
  reference = u"%s#header.content_language" % rfc7231.SPEC_URL
  syntax = rfc7231.Content_Language
  list_header = False
  deprecated = False
  valid_in_requests = True
  valid_in_responses = True




class ContentLanguageTest(HeaderTest):
    name = 'Content-Language'
    inputs = ['en-US']
    expected_out = 'en-US'
    expected_err = []