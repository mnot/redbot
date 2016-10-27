#!/usr/bin/env python

from redbot.message import headers
from redbot.syntax import rfc7235

class proxy_authenticate(headers.HttpHeader):
    canonical_name = "Proxy-Authenticate"
    description = """\
The `Proxy-Authenticate` response header consists of a challenge that indicates the authentication
scheme and parameters applicable to the proxy for this request-target."""
    reference = "%s#header.proxy-authenticate" % rfc7235.SPEC_URL
    syntax = rfc7235.Proxy_Authenticate
    list_header = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
