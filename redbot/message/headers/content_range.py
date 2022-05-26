#!/usr/bin/env python

from redbot.message import headers, HttpMessage
from redbot.speak import Note, categories, levels
from redbot.syntax import rfc7233
from redbot.type import AddNoteMethodType


class content_range(headers.HttpHeader):
    canonical_name = "Content-Range"
    description = """\
The `Content-Range` header is sent with a partial body to specify where in the full body the
partial body should be applied."""
    reference = f"{rfc7233.SPEC_URL}#header.content_range"
    syntax = rfc7233.Content_Range
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        # #53: check syntax, values?
        if self.message.status_code not in ["206", "416"]:
            add_note(CONTENT_RANGE_MEANINGLESS)
        return field_value


class CONTENT_RANGE_MEANINGLESS(Note):
    category = categories.RANGE
    level = levels.WARN
    summary = "%(response)s shouldn't have a Content-Range header."
    text = """\
HTTP only defines meaning for the `Content-Range` header in responses with a `206 Partial Content`
or `416 Requested Range Not Satisfiable` status code.

Putting a `Content-Range` header in this response may confuse caches and clients."""


class ContentRangeTest(headers.HeaderTest):
    name = "Content-Range"
    inputs = [b"bytes 1-100/200"]
    expected_out = "bytes 1-100/200"
    expected_err = []  # type: ignore

    def set_context(self, message: HttpMessage) -> None:
        message.status_code = "206"
