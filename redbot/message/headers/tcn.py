#!/usr/bin/env python


from redbot.message import headers


class tcn(headers.HttpHeader):
    canonical_name = "TCN"
    description = """\
The `TCN` header field is part of an experimental transparent content negotiation scheme. It
is not widely supported in clients.
"""
    reference = "https://tools.ietf.org/html/rfc2295"
    list_header = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
    no_coverage = True