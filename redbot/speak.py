"""
A collection of notes that the RED can emit.

PLEASE NOTE: the summary field is automatically HTML escaped, so it can contain arbitrary text (as
long as it's unicode).

However, the longer text field IS NOT ESCAPED, and therefore all variables to be interpolated into
it need to be escaped to be safe for use in HTML.
"""

from cgi import escape as e_html
from markdown import markdown


class _Categories:
    "Note classifications."
    GENERAL = u"General"
    SECURITY = u"Security"
    CONNEG = u"Content Negotiation"
    CACHING = u"Caching"
    VALIDATION = u"Validation"
    CONNECTION = u"Connection"
    RANGE = u"Partial Content"
categories = _Categories()

class _Levels:
    "Note levels."
    GOOD = u'good'
    WARN = u'warning'
    BAD = u'bad'
    INFO = u'info'
levels = _Levels()

class Note:
    """
    A note about an HTTP resource, representation, or other component
    related to the URI under test.
    """
    category = None
    level = None
    summary = u""
    text = u""
    def __init__(self, subject, subrequest=None, vrs=None):
        self.subject = subject
        self.subrequest = subrequest
        self.vars = vrs or {}

    def __eq__(self, other):
        if self.__class__ == other.__class__ \
           and self.vars == other.vars \
           and self.subject == other.subject:
            return True
        else:
            return False

    def show_summary(self, lang):
        """
        Output a textual summary of the message as a Unicode string.
        
        Note that if it is displayed in an environment that needs 
        encoding (e.g., HTML), that is *NOT* done.
        """
        return self.summary % self.vars
        
    def show_text(self, lang):
        """
        Show the HTML text for the message as a Unicode string.
        
        The resulting string is already HTML-encoded.
        """
        return markdown(self.text % dict(
            [(k, e_html(unicode(v), True)) for k, v in self.vars.items()]
        ), output_format="html5")


response = {
    'this': 'This response',
    'conneg': 'The uncompressed response',
    'LM validation': 'The 304 response',
    'ETag validation': 'The 304 response',
    'range': 'The partial response',
}


class REQUEST_HDR_IN_RESPONSE(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u'"%(field_name)s" is a request header.'
    text = u"""\
%(field_name)s is only defined to have meaning in requests; in responses, it doesn't have any
meaning, so RED has ignored it."""

class RESPONSE_HDR_IN_REQUEST(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u'"%(field_name)s" is a request header.'
    text = u"""\
%(field_name)s is only defined to have meaning in responses; in requests, it doesn't have any
meaning, so RED has ignored it."""

class HEADER_BLOCK_TOO_LARGE(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"%(response)s's headers are very large (%(header_block_size)s)."
    text = u"""\
Some implementations have limits on the total size of headers that they'll accept. For example,
Squid's default configuration limits header blocks to 20k."""

class HEADER_TOO_LARGE(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = u"The %(header_name)s header is very large (%(header_size)s)."
    text = u"""\
Some implementations limit the size of any single header line."""

class HEADER_NAME_ENCODING(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"The %(header_name)s header's name contains non-ASCII characters."
    text = u"""\
HTTP header field-names can only contain ASCII characters. RED has detected (and possibly removed)
non-ASCII characters in this header name."""

class HEADER_VALUE_ENCODING(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = u"The %(header_name)s header's value contains non-ASCII characters."
    text = u"""\
HTTP headers use the ISO-8859-1 character set, but in most cases are pure ASCII (a subset of this
encoding).

This header has non-ASCII characters, which RED has interpreted as being encoded in
ISO-8859-1. If another encoding is used (e.g., UTF-8), the results may be unpredictable."""

class HEADER_DEPRECATED(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = u"The %(header_name)s header is deprecated."
    text = u"""\
This header field is no longer recommended for use, because of interoperability problems and/or
lack of use. See [the deprecation notice](%(deprecation_ref)s) for more information."""


class BODY_NOT_ALLOWED(Note):
    category = categories.CONNECTION
    level = levels.BAD
    summary = u"%(response)s is not allowed to have a body."
    text = u"""\
HTTP defines a few special situations where a response does not allow a body. This includes 101,
204 and 304 responses, as well as responses to the `HEAD` method.

%(response)s had a body, despite it being disallowed. Clients receiving it may treat the body as
the next response in the connection, leading to interoperability and security issues."""


# Specific headers

class BAD_CC_SYNTAX(Note):
    category = categories.CACHING
    level = levels.BAD
    summary = u"The %(bad_cc_attr)s Cache-Control directive's syntax is incorrect."
    text = u"This value must be an integer."

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

class BAD_CHUNK(Note):
    category = categories.CONNECTION
    level = levels.BAD
    summary = u"%(response)s had chunked encoding errors."
    text = u"""\
The response indicates it uses HTTP chunked encoding, but there was a problem decoding the
chunking.

A valid chunk looks something like this:

`[chunk-size in hex]\\r\\n[chunk-data]\\r\\n`

However, the chunk sent started like this:

`%(chunk_sample)s`

This is a serious problem, because HTTP uses chunking to delimit one response from the next one;
incorrect chunking can lead to interoperability and security problems.

This issue is often caused by sending an integer chunk size instead of one in hex, or by sending
`Transfer-Encoding: chunked` without actually chunking the response body."""


class BAD_ZLIB(Note):
    category = categories.CONNEG
    level = levels.BAD
    summary = u"%(response)s was compressed using GZip, but the data was corrupt."
    text = u"""\
GZip-compressed responses use zlib compression to reduce the number of bytes transferred on the
wire. However, this response could not be decompressed; the error encountered was
"`%(zlib_error)s`".

%(ok_zlib_len)s bytes were decompressed successfully before this; the erroneous chunk starts with
"`%(chunk_sample)s`"."""


class MISSING_HDRS_304(Note):
    category = categories.VALIDATION
    level = levels.WARN
    summary = u"The %(subreq_type)s response is missing required headers."
    text = u"""\
HTTP requires `304 Not Modified` responses to have certain headers, if they are also present in a
normal (e.g., `200 OK` response).

%(response)s is missing the following headers: `%(missing_hdrs)s`.

This can affect cache operation; because the headers are missing, caches might remove them from
their cached copies."""


if __name__ == '__main__':
    # do a sanity check on all of the defined messages
    import re, types
    for n, v in locals().items():
        if type(v) is types.ClassType and issubclass(v, Note) \
          and n != "Note":
            print "checking", n
            assert v.category in categories.__class__.__dict__.values(), n
            assert v.level in levels.__class__.__dict__.values(), n
            assert type(v.summary) is types.UnicodeType, n
            assert v.summary != "", n
            assert not re.search("\s{2,}", v.summary), n
            assert type(v.text) is types.UnicodeType, n
    #        assert v.text != "", n
