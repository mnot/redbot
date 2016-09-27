#!/usr/bin/env python


from redbot.message import headers
from redbot.speak import Note, categories, levels

from redbot.syntax import rfc7234

class tcn(headers.HttpHeader):
    canonical_name = "TCN"
    reference = "https://tools.ietf.org/html/rfc2295"
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
