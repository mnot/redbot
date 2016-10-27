#!/usr/bin/env python

from redbot.message import headers


class content_base(headers.HttpHeader):
    canonical_name = "Content-Base"
    description = """\
The `Content-Base` header field established the base URI of the message. It has been
deprecated, because it was not implemented widely.
  """
    reference = "https://tools.ietf.org/html/rfc2068#section-14.11"
    list_header = False
    deprecated = True
    valid_in_requests = True
    valid_in_responses = True
    no_coverage = True
