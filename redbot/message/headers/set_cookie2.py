from redbot.message import headers


class set_cookie2(headers.HttpHeader):
    canonical_name = "Set-Cookie2"
    description = """\
The `Set-Cookie2` header has been deprecated; use `Set-Cookie` instead."""
    reference = headers.RFC6265
    list_header = True
    deprecated = True
    valid_in_requests = False
    valid_in_responses = True
    no_coverage = True
