from redbot.message import headers
from redbot.syntax import rfc7231


class retry_after(headers.HttpHeader):
    canonical_name = "Retry-After"
    description = """\
The `Retry-After` header can be used with a `503 Service Unavailable` response to indicate how long
the service is expected to be unavailable to the requesting client.

The value of this field can be either a date or an integer number of seconds."""
    reference = f"{rfc7231.SPEC_URL}#header.retry-after"
    syntax = rfc7231.Retry_After
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
