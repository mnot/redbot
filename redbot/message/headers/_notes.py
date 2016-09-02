#!/usr/bin/env python

"""
Common header-related Notes.
"""

from redbot.speak import Note, categories, levels


class SINGLE_HEADER_REPEAT(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"Only one %(field_name)s header is allowed in a response."
    text = u"""\
This header is designed to only occur once in a message. When it occurs more than once, a receiver
needs to choose the one to use, which can lead to interoperability problems, since different
implementations may make different choices.

For the purposes of its tests, RED uses the last instance of the header that is present; other
implementations may behave differently."""


class BAD_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"The %(field_name)s header's syntax isn't valid."
    text = u"""\
The value for this header doesn't conform to its specified syntax; see [its
definition](%(ref_uri)s) for more information."""

class PARAM_STAR_QUOTED(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"The '%(param)s' parameter's value cannot be quoted."
    text = u"""\
Parameter values that end in '*' have a specific format, defined in
[RFC5987](http://tools.ietf.org/html/rfc5987), to allow non-ASCII text.

The `%(param)s` parameter on the `%(field_name)s` header has double-quotes around it, which is not
valid."""

class PARAM_STAR_ERROR(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"The %(param)s parameter's value is invalid."
    text = u"""\
Parameter values that end in '*' have a specific format, defined in
[RFC5987](http://tools.ietf.org/html/rfc5987), to allow non-ASCII text.
 
 The `%(param)s` parameter on the `%(field_name)s` header is not valid; it needs to have three
parts, separated by single quotes (')."""

class PARAM_STAR_BAD(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"The %(param)s* parameter isn't allowed on the %(field_name)s header."
    text = u"""\
Parameter values that end in '*' are reserved for non-ascii text, as explained in
[RFC5987](http://tools.ietf.org/html/rfc5987).

The `%(param)s` parameter on the `%(field_name)s` does not allow this; you should use %(param)s
without the "*" on the end (and without the associated encoding).

RED ignores the content of this parameter. 
     """

class PARAM_STAR_NOCHARSET(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = u"The %(param)s parameter's value doesn't define an encoding."
    text = u"""\
Parameter values that end in '*' have a specific format, defined in
[RFC5987](http://tools.ietf.org/html/rfc5987), to allow non-ASCII text.

The `%(param)s` parameter on the `%(field_name)s` header doesn't declare its character encoding,
which means that recipients can't understand it. It should be `UTF-8`."""

class PARAM_STAR_CHARSET(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = u"The %(param)s parameter's value uses an encoding other than UTF-8."
    text = u"""\
Parameter values that end in '*' have a specific format, defined in
[RFC5987](http://tools.ietf.org/html/rfc5987), to allow non-ASCII text.
 
The `%(param)s` parameter on the `%(field_name)s` header uses the `'%(enc)s` encoding, which has
interoperability issues on some browsers. It should be `UTF-8`."""

class PARAM_REPEATS(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = u"The '%(param)s' parameter repeats in the %(field_name)s header."
    text = u"""\
Parameters on the %(field_name)s header should not repeat; implementations may handle them
differently."""

class PARAM_SINGLE_QUOTED(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = u"The '%(param)s' parameter on the %(field_name)s header is single-quoted."
    text = u"""\
The `%(param)s`'s value on the %(field_name)s header start and ends with a single quote (').
However, single quotes don't mean anything there.

This means that the value will be interpreted as `%(param_val)s`, **not**
`%(param_val_unquoted)s`. If you intend the latter, drop the single quotes."""

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
