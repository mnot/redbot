#!/usr/bin/env python

from redbot.message import headers
from redbot.syntax import rfc7234


class warning(headers.HttpHeader):
    canonical_name = "Warning"
    description = """\
The `Warning` header is used to carry additional information about the status or transformation of
a message that might not be reflected in it. It has been deprecated."""
    reference = f"{rfc7234.SPEC_URL}#header.warning"
    syntax = rfc7234.Warning
    list_header = True
    deprecated = True
    valid_in_requests = False
    valid_in_responses = True
