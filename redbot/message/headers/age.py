#!/usr/bin/env python

import redbot.message.headers as headers
from redbot.speak import Note, c as categories, l as levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7234

class age(HttpHeader):
  canonical_name = u"Age"
  description = u"""\
The `Age` header conveys the sender's estimate of the amount of time since the response (or its
validation) was generated at the origin server."""
  reference = u"%s#header.age" % rfc7234.SPEC_URL
  syntax = rfc7234.Age
  list_header = False
  deprecated = False
  valid_in_requests = False
  valid_in_responses = True

  def parse(subject, field_value, add_note):
      try:
          age = int(field_value)
      except ValueError:
          add_note(AGE_NOT_INT)
          return None
      if age < 0:
          add_note(AGE_NEGATIVE)
          return None
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

    
    
class AgeTest(HeaderTest):
    name = 'Age'
    inputs = ['10']
    expected_out = 10
    expected_err = []

class MultipleAgeTest(HeaderTest):
    name = 'Age'
    inputs = ['20', '10']
    expected_out = 10
    expected_err = [SINGLE_HEADER_REPEAT]

class CharAgeTest(HeaderTest):
    name = 'Age'
    inputs = ['foo']
    expected_out = None
    expected_err = [AGE_NOT_INT]

class NegAgeTest(HeaderTest):
    name = "Age"
    inputs = ["-20"]
    expected_out = None
    expected_err = [AGE_NEGATIVE]
