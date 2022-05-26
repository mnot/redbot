#!/usr/bin/env python


from redbot.message import headers
from redbot.syntax import rfc7230


class trailer(headers.HttpHeader):
    canonical_name = "Trailer"
    description = """\
The `Trailer` header indicates that the given set of header fields will be
present in the trailer of the message, after the body."""
    reference = f"{rfc7230.SPEC_URL}#header.trailer"
    syntax = rfc7230.Trailer
    list_header = True
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True
