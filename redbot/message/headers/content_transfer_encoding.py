#!/usr/bin/env python

from redbot.message import headers


class content_transfer_encoding(headers.HttpHeader):
    canonical_name = "Content-Transfer-Encoding"
    description = """\
The `Content-Transfer-Encoding` isn't part of HTTP, but it is used in MIME protocols in a manner
analogous to `Transfer-Encoding`."""
    reference = "https://tools.ietf.org/html/rfc2616#section-19.4.5"
    list_header = False
    deprecated = True
    valid_in_requests = True
    valid_in_responses = True
    no_coverage = True
