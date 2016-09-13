#!/usr/bin/env python

from redbot.message import headers
from redbot.speak import Note, categories, levels
from redbot.syntax import rfc7231


class content_disposition(headers.HttpHeader):
    canonical_name = u"Content-Disposition"
    description = u"""\
The `Content-Disposition` header suggests a name to use when saving the file.

When the disposition (the first value) is set to `attachment`, it also prompts browsers to download
the file, rather than display it."""
    reference = u"https://tools.ietf.org/html/rfc6266"
    syntax = r'(?:%s(?:\s*;\s*%s)*)' % (rfc7231.token, rfc7231.parameter)
    list_header = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True

    def parse(self, field_value, add_note):
        try:
            disposition, param_str = field_value.split(";", 1)
        except ValueError:
            disposition, param_str = field_value, ''
        disposition = disposition.lower()
        param_dict = headers.parse_params(param_str, add_note)
        if disposition not in ['inline', 'attachment']:
            add_note(DISPOSITION_UNKNOWN, disposition=disposition)
        if not param_dict.has_key('filename'):
            add_note(DISPOSITION_OMITS_FILENAME)
        if "%" in param_dict.get('filename', ''):
            add_note(DISPOSITION_FILENAME_PERCENT)
        if "/" in param_dict.get('filename', '') or r"\\" in param_dict.get('filename*', ''):
            add_note(DISPOSITION_FILENAME_PATH_CHAR)
        return disposition, param_dict


class DISPOSITION_UNKNOWN(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = u"The '%(disposition)s' Content-Disposition isn't known."
    text = u"""\
The `Content-Disposition` header has two widely-known values; `inline` and `attachment`.
`%(disposition)s` isn't recognised, and most implementations will default to handling it like
`attachment`."""

class DISPOSITION_OMITS_FILENAME(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = u"The Content-Disposition header doesn't have a 'filename' parameter."
    text = u"""\
The `Content-Disposition` header suggests a filename for clients to use when saving the file
locally.

It should always contain a `filename` parameter, even when the `filename*` parameter is used to
carry an internationalised filename, so that browsers can fall back to an ASCII-only filename."""

class DISPOSITION_FILENAME_PERCENT(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = \
        u"The 'filename' parameter on the Content-Disposition header contains a '%%' character."
    text = u"""\
The `Content-Disposition` header suggests a filename for clients to use when saving the file
locally, using the `filename` parameter.

[RFC6266](http://tools.ietf.org/html/rfc6266) specifies how to carry non-ASCII characters in this
parameter. However, historically some (but not all) browsers have also decoded %%-encoded
characters in the `filename` parameter, which means that they'll be treated differently depending
on the browser you're using.

As a result, it's not interoperable to use percent characters in the `filename` parameter. Use the
correct encoding in the `filename*` parameter instead."""

class DISPOSITION_FILENAME_PATH_CHAR(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = u"The filename in the Content-Disposition header contains a path character."
    text = u"""\
The `Content-Disposition` header suggests a filename for clients to use when saving the file
locally, using the `filename` and `filename*` parameters.

One of these parameters contains a path character ("\" or "/"), used to navigate between
directories on common operating systems.

Because this can be used to attach the browser's host operating system (e.g., by saving a file to a
system directory), browsers will usually ignore these parameters, or remove path information.

You should remove these characters."""



class QuotedCDTest(headers.HeaderTest):
    name = 'Content-Disposition'
    inputs = ['attachment; filename="foo.txt"']
    expected_out = (u'attachment', {u'filename': u'foo.txt'})
    expected_err = []

class TokenCDTest(headers.HeaderTest):
    name = 'Content-Disposition'
    inputs = ['attachment; filename=foo.txt']
    expected_out = (u'attachment', {u'filename': u'foo.txt'})
    expected_err = []

class InlineCDTest(headers.HeaderTest):
    name = 'Content-Disposition'
    inputs = ['inline; filename=foo.txt']
    expected_out = (u'inline', {u'filename': u'foo.txt'})
    expected_err = []

class RepeatCDTest(headers.HeaderTest):
    name = 'Content-Disposition'
    inputs = ['attachment; filename=foo.txt', 'inline; filename=bar.txt']
    expected_out = (u'inline', {u'filename': u'bar.txt'})
    expected_err = [headers.SINGLE_HEADER_REPEAT]

class FilenameStarCDTest(headers.HeaderTest):
    name = 'Content-Disposition'
    inputs = ["attachment; filename=foo.txt; filename*=UTF-8''a%cc%88.txt"]
    expected_out = ('attachment', {
        u'filename': u'foo.txt',
        u'filename*': u'a\u0308.txt'})
    expected_err = []

class FilenameStarQuotedCDTest(headers.HeaderTest):
    name = 'Content-Disposition'
    inputs = ["attachment; filename=foo.txt; filename*=\"UTF-8''a%cc%88.txt\""]
    expected_out = (u'attachment', {
        u'filename': u'foo.txt',
        u'filename*': u'a\u0308.txt'})
    expected_err = [headers.PARAM_STAR_QUOTED]

class FilenamePercentCDTest(headers.HeaderTest):
    name = 'Content-Disposition'
    inputs = ["attachment; filename=fo%22o.txt"]
    expected_out = (u'attachment', {u'filename': u'fo%22o.txt', })
    expected_err = [DISPOSITION_FILENAME_PERCENT]

class FilenamePathCharCDTest(headers.HeaderTest):
    name = 'Content-Disposition'
    inputs = ['attachment; filename="/foo.txt"']
    expected_out = (u'attachment', {'filename': u'/foo.txt',})
    expected_err = [DISPOSITION_FILENAME_PATH_CHAR]
