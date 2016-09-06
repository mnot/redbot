#!/usr/bin/env python

from redbot.speak import Note, categories, levels
from redbot.message import headers
from redbot.message.headers import HttpHeader, HeaderTest, parse_date
from redbot.syntax import rfc7231

class date(HttpHeader):
    canonical_name = u"Date"
    description = u"""\
The `Date` header represents the time when the message was generated, regardless of caching that
happened since.

It is used by caches as input to expiration calculations, and to detect clock drift."""
    reference = u"%s#header.date" % rfc7231.SPEC_URL
    syntax = False # rfc7231.Date
    list_header = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True

    def parse(self, field_value, add_note):
        try:
            date = parse_date(field_value)
        except ValueError:
            add_note(BAD_DATE_SYNTAX)
            return None
        return date


class BAD_DATE_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"The %(field_name)s header's value isn't a valid date."
    text = u"""\
HTTP dates have very specific syntax, and sending an invalid date can cause a number of problems,
especially around caching. Common problems include sending "1 May" instead of "01 May" (the month
is a fixed-width field), and sending a date in a timezone other than GMT. See [the HTTP
specification](http://www.w3.org/Protocols/rfc2616/rfc2616-sec3.html#sec3.3) for more
information."""


class BasicDateTest(HeaderTest):
    name = 'Date'
    inputs = ['Mon, 04 Jul 2011 09:08:06 GMT']
    expected_out = 1309770486
    expected_err = []

class BadDateTest(HeaderTest):
    name = 'Date'
    inputs = ['0']
    expected_out = None
    expected_err = [headers.BAD_DATE_SYNTAX]

class BlankDateTest(HeaderTest):
    name = 'Date'
    inputs = ['']
    expected_out = None
    expected_err = [headers.BAD_DATE_SYNTAX]
