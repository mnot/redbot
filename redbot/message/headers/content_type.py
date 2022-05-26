#!/usr/bin/env python

from typing import Tuple

from redbot.message import headers
from redbot.syntax import rfc7231
from redbot.type import AddNoteMethodType, ParamDictType


class content_type(headers.HttpHeader):
    canonical_name = "Content-Type"
    description = """\
The `Content-Type` header indicates the media type of the body sent to the recipient or, in the
case of responses to the HEAD method, the media type that would have been sent had the request been
a GET."""
    reference = f"{rfc7231.SPEC_URL}#header.content_type"
    syntax = rfc7231.Content_Type
    list_header = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True

    def parse(
        self, field_value: str, add_note: AddNoteMethodType
    ) -> Tuple[str, ParamDictType]:
        try:
            media_type, param_str = field_value.split(";", 1)
        except ValueError:
            media_type, param_str = field_value, ""
        media_type = media_type.lower()
        param_dict = headers.parse_params(param_str, add_note, ["charset"])
        return media_type, param_dict


class BasicCTTest(headers.HeaderTest):
    name = "Content-Type"
    inputs = [b"text/plain; charset=utf-8"]
    expected_out = ("text/plain", {"charset": "utf-8"})
    expected_err = []  # type: ignore
