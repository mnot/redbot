#!/usr/bin/env python

from typing import Tuple

from redbot.message import headers
from redbot.speak import Note, categories, levels
from redbot.syntax import rfc7234
from redbot.type import AddNoteMethodType


class cache_control(headers.HttpHeader):
    canonical_name = "Cache-Control"
    description = """\
The `Cache-Control` header is used to specify directives that must be obeyed by all caches along
the request/response chain. Cache directives are unidirectional in that the presence of a directive
in a request does not imply that the same directive is in effect in the response."""
    reference = "%s#header.cache-control" % rfc7234.SPEC_URL
    syntax = rfc7234.Cache_Control
    list_header = True
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Tuple[str, str]:
        try:
            directive_name, directive_val = field_value.split("=", 1)
            directive_val = headers.unquote_string(directive_val)
        except ValueError:
            directive_name = field_value
            directive_val = None
        directive_name = directive_name.lower()
        if directive_name in ["max-age", "s-maxage"]:
            try:
                directive_val = int(directive_val)  # type: ignore
            except (ValueError, TypeError):
                add_note(BAD_CC_SYNTAX, bad_cc_attr=directive_name)
                raise ValueError
        return (directive_name, directive_val)


class BAD_CC_SYNTAX(Note):
    category = categories.CACHING
    level = levels.BAD
    summary = "The %(bad_cc_attr)s Cache-Control directive's syntax is incorrect."
    text = "This value must be an integer."


class CacheControlTest(headers.HeaderTest):
    name = "Cache-Control"
    inputs = [b"a=b, c=d", b"e=f", b"g"]
    expected_out = [("a", "b"), ("c", "d"), ("e", "f"), ("g", None)]
    expected_err = []  # type: ignore


class CacheControlCaseTest(headers.HeaderTest):
    name = "Cache-Control"
    inputs = [b"A=b, c=D"]
    expected_out = [("a", "b"), ("c", "D")]
    expected_err = []  # type: ignore


class CacheControlQuotedTest(headers.HeaderTest):
    name = "Cache-Control"
    inputs = [b'a="b,c", c=d']
    expected_out = [("a", "b,c"), ("c", "d")]
    expected_err = []  # type: ignore


class CacheControlMaxAgeTest(headers.HeaderTest):
    name = "Cache-Control"
    inputs = [b"max-age=5"]
    expected_out = [("max-age", 5)]
    expected_err = []  # type: ignore


class CacheControlBadMaxAgeTest(headers.HeaderTest):
    name = "Cache-Control"
    inputs = [b"max-age=foo"]
    expected_out = []  # type: ignore
    expected_err = [BAD_CC_SYNTAX]
