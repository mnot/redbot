#!/usr/bin/env python

from redbot.message import headers
from redbot.speak import Note, categories, levels
from redbot.syntax import rfc7234
from redbot.type import AddNoteMethodType


class age(headers.HttpHeader):
    canonical_name = "Age"
    description = """\
The `Age` header conveys the sender's estimate of the amount of time since the response (or its
validation) was generated at the origin server."""
    reference = "%s#header.age" % rfc7234.SPEC_URL
    syntax = False  # rfc7234.Age
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> int:
        try:
            age_value = int(field_value)
        except ValueError:
            add_note(AGE_NOT_INT)
            raise
        if age_value < 0:
            add_note(AGE_NEGATIVE)
            raise ValueError
        return age_value


class AGE_NOT_INT(Note):
    category = categories.CACHING
    level = levels.BAD
    summary = "The Age header's value should be an integer."
    text = """\
The `Age` header indicates the age of the response; i.e., how long it has been cached
since it was generated. The value given was not an integer, so it is not a valid age."""


class AGE_NEGATIVE(Note):
    category = categories.CACHING
    level = levels.BAD
    summary = "The Age headers' value must be a positive integer."
    text = """\
The `Age` header indicates the age of the response; i.e., how long it has been cached
since it was generated. The value given was negative, so it is not a valid age."""


class AgeTest(headers.HeaderTest):
    name = "Age"
    inputs = [b"10"]
    expected_out = 10
    expected_err = []  # type: ignore


class MultipleAgeTest(headers.HeaderTest):
    name = "Age"
    inputs = [b"20", b"10"]
    expected_out = 10
    expected_err = [headers.SINGLE_HEADER_REPEAT]


class CharAgeTest(headers.HeaderTest):
    name = "Age"
    inputs = [b"foo"]
    expected_out = None  # type: ignore
    expected_err = [AGE_NOT_INT]


class NegAgeTest(headers.HeaderTest):
    name = "Age"
    inputs = [b"-20"]
    expected_out = None  # type: ignore
    expected_err = [AGE_NEGATIVE]
