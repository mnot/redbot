from redbot.message import headers
from redbot.syntax import rfc7231
from redbot.type import AddNoteMethodType


class vary(headers.HttpHeader):
    canonical_name = "Vary"
    description = """\
The `Vary` header indicates the set of request headers that determines whether a cache is permitted
to use the response to reply to a subsequent request without validation.

In uncacheable or stale responses, the Vary field value advises the user agent about the criteria
that were used to select the representation."""
    reference = f"{rfc7231.SPEC_URL}#header.vary"
    syntax = rfc7231.Vary
    list_header = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        return field_value.lower()
