#!/usr/bin/env python


import redbot.speak as rs
import redbot.message.headers as headers
from redbot.speak import Note, categories, levels
from redbot.message.headers import HttpHeader, HeaderTest, BAD_SYNTAX
from redbot.syntax import rfc7230

class content_length(HttpHeader):
  canonical_name = u"Content-Length"
  description = u"""\
The `Content-Length` header indicates the size of the body, in number of bytes. In responses to the
HEAD method, it indicates the size of the body that would have been sent had the request been a GET.

If Content-Length is incorrect, persistent connections will not work, and caches may not store the
response (since they can't be sure if they have the whole response)."""
  reference = u"%s#header.content_length" % rfc7230.SPEC_URL
  syntax = rfc7230.Content_Length
  list_header = False
  deprecated = False
  valid_in_requests = True
  valid_in_responses = True

  def parse(self, field_value, add_note):
    try:
      return int(field_value)
    except ValueError:
      return

    
class ContentLengthTest(HeaderTest):
    name = 'Content-Length'
    inputs = ['1']
    expected_out = 1
    expected_err = []

class ContentLengthTextTest(HeaderTest):
    name = 'Content-Length'
    inputs = ['a']
    expected_out = None
    expected_err = [BAD_SYNTAX]

class ContentLengthSemiTest(HeaderTest):
    name = 'Content-Length'
    inputs = ['1;']
    expected_out = None
    expected_err = [BAD_SYNTAX]

class ContentLengthSpaceTest(HeaderTest):
    name = 'Content-Length'
    inputs = [' 1 ']
    expected_out = 1
    expected_err = []

class ContentLengthBigTest(HeaderTest):
    name = 'Content-Length'
    inputs = ['9' * 999]
    expected_out = long('9' * 999)
    expected_err = []
