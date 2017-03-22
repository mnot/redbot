#!/usr/bin/env python

from typing import Tuple, Dict

from redbot.message import headers
from redbot.speak import Note, categories, levels
from redbot.syntax import rfc7231
from redbot.type import AddNoteMethodType


class x_ua_compatible(headers.HttpHeader):
    canonical_name = "X-UA-Compatible"
    reference = "http://msdn.microsoft.com/en-us/library/cc288325(VS.85).aspx"
    syntax = rfc7231.parameter
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Tuple[str, str]:
        try:
            attr, attr_value = field_value.split("=", 1)
        except ValueError:
            attr = field_value
            attr_value = None
        return attr, attr_value

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        directives = {} # type: Dict[str, str]
        warned = False
        attr, attr_value = self.value
        if attr in directives and not warned:
            add_note(UA_COMPATIBLE_REPEAT)
            warned = True
        directives[attr] = attr_value
        add_note(UA_COMPATIBLE)



class UA_COMPATIBLE(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = "%(response)s explicitly sets a rendering mode for Internet Explorer 8."
    text = """\
Internet Explorer 8 allows responses to explicitly set the rendering mode used for a given page
(known a the "compatibility mode").

See [Microsoft's documentation](http://msdn.microsoft.com/en-us/library/cc288325(VS.85).aspx) for
more information."""

class UA_COMPATIBLE_REPEAT(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = "%(response)s has multiple X-UA-Compatible directives targeted at the same UA."
    text = """\
Internet Explorer 8 allows responses to explicitly set the rendering mode used for a page.

This response has more than one such directive targetted at one browser; this may cause
unpredictable results.

See [this blog entry](http://msdn.microsoft.com/en-us/library/cc288325(VS.85).aspx) for more
information."""



class BasicUACTest(headers.HeaderTest):
    name = 'X-UA-Compatible'
    inputs = [b'foo=bar']
    expected_out = ("foo", "bar")
    expected_err = [UA_COMPATIBLE]
