#!/usr/bin/env python

from redbot.message import headers
from redbot.speak import Note, categories, levels
from redbot.syntax import rfc7235

class www_authenticate(headers.HttpHeader):
    canonical_name = "WWW-Authenticate"
    description = """\
The `WWW-Authenticate` response header consists of at least one challenge that
indicates the authentication scheme(s) and parameters applicable."""
    reference = "%s#header.www-authenticate" % rfc7235.SPEC_URL
    syntax = rfc7235.WWW_Authenticate
    list_header = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
