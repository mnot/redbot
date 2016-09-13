#!/usr/bin/env python

from redbot.message import headers
from redbot.speak import Note, categories, levels
from redbot.syntax import rfc7234

class age(headers.HttpHeader):
    canonical_name = u"Age"
    description = u"""\
The `Age` header conveys the sender's estimate of the amount of time since the response (or its
validation) was generated at the origin server."""
    reference = u"%s#header.age" % rfc7234.SPEC_URL
    syntax = False # rfc7234.Age
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value, add_note):
        try:
            age = int(field_value)
        except ValueError:
            add_note(AGE_NOT_INT)
            raise
        if age < 0:
            add_note(AGE_NEGATIVE)
            raise ValueError
        return age



class AGE_NOT_INT(Note):
    category = categories.CACHING
    level = levels.BAD
    summary = u"The Age header's value should be an integer."
    text = u"""\
The `Age` header indicates the age of the response; i.e., how long it has been cached
since it was generated. The value given was not an integer, so it is not a valid age."""

class AGE_NEGATIVE(Note):
    category = categories.CACHING
    level = levels.BAD
    summary = u"The Age headers' value must be a positive integer."
    text = u"""\
The `Age` header indicates the age of the response; i.e., how long it has been cached
since it was generated. The value given was negative, so it is not a valid age."""



class AgeTest(headers.HeaderTest):
    name = 'Age'
    inputs = ['10']
    expected_out = 10
    expected_err = []

class MultipleAgeTest(headers.HeaderTest):
    name = 'Age'
    inputs = ['20', '10']
    expected_out = 10
    expected_err = [headers.SINGLE_HEADER_REPEAT]

class CharAgeTest(headers.HeaderTest):
    name = 'Age'
    inputs = ['foo']
    expected_out = None
    expected_err = [AGE_NOT_INT]

class NegAgeTest(headers.HeaderTest):
    name = "Age"
    inputs = ["-20"]
    expected_out = None
    expected_err = [AGE_NEGATIVE]
