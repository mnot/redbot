"""
A collection of messages that the RED can emit.

Each should be in the form:

MESSAGE_ID = (classification, level,
    {'lang': u'message'}
    {'lang': u'long message'}
)

where 'lang' is a language tag, 'message' is a string (NO HTML) that
contains the message in that language, and 'long message' is a longer
explanation that may contain HTML.

Both message forms may contain %(var)s style variable interpolation.

PLEASE NOTE: the message field is automatically HTML escaped in webui.py, so
it can contain arbitrary text (as long as it's unicode). However, the long
message IS NOT ESCAPED, and therefore all variables to be interpolated into
it (but not the short version) need to be escaped.
"""

__author__ = "Mark Nottingham <mnot@mnot.net>"
__copyright__ = """\
Copyright (c) 2009-2012 Mark Nottingham

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

from cgi import escape as e_html

# message classifications
class _Classifications:
    GENERAL = u"General"
    SECURITY = u"Security"
    CONNEG = u"Content Negotiation"
    CACHING = u"Caching"
    VALIDATION = u"Validation"
    CONNECTION = u"Connection"
    RANGE = u"Partial Content"
c = _Classifications()

# message levels
class _Levels:
    GOOD = u'good'
    WARN = u'warning'
    BAD = u'bad'
    INFO = u'info'
l = _Levels()

class Message:
    """
    A message about an HTTP resource, representation, or other component
    related to the URI under test.
    """
    category = None
    level = None
    summary = {}
    text = {}
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
        return e_html(self.summary[lang] % self.vars)
        
    def show_text(self, lang):
        """
        Show the HTML text for the message as a Unicode string.
        
        The resulting string is already HTML-encoded.
        """
        return self.text[lang] % dict(
            [(k, e_html(unicode(v))) for k, v in self.vars.items()]
        )


response = {
    'this': {'en': 'This response'},
    'conneg': {'en': 'The uncompressed response'},
    'LM validation': {'en': 'The 304 response'},
    'ETag validation': {'en': 'The 304 response'},
    'range': {'en': 'The partial response'},
}

class URI_TOO_LONG(Message):
    category = c.GENERAL
    level = l.WARN
    summary = {
    'en': u"The URI is very long (%(uri_len)s characters)."
    }
    text = {
    'en': u"""Long URIs aren't supported by some implementations, including
    proxies. A reasonable upper size limit is 8192 characters."""
    }

class URI_BAD_SYNTAX(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
    'en': u"The URI's syntax isn't valid."
    }
    text = {
    'en': u"""This isn't a valid URI. Look for illegal characters and other
    problems; see <a href='http://www.ietf.org/rfc/rfc3986.txt'>RFC3986</a>
    for more information."""
    }

class FIELD_NAME_BAD_SYNTAX(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
     'en': u'"%(field_name)s" is not a valid header field-name.'
    }
    text = {
    'en': u"""Header names are limited to the TOKEN production in HTTP; i.e., 
    they can't contain parenthesis, angle brackes (&lt;&gt;), ampersands (@), 
    commas, semicolons, colons, backslashes (\\), forward slashes (/), quotes, 
    square brackets ([]), question marks, equals signs (=), curly brackets 
    ({}) spaces or tabs."""
    }

class HEADER_BLOCK_TOO_LARGE(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
    'en': u"%(response)s's headers are very large (%(header_block_size)s)."
    }
    text = {
    'en': u"""Some implementations have limits on the total size of headers
    that they'll accept. For example, Squid's default configuration limits
    header blocks to 20k."""
    }

class HEADER_TOO_LARGE(Message):
    category = c.GENERAL
    level = l.WARN
    summary = {
    'en': u"The %(header_name)s header is very large (%(header_size)s)."
    }
    text = {
    'en': u"""Some implementations limit the size of any single header
    line."""
    }

class HEADER_NAME_ENCODING(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
     'en': u"The %(header_name)s header's name contains non-ASCII characters."
    }
    text = {
     'en': u"""HTTP header field-names can only contain ASCII characters. RED
     has detected (and possibly removed) non-ASCII characters in this header
     name."""
    }

class HEADER_VALUE_ENCODING(Message):
    category = c.GENERAL
    level = l.WARN
    summary = {
     'en': u"The %(header_name)s header's value contains non-ASCII characters."
    }
    text = {
     'en': u"""HTTP headers use the ISO-8859-1 character set, but in most
     cases are pure ASCII (a subset of this encoding).<p>
     This header has non-ASCII characters, which RED has interpreted as
     being encoded in ISO-8859-1. If another encoding is used (e.g., UTF-8),
     the results may be unpredictable."""
    }

class HEADER_DEPRECATED(Message):
    category = c.GENERAL
    level = l.WARN
    summary = {
    'en': u"The %(header_name)s header is deprecated."
    }
    text = {
    'en': u"""This header field is no longer recommended for use, because of
    interoperability problems and/or lack of use. See
    <a href="%(ref)s">its documentation</a> for more information."""
    }

class SINGLE_HEADER_REPEAT(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
    'en': u"Only one %(field_name)s header is allowed in a response."
    }
    text = {
    'en': u"""This header is designed to only occur once in a message. When it
    occurs more than once, a receiver needs to choose the one to use, which
    can lead to interoperability problems, since different implementations may
    make different choices.<p>
    For the purposes of its tests, RED uses the last instance of the header
    that is present; other implementations may behave differently."""
    }

class BODY_NOT_ALLOWED(Message):
    category = c.CONNECTION
    level = l.BAD
    summary = {
     'en': u"%(response)s is not allowed to have a body."
    }
    text = {
     'en': u"""HTTP defines a few special situations where a response does not
     allow a body. This includes 101, 204 and 304 responses, as well as
     responses to the <code>HEAD</code> method.<p>
     %(response)s had a body, despite it being disallowed. Clients receiving
     it may treat the body as the next response in the connection, leading to
     interoperability and security issues."""
    }

class BAD_SYNTAX(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
    'en': u"The %(field_name)s header's syntax isn't valid."
    }
    text = {
    'en': u"""The value for this header doesn't conform to its specified 
    syntax; see <a href="%(ref_uri)s">its definition</a> for more information.
    """
    }

# Specific headers

class BAD_CC_SYNTAX(Message):
    category = c.CACHING
    level = l.BAD
    summary = {
     'en': u"The %(bad_cc_attr)s Cache-Control directive's syntax is \
incorrect."
    }
    text = {
     'en': u"This value must be an integer."
    }

class AGE_NOT_INT(Message):
    category = c.CACHING
    level = l.BAD
    summary = {
    'en': u"The Age header's value should be an integer."
    }
    text = {
    'en': u"""The <code>Age</code> header indicates the age of the response;
    i.e., how long it has been cached since it was generated. The value given 
    was not an integer, so it is not a valid age."""
    }

class AGE_NEGATIVE(Message):
    category = c.CACHING
    level = l.BAD
    summary = {
    'en': u"The Age headers' value must be a positive integer."
    }
    text = {
    'en': u"""The <code>Age</code> header indicates the age of the response;
    i.e., how long it has been cached since it was generated. The value given 
    was negative, so it is not a valid age."""
    }

class BAD_CHUNK(Message):
    category = c.CONNECTION
    level = l.BAD
    summary = {
     'en': u"%(response)s had chunked encoding errors."
    }
    text = {
     'en': u"""The response indicates it uses HTTP chunked encoding, but there
     was a problem decoding the chunking.<p>
     A valid chunk looks something like this:<p>
     <code>[chunk-size in hex]\\r\\n[chunk-data]\\r\\n</code><p>
     However, the chunk sent started like this:<p>
     <code>%(chunk_sample)s</code><p>
     This is a serious problem, because HTTP uses chunking to delimit one
     response from the next one; incorrect chunking can lead to 
     interoperability and security problems.<p>
     This issue is often caused by sending an integer chunk size instead of 
     one in hex, or by sending <code>Transfer-Encoding: chunked</code> without
     actually chunking the response body."""
    }

class BAD_GZIP(Message):
    category = c.CONNEG
    level = l.BAD
    summary = {
    'en': u"%(response)s was compressed using GZip, but the header wasn't \
valid."
    }
    text = {
    'en': u"""GZip-compressed responses have a header that contains metadata.
    %(response)s's header wasn't valid; the error encountered was
    "<code>%(gzip_error)s</code>"."""
    }

class BAD_ZLIB(Message):
    category = c.CONNEG
    level = l.BAD
    summary = {
    'en': u"%(response)s was compressed using GZip, but the data was corrupt."
    }
    text = {
    'en': u"""GZip-compressed responses use zlib compression to reduce the 
    number of bytes transferred on the wire. However, this response could not 
    be decompressed; the error encountered was 
    "<code>%(zlib_error)s</code>".<p>
    %(ok_zlib_len)s bytes were decompressed successfully before this; the 
    erroneous chunk starts with "<code>%(chunk_sample)s</code>"."""
    }

class ENCODING_UNWANTED(Message):
    category = c.CONNEG
    level = l.WARN
    summary = {
     'en': u"%(response)s contained unwanted content-codings."
    }
    text = {
     'en': u"""%(response)s's <code>Content-Encoding</code> header indicates 
     it has content-codings applied (<code>%(unwanted_codings)s</code>) that
     RED didn't ask for.<p>
     Normally, clients ask for the encodings they want in the
     <code>Accept-Encoding</code> request header. Using encodings that the
     client doesn't explicitly request can lead to interoperability 
     problems."""
    }

class TRANSFER_CODING_IDENTITY(Message):
    category = c.CONNECTION
    level = l.INFO
    summary = {
    'en': u"The identity transfer-coding isn't necessary."
    }
    text = {
    'en': u"""HTTP defines <em>transfer-codings</em> as a hop-by-hop encoding
    of the message body. The <code>identity</code> tranfer-coding was defined
    as the absence of encoding; it doesn't do anything, so it's necessary.<p>
    You can remove this token to save a few bytes."""
    }

class TRANSFER_CODING_UNWANTED(Message):
    category = c.CONNECTION
    level = l.BAD
    summary = {
     'en': u"%(response)s has unsupported transfer-coding."
    }
    text = {
     'en': u"""%(response)s's <code>Transfer-Encoding</code> header indicates 
     it has transfer-codings applied, but RED didn't ask for 
     it (or them) to be.<p>
     They are: <code>%(unwanted_codings)s</code><p>
     Normally, clients ask for the encodings they want in the
     <code>TE</code> request header. Using codings that the
     client doesn't explicitly request can lead to interoperability 
     problems."""
    }

class TRANSFER_CODING_PARAM(Message):
    category = c.CONNECTION
    level = l.WARN
    summary = {
     'en': u"%(response)s had parameters on its transfer-codings."
    }
    text = {
     'en': u"""HTTP allows transfer-codings in the
     <code>Transfer-Encoding</code> header to have optional parameters,
     but it doesn't define what they mean.<p>
     %(response)s has encodings with such paramters;
     although they're technically allowed, they may cause interoperability
     problems. They should be removed."""
    }

class BAD_DATE_SYNTAX(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
    'en': u"The %(field_name)s header's value isn't a valid date."
    }
    text = {
    'en': u"""HTTP dates have very specific syntax, and sending an invalid 
    date can cause a number of problems, especially around caching. Common 
    problems include sending "1 May" instead of "01 May" (the month is a 
    fixed-width field), and sending a date in a timezone other than GMT. See
    <a href="http://www.w3.org/Protocols/rfc2616/rfc2616-sec3.html#sec3.3">the
    HTTP specification</a> for more information."""
    }

class LM_FUTURE(Message):
    category = c.CACHING
    level = l.BAD
    summary = {
    'en': u"The Last-Modified time is in the future."
    }
    text = {
    'en': u"""The <code>Last-Modified</code> header indicates the last point 
    in time that the resource has changed. %(response)s's
    <code>Last-Modified</code> time is in the future, which doesn't have any
    defined meaning in HTTP."""
    }

class LM_PRESENT(Message):
    category = c.CACHING
    level = l.INFO
    summary = {
    'en': u"The resource last changed %(last_modified_string)s."
    }
    text = {
    'en': u"""The <code>Last-Modified</code> header indicates the last point 
    in time that the resource has changed. It is used in HTTP for validating 
    cached responses, and for calculating heuristic freshness in caches.<p>
    This resource last changed %(last_modified_string)s."""
    }

class CONTENT_TRANSFER_ENCODING(Message):
    category = c.GENERAL
    level = l.WARN
    summary = {
    'en': u"The Content-Transfer-Encoding header isn't necessary in HTTP."
    }
    text = {
    'en': u"""<code>Content-Transfer-Encoding</code> is a MIME header, not
    a HTTP header; it's only used when HTTP messages are moved over
    MIME-based protocols (e.g., SMTP), which is uncommon.<p>
    You can safely remove this header.
    """
    }

class MIME_VERSION(Message):
    category = c.GENERAL
    level = l.WARN
    summary = {
    'en': u"The MIME-Version header isn't necessary in HTTP."
    }
    text = {
    'en': u"""<code>MIME_Version</code> is a MIME header, not a HTTP header; 
    it's only used when HTTP messages are moved over MIME-based protocols
    (e.g., SMTP), which is uncommon.<p>
    You can safely remove this header.
    """
    }

class PRAGMA_NO_CACHE(Message):
    category = c.CACHING
    level = l.WARN
    summary = {
    'en': u"Pragma: no-cache is a request directive, not a response \
directive."
    }
    text = {
    'en': u"""<code>Pragma</code> is a very old request header that is 
    sometimes used as a response header, even though this is not specified 
    behaviour. <code>Cache-Control: no-cache</code> is more appropriate."""
    }

class PRAGMA_OTHER(Message):
    category = c.GENERAL
    level = l.WARN
    summary = {
    'en': u"""The Pragma header is being used in an undefined way."""
    }
    text = {
    'en': u"""HTTP only defines <code>Pragma: no-cache</code>; other uses of
    this header are deprecated."""
    }

class VIA_PRESENT(Message):
    category = c.GENERAL
    level = l.INFO
    summary = {
    'en': u"One or more intermediaries are present."
    }
    text = {
    'en': u"""The <code>Via</code> header indicates that one or more
    intermediaries are present between RED and the origin server for the
    resource.<p>
    This may indicate that a proxy is in between RED and the server, or that
    the server uses a "reverse proxy" or CDN in front of it.<p>
    %(via_list)s
    <p>
    There field has three space-separated components; first, the HTTP version
    of the message that the intermediary received, then the identity of the
    intermediary (usually but not always its hostname), and then optionally a
    product identifier or comment (usually used to identify the software being
    used)."""
    }

class LOCATION_UNDEFINED(Message):
    category = c.GENERAL
    level = l.WARN
    summary = {
     'en': u"%(response)s doesn't define any meaning for the Location header."
    }
    text = {
     'en': u"""The <code>Location</code> header is used for specific purposes
     in HTTP; mostly to indicate the URI of another resource (e.g., in
     redirection, or when a new resource is created).<p>
     In other status codes (such as this one) it doesn't have a defined 
     meaning, so any use of it won't be interoperable.<p>
     Sometimes <code>Location</code> is confused with 
     <code>Content-Location</code>, which indicates a URI for the payload 
     of the message that it appears in."""
    }

class LOCATION_NOT_ABSOLUTE(Message):
    category = c.GENERAL
    level = l.INFO
    summary = {
     'en': u"The Location header contains a relative URI."
    }
    text = {
     'en': u"""<code>Location</code> was originally specified to contain 
     an absolute, not relative, URI.<p>
     It is in the process of being updated, and most clients will work 
     around this.</p>
     The correct absolute URI is (probably):<br>
     <code>%(full_uri)s</code>"""
    }

class CONTENT_TYPE_OPTIONS(Message):
    category = c.SECURITY
    level = l.INFO
    summary = {
     'en': u"%(response)s instructs Internet Explorer not to 'sniff' its \
media type."
    }
    text = {
     'en': u"""Many Web browers "sniff" the media type of responses to figure
     out whether they're HTML, RSS or another format, no matter what the
     <code>Content-Type</code> header says.<p>
     This header instructs Microsoft's Internet Explorer not to do this, but
     to always respect the Content-Type header. It probably won't have any
     effect in other clients.<p>
     See <a href="http://bit.ly/t1UHW2">this blog entry</a>
     for more information about this header."""
    }

class CONTENT_TYPE_OPTIONS_UNKNOWN(Message):
    category = c.SECURITY
    level = l.WARN
    summary = {
     'en': u"%(response)s contains an X-Content-Type-Options header with an \
unknown value."
    }
    text = {
     'en': u"""Only one value is currently defined for this header,
     <code>nosniff</code>. Using other values here won't necessarily cause
     problems, but they probably won't have any effect either.<p>
     See <a href="http://bit.ly/t1UHW2">this blog entry</a> for more
     information about this header."""
    }

class DOWNLOAD_OPTIONS(Message):
    category = c.SECURITY
    level = l.INFO
    summary = {
     'en': u"%(response)s can't be directly opened directly by Internet \
Explorer when downloaded."
    }
    text = {
     'en': u"""When the <code>X-Download-Options</code> header is present
     with the value <code>noopen</code>, Internet Explorer users are prevented
     from directly opening a file download; instead, they must first save the
     file locally. When the locally saved file is later opened, it no longer
     executes in the security context of your site, helping to prevent script
     injection.<p>
     This header probably won't have any effect in other clients.<p>
     See <a href="http://bit.ly/sfuxWE">this blog article</a> for more
     details."""
    }

class DOWNLOAD_OPTIONS_UNKNOWN(Message):
    category = c.SECURITY
    level = l.WARN
    summary = {
     'en': u"%(response)s contains an X-Download-Options header with an \
unknown value."
    }
    text = {
     'en': u"""Only one value is currently defined for this header,
     <code>noopen</code>. Using other values here won't necessarily cause
     problems, but they probably won't have any effect either.<p>
     See <a href="http://bit.ly/sfuxWE">this blog article</a> for more
     details."""
    }

class FRAME_OPTIONS_DENY(Message):
    category = c.SECURITY
    level = l.INFO
    summary = {
     'en': u"%(response)s prevents some browsers from rendering it if it \
will be contained within a frame."
    }
    text = {
     'en': u"""The <code>X-Frame-Options</code> response header controls how
     IE8 handles HTML frames; the <code>DENY</code> value prevents this
     content from being rendered within a frame, which defends against certain
     types of attacks.<p>
     Currently this is supported by IE8 and Safari 4.<p>
     See <a href="http://bit.ly/v5Bh5Q">this blog entry</a> for more
     information.
     """
    }

class FRAME_OPTIONS_SAMEORIGIN(Message):
    category = c.SECURITY
    level = l.INFO
    summary = {
     'en': u"%(response)s prevents some browsers from rendering it if it \
will be contained within a frame on another site."
    }
    text = {
     'en': u"""The <code>X-Frame-Options</code> response header controls how
     IE8 handles HTML frames; the <code>DENY</code> value prevents this
     content from being rendered within a frame on another site, which defends
     against certain types of attacks.<p>
     Currently this is supported by IE8 and Safari 4.<p>
     See <a href="http://bit.ly/v5Bh5Q">this blog entry</a> for more
     information.
     """
    }

class FRAME_OPTIONS_UNKNOWN(Message):
    category = c.SECURITY
    level = l.WARN
    summary = {
     'en': u"%(response)s contains an X-Frame-Options header with an unknown \
value."
    }
    text = {
     'en': u"""Only two values are currently defined for this header,
     <code>DENY</code> and <code>SAMEORIGIN</code>. Using other values here
     won't necessarily cause problems, but they probably won't have any effect
     either.<p>
     See <a href="http://bit.ly/v5Bh5Q">this blog entry</a> for more
     information.
     """
    }

class SMART_TAG_NO_WORK(Message):
    category = c.GENERAL
    level = l.WARN
    summary = {
     'en': u"The %(field_name)s header doesn't have any effect on smart tags."
    }
    text = {
     'en': u"""This header doesn't have any effect on Microsoft Smart Tags,
     except in certain beta versions of IE6. To turn them off, you'll need
     to make changes in the HTML content it"""
    }

class UA_COMPATIBLE(Message):
    category = c.GENERAL
    level = l.INFO
    summary = {
     'en': u"%(response)s explicitly sets a rendering mode for Internet \
Explorer 8."
    }
    text = {
     'en': u"""Internet Explorer 8 allows responses to explicitly set the
     rendering mode used for a given page (known a the "compatibility
     mode").<p>
     See 
     <a href="http://msdn.microsoft.com/en-us/library/cc288325(VS.85).aspx">
     Microsoft's documentation</a> for more information."""
    }

class UA_COMPATIBLE_REPEAT(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
     'en': u"%(response)s has multiple X-UA-Compatible directives targeted \
at the same UA."
    }
    text = {
     'en': u"""Internet Explorer 8 allows responses to explicitly set the
     rendering mode used for a page.<p>
     This response has more than one such directive targetted at one browser;
     this may cause unpredictable results.<p>
     See 
     <a href="http://msdn.microsoft.com/en-us/library/cc288325(VS.85).aspx">
     this blog entry</a> for more information."""
    }

class XSS_PROTECTION_ON(Message):
    category = c.SECURITY
    level = l.INFO
    summary = {
     'en': u"%(response)s enables XSS filtering in IE8+."
    }
    text = {
     'en': u"""Recent versions of Internet Explorer have built-in Cross-Site
     Scripting (XSS) attack protection; they try to automatically filter
     requests that fit a particular profile.<p>
     %(response)s has explicitly enabled this protection. If IE detects a
     Cross-site scripting attack, it will "sanitise" the page to prevent
     the attack. In other words, the page will still render.<p>
     This header probably won't have any effect on other clients.<p>
     See <a href="http://bit.ly/tJbICH">this blog entry</a> for more 
     information.
     """
    }

class XSS_PROTECTION_OFF(Message):
    category = c.SECURITY
    level = l.INFO
    summary = {
     'en': u"%(response)s disables XSS filtering in IE8+."
    }
    text = {
     'en': u"""Recent versions of Internet Explorer have built-in Cross-Site
     Scripting (XSS) attack protection; they try to automatically filter
     requests that fit a particular profile.<p>
     %(response)s has explicitly disabled this protection. In some scenarios,
     this is useful to do, if the protection interferes with the
     application.<p>
     This header probably won't have any effect on other clients.<p>
     See <a href="http://bit.ly/tJbICH">this blog entry</a> for more 
     information.
     """
    }

class XSS_PROTECTION_BLOCK(Message):
    category = c.SECURITY
    level = l.INFO
    summary = {
     'en': u"%(response)s blocks XSS attacks in IE8+."
    }
    text = {
     'en': u"""Recent versions of Internet Explorer have built-in Cross-Site
     Scripting (XSS) attack protection; they try to automatically filter
     requests that fit a particular profile.<p>
     Usually, IE will rewrite the attacking HTML, so that the attack is
     neutralised, but the content can still be seen. %(response)s instructs IE
     to not show such pages at all, but rather to display an error.<p>
     This header probably won't have any effect on other clients.<p>
     See <a href="http://bit.ly/tJbICH">this blog entry</a> for more 
     information.
     """
    }


### Ranges

class UNKNOWN_RANGE(Message):
    category = c.RANGE
    level = l.WARN
    summary = {
     'en': u"%(response)s advertises support for non-standard range-units."
    }
    text = {
     'en': u"""The <code>Accept-Ranges</code> response header tells clients
     what <code>range-unit</code>s a resource is willing to process in future
     requests. HTTP only defines two: <code>bytes</code> and
     <code>none</code>.
     <p>
     Clients who don't know about the non-standard range-unit will not be
     able to use it."""
    }

class RANGE_CORRECT(Message):
    category = c.RANGE
    level = l.GOOD
    summary = {
    'en': u"A ranged request returned the correct partial content."
    }
    text = {
    'en': u"""This resource advertises support for ranged requests with
    <code>Accept-Ranges</code>; that is, it allows clients to specify that
    only part of it should be sent. RED has tested this by requesting part of
    this response, which was returned correctly."""
    }

class RANGE_INCORRECT(Message):
    category = c.RANGE
    level = l.BAD
    summary = {
    'en': u'A ranged request returned partial content, but it was incorrect.'
    }
    text = {
    'en': u"""This resource advertises support for ranged requests with
    <code>Accept-Ranges</code>; that is, it allows clients to specify that
    only part of the response should be sent. RED has tested this by
    requesting part of this response, but the partial response doesn't
    correspond with the full response retrieved at the same time. This could
    indicate that the range implementation isn't working properly.
    <p>RED sent<br/>
    <code>Range: %(range)s</code>
    <p>RED expected %(range_expected_bytes)s bytes:<br/>
    <code>%(range_expected).100s</code>
    <p>RED received %(range_received_bytes)s bytes:<br/>
    <code>%(range_received).100s</code>
    <p><em>(showing samples of up to 100 characters)</em></p>"""
    }

class RANGE_CHANGED(Message):
    category = c.RANGE
    level = l.WARN
    summary = {
    'en' : u"A ranged request returned another representation."
    }
    text = {
    'en' : u"""A new representation was retrieved when checking support of
    ranged request. This is not an error, it just indicates that RED
    cannot draw any conclusion at this time."""
    }

class RANGE_FULL(Message):
    category = c.RANGE
    level = l.WARN
    summary = {
    'en': u"A ranged request returned the full rather than partial content."
    }
    text = {
    'en': u"""This resource advertises support for ranged requests with
    <code>Accept-Ranges</code>; that is, it allows clients to specify that
    only part of the response should be sent. RED has tested this by
    requesting part of this response, but the entire response was returned. In
    other words, although the resource advertises support for partial content,
    it doesn't appear to actually do so."""
    }

class RANGE_STATUS(Message):
    category = c.RANGE
    level = l.INFO
    summary = {
    'en': u"A ranged request returned a %(range_status)s status."
    }
    text = {
    'en': u"""This resource advertises support for ranged requests; that is,
    it allows clients to specify that only part of the response should be
    sent. RED has tested this by requesting part of this response, but a
    %(enc_range_status)s response code was returned, which RED was not
    expecting."""
    }

class RANGE_NEG_MISMATCH(Message):
    category = c.RANGE
    level = l.BAD
    summary = {
     'en': u"Partial responses don't have the same support for compression \
that full ones do."
    }
    text = {
     'en': u"""This resource supports ranged requests and also supports
     negotiation for gzip compression, but doesn't support compression for
     both full and partial responses.<p>
     This can cause problems for clients when they compare the partial and
     full responses, since the partial response is expressed as a byte range,
     and compression changes the bytes."""
    }

### Body

class CL_CORRECT(Message):
    category = c.GENERAL
    level = l.GOOD
    summary = {
    'en': u'The Content-Length header is correct.'
    }
    text = {
    'en': u"""<code>Content-Length</code> is used by HTTP to delimit messages;
    that is, to mark the end of one message and the beginning of the next. RED
    has checked the length of the body and found the
    <code>Content-Length</code> to be correct."""
    }

class CL_INCORRECT(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
    'en': u"%(response)s's Content-Length header is incorrect."
    }
    text = {
    'en': u"""<code>Content-Length</code> is used by HTTP to delimit messages;
    that is, to mark the end of one message and the beginning of the next. RED
    has checked the length of the body and found the
    <code>Content-Length</code> is not correct. This can cause problems not
    only with connection handling, but also caching, since an incomplete
    response is considered uncacheable.<p>
    The actual body size sent was %(body_length)s bytes."""
    }

class CMD5_CORRECT(Message):
    category = c.GENERAL
    level = l.GOOD
    summary = {
    'en': u'The Content-MD5 header is correct.'
    }
    text = {
    'en': u"""<code>Content-MD5</code> is a hash of the body, and can be used
    to ensure integrity of the response. RED has checked its value and found
    it to be correct."""
    }

class CMD5_INCORRECT(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
    'en': u'The Content-MD5 header is incorrect.'
    }
    text = {
    'en': u"""<code>Content-MD5</code> is a hash of the body, and can be used
    to ensure integrity of the response. RED has checked its value and found
    it to be incorrect; i.e., the given <code>Content-MD5</code> does not
    match what RED thinks it should be (%(calc_md5)s)."""
    }

### Conneg

class CONNEG_GZIP_GOOD(Message):
    category = c.CONNEG
    level = l.GOOD
    summary = {
    'en': u'Content negotiation for gzip compression is supported, saving \
%(savings)s%%.'
    }
    text = {
    'en': u"""HTTP supports compression of responses by negotiating for
    <code>Content-Encoding</code>. When RED asked for a compressed response,
    the resource provided one, saving %(savings)s%% of its original size
    (from %(orig_size)s to %(gzip_size)s bytes).<p>
    The compressed response's headers are displayed."""
    }

class CONNEG_GZIP_BAD(Message):
    category = c.CONNEG
    level = l.WARN
    summary = {
    'en': u'Content negotiation for gzip compression makes the response \
%(savings)s%% larger.'
    }
    text = {
    'en': u"""HTTP supports compression of responses by negotiating for
    <code>Content-Encoding</code>. When RED asked for a compressed response,
    the resource provided one, but it was %(savings)s%% <em>larger</em> than
    the original response; from %(orig_size)s to %(gzip_size)s bytes.<p>
    Often, this happens when the uncompressed response is very small, or can't
    be compressed more; since gzip compression has some overhead, it can make
    the response larger. Turning compression <strong>off</strong> for this
    resource may slightly improve response times and save bandwidth.<p>
    The compressed response's headers are displayed."""
    }

class CONNEG_NO_GZIP(Message):
    category = c.CONNEG
    level = l.INFO
    summary = {
    'en': u'Content negotiation for gzip compression isn\'t supported.'
    }
    text = {
    'en': u"""HTTP supports compression of responses by negotiating for
    <code>Content-Encoding</code>. When RED asked for a compressed response,
    the resource did not provide one."""
    }

class CONNEG_NO_VARY(Message):
    category = c.CONNEG
    level = l.BAD
    summary = {
    'en': u"%(response)s is negotiated, but doesn't have an appropriate \
Vary header."
    }
    text = {
    'en': u"""All content negotiated responses need to have a
    <code>Vary</code> header that reflects the header(s) used to select the
    response.<p>
    %(response)s was negotiated for <code>gzip</code> content encoding, so the
    <code>Vary</code> header needs to contain <code>Accept-Encoding</code>,
    the request header used."""
    }

class CONNEG_GZIP_WITHOUT_ASKING(Message):
    category = c.CONNEG
    level = l.WARN
    summary = {
    'en': u"A gzip-compressed response was sent when it wasn't asked for."
    }
    text = {
    'en': u"""HTTP supports compression of responses by negotiating for
    <code>Content-Encoding</code>. Even though RED didn't ask for a compressed
    response, the resource provided one anyway.<p>
    It could be that the response is always compressed, but doing so can 
    break clients that aren't expecting a compressed response."""
    }

class VARY_INCONSISTENT(Message):
    category = c.CONNEG
    level = l.BAD
    summary = {
    'en': u"The resource doesn't send Vary consistently."
    }
    text = {
    'en': u"""HTTP requires that the <code>Vary</code> response header be sent
    consistently for all responses if they change based upon different aspects
    of the request.<p>
    This resource has both compressed and uncompressed variants
    available, negotiated by the <code>Accept-Encoding</code> request header,
    but it sends different Vary headers for each;<p>
    <ul>
      <li>"<code>%(conneg_vary)s</code>" when the response is compressed,
       and</li>
      <li>"<code>%(no_conneg_vary)s</code>" when it is not.</li>
    </ul>
    <p>This can cause problems for downstream caches, because they
    cannot consistently determine what the cache key for a given URI is."""
    }

class VARY_STATUS_MISMATCH(Message):
    category = c.CONNEG
    level = l.BAD
    summary = {
     'en': u"The response status is different when content negotiation \
happens."
    }
    text = {
     'en': u"""When content negotiation is used, the response status
     shouldn't change between negotiated and non-negotiated responses.<p>
     When RED send asked for a negotiated response, it got a
     <code>%(neg_status)s status code; when it didn't, it got 
     <code>%(noneg_status)s</code>.<p>
     RED hasn't checked other aspects of content-negotiation because of
     this."""
    }
    
class VARY_HEADER_MISMATCH(Message):
    category = c.CONNEG
    level = l.BAD
    summary = {
     'en': u"The %(header)s header is different when content negotiation \
happens."
    }
    text = {
     'en': u"""When content negotiation is used, the %(header)s response
     header shouldn't change between negotiated and non-negotiated
     responses."""
    }

class VARY_BODY_MISMATCH(Message):
    category = c.CONNEG
    level = l.WARN
    summary = {
     'en': u"The response body is different when content negotiation happens."
    }
    text = {
     'en': u"""When content negotiation is used, the response body
     shouldn't change between negotiated and non-negotiated
     responses.<p>
     This might be because different servers handled the two requests.<p>"""
    }

class VARY_ETAG_DOESNT_CHANGE(Message):
    category = c.CONNEG
    level = l.BAD
    summary = {
    'en': u"The ETag doesn't change between negotiated representations."
    }
    text = {
    'en': u"""HTTP requires that the <code>ETag</code>s for two different
    responses associated with the same URI be different as well, to help
    caches and other receivers disambiguate them.<p>
    This resource, however, sent the same ETag for both its compressed and
    uncompressed versions (negotiated by <code>Accept-Encoding</code>). This
    can cause interoperability problems, especially with caches."""
    }

### Clock

class DATE_CORRECT(Message):
    category = c.GENERAL
    level = l.GOOD
    summary = {
    'en': u"The server's clock is correct."
    }
    text = {
    'en': u"""HTTP's caching model assumes reasonable synchronisation between
    clocks on the server and client; using RED's local clock, the server's
    clock appears to be well-synchronised."""
    }

class DATE_INCORRECT(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
    'en': u"The server's clock is %(clock_skew_string)s."
    }
    text = {
    'en': u"""Using RED's local clock, the server's clock does not appear to 
    be well-synchronised.<p>
    HTTP's caching model assumes reasonable synchronisation between clocks on
    the server and client; clock skew can cause responses that should be
    cacheable to be considered uncacheable (especially if their freshness
    lifetime is short).<p>
    Ask your server administrator to synchronise the clock, e.g., using <a
    href="http://en.wikipedia.org/wiki/Network_Time_Protocol" title="Network
    Time Protocol">NTP</a>.</p>
    Apparent clock skew can also be caused by caching the response without
    adjusting the <code>Age</code> header; e.g., in a reverse proxy or <abbr
    title="Content Delivery Network">CDN</abbr>. See <a
    href="http://www2.research.att.com/~edith/Papers/HTML/usits01/index.html">
    this paper</a> for more information. """
    }

class AGE_PENALTY(Message):
    category = c.GENERAL
    level = l.WARN
    summary = {
     'en': u"It appears that the Date header has been changed by an \
intermediary."
    }
    text = {
     'en': u"""It appears that this response has been cached by a reverse
     proxy or <abbr title="Content Delivery Network">CDN</abbr>, because the
     <code>Age</code> header is present, but the <code>Date</code> header is
     more recent than it indicates.<p>
     Generally, reverse proxies should either omit the <code>Age</code> header
     (if they have another means of determining how fresh the response is), or
     leave the <code>Date</code> header alone (i.e., act as a normal HTTP
     cache).<p>
     See <a href="http://bit.ly/sd64Tc">this paper</a> for more
     information."""
    }

class DATE_CLOCKLESS(Message):
    category = c.GENERAL
    level = l.WARN
    summary = {
     'en': u"%(response)s doesn't have a Date header."
    }
    text = {
     'en': u"""Although HTTP allowes a server not to send a <code>Date</code>
     header if it doesn't have a local clock, this can make calculation of the
     response's age inexact."""
    }

class DATE_CLOCKLESS_BAD_HDR(Message):
    category = c.CACHING
    level = l.BAD
    summary = {
     'en': u"Responses without a Date aren't allowed to have Expires or \
Last-Modified values."
    }
    text = {
     'en': u"""Because both the <code>Expires</code> and
     <code>Last-Modified</code> headers are date-based, it's necessary to know
     when the message was generated for them to be useful; otherwise, clock
     drift, transit times between nodes as well as caching could skew their
     application."""
    }

### Caching

class METHOD_UNCACHEABLE(Message):
    category = c.CACHING
    level = l.INFO
    summary = {
     'en': u"Responses to the %(method)s method can't be stored by caches."
    }
    text = {
    'en': u""""""
    }

class CC_MISCAP(Message):
    category = c.CACHING
    level = l.WARN
    summary = {
     'en': u"The %(cc)s Cache-Control directive appears to have incorrect \
capitalisation."
    }
    text = {
     'en': u"""Cache-Control directive names are case-sensitive, and will not
     be recognised by most implementations if the capitalisation is wrong.<p>
     Did you mean to use %(cc_lower)s instead of %(cc)s?"""
    }

class CC_DUP(Message):
    category = c.CACHING
    level = l.WARN
    summary = {
     'en': u"The %(cc)s Cache-Control directive appears more than once."
    }
    text = {
     'en': u"""The %(cc)s Cache-Control directive is only defined to appear
     once; it is used more than once here, so implementations may use
     different instances (e.g., the first, or the last), making their
     behaviour unpredictable."""
    }

class NO_STORE(Message):
    category = c.CACHING
    level = l.INFO
    summary = {
     'en': u"%(response)s can't be stored by a cache."
    }
    text = {
    'en': u"""The <code>Cache-Control: no-store</code> directive indicates
    that this response can't be stored by a cache."""
    }

class PRIVATE_CC(Message):
    category = c.CACHING
    level = l.INFO
    summary = {
     'en': u"%(response)s only allows a private cache to store it."
    }
    text = {
    'en': u"""The <code>Cache-Control: private</code> directive indicates that
    the response can only be stored by caches that are specific to a single
    user; for example, a browser cache. Shared caches, such as those in
    proxies, cannot store it."""
    }

class PRIVATE_AUTH(Message):
    category = c.CACHING
    level = l.INFO
    summary = {
     'en': u"%(response)s only allows a private cache to store it."
    }
    text = {
    'en': u"""Because the request was authenticated and this response doesn't
    contain a <code>Cache-Control: public</code> directive, this response can
    only be stored by caches that are specific to a single user; for example,
    a browser cache. Shared caches, such as those in proxies, cannot store
    it."""
    }

class STOREABLE(Message):
    category = c.CACHING
    level = l.INFO
    summary = {
     'en': u"""%(response)s allows all caches to store it."""
    }
    text = {
     'en': u"""A cache can store this response; it may or may not be able to
     use it to satisfy a particular request."""
    }

class NO_CACHE(Message):
    category = c.CACHING
    level = l.INFO
    summary = {
     'en': u"%(response)s cannot be served from cache without validation."
    }
    text = {
     'en': u"""The <code>Cache-Control: no-cache</code> directive means that
     while caches <strong>can</strong> store this response, they cannot use
     it to satisfy a request unless it has been validated (either with an
     <code>If-None-Match</code> or <code>If-Modified-Since</code> conditional)
     for that request.<p>"""
    }

class NO_CACHE_NO_VALIDATOR(Message):
    category = c.CACHING
    level = l.INFO
    summary = {
     'en': u"%(response)s cannot be served from cache without validation."
    }
    text = {
     'en': u"""The <code>Cache-Control: no-cache</code> directive means that
     while caches <strong>can</strong> store this response, they cannot use
     it to satisfy a request unless it has been validated (either with an
     <code>If-None-Match</code> or <code>If-Modified-Since</code> conditional)
     for that request.<p>
     %(response)s doesn't have a <code>Last-Modified</code> or
     <code>ETag</code> header, so it effectively can't be used by a cache."""
    }

class VARY_ASTERISK(Message):
    category = c.CACHING
    level = l.WARN
    summary = {
    'en': u"Vary: * effectively makes this response uncacheable."
    }
    text = {
    'en': u"""<code>Vary *</code> indicates that responses for this resource
    vary by some aspect that can't (or won't) be described by the server. This
    makes this response effectively uncacheable."""
    }

class VARY_USER_AGENT(Message):
    category = c.CACHING
    level = l.INFO
    summary = {
     'en': u"Vary: User-Agent can cause cache inefficiency."
    }
    text = {
    'en': u"""Sending <code>Vary: User-Agent</code> requires caches to store
    a separate copy of the response for every <code>User-Agent</code> request
    header they see.<p>
    Since there are so many different <code>User-Agent</code>s, this can
    "bloat" caches with many copies of the same thing, or cause them to give
    up on storing these responses at all.<p>
    Consider having different URIs for the various versions of your content 
    instead; this will give finer control over caching without sacrificing
    efficiency."""
    }

class VARY_HOST(Message):
    category = c.CACHING
    level = l.WARN
    summary = {
     'en': u"Vary: Host is not necessary."
    }
    text = {
    'en': u"""Some servers (e.g., <a
    href="http://httpd.apache.org/">Apache</a> with <a
    href="http://httpd.apache.org/docs/2.0/mod/mod_rewrite.html">mod_rewrite</a>)
    will send <code>Host</code> in the <code>Vary</code> header, in the belief
    that since it affects how the server selects what to send back, this is
    necessary.<p>
    This is not the case; HTTP specifies that the URI is the basis of the
    cache key, and the URI incorporates the <code>Host</code> header.<p>
    The presence of <code>Vary: Host</code> may make some caches not store an
    otherwise cacheable response (since some cache implementations will not
    store anything that has a <code>Vary</code> header)."""
    }

class VARY_COMPLEX(Message):
    category = c.CACHING
    level = l.WARN
    summary = {
     'en': u"This resource varies in %(vary_count)s ways."
    }
    text = {
     'en': u"""The <code>Vary</code> mechanism allows a resource to describe
     the dimensions that its responses vary, or change, over; each listed
     header is another dimension.<p>
     Varying by too many dimensions makes using this information
     impractical."""
    }

class PUBLIC(Message):
    category = c.CACHING
    level = l.WARN
    summary = {
     'en': u"Cache-Control: public is rarely necessary."
    }
    text = {
     'en': u"""The <code>Cache-Control: public</code> directive makes a
     response cacheable even when the request had an
     <code>Authorization</code> header (i.e., HTTP authentication was in
     use).<p>
     Additionally, <a href="http://firefox.org/">Firefox</a>'s cache will
     store SSL-protected responses on disk when <code>public</code> is
     present; otherwise, they are only cached in memory.<p>
     <p>Therefore, SSL-protected or HTTP-authenticated (NOT
     cookie-authenticated) resources <em>may</em> have use for
     <code>public</code> to improve cacheability, if used judiciously.<p>
     However, other responses <strong>do not need to contain
     <code>public</code> </strong>; it does not make the response "more
     cacheable", and only makes the headers larger."""
    }

class CURRENT_AGE(Message):
    category = c.CACHING
    level = l.INFO
    summary = {
     'en': u"%(response)s has been cached for %(age)s."
    }
    text = {
    'en': u"""The <code>Age</code> header indicates the age of the response;
    i.e., how long it has been cached since it was generated. HTTP takes this
    as well as any apparent clock skew into account in computing how old the
    response already is."""
    }

class FRESHNESS_FRESH(Message):
    category = c.CACHING
    level = l.GOOD
    summary = {
     'en': u"%(response)s is fresh until %(freshness_left)s from now."
    }
    text = {
    'en': u"""A response can be considered fresh when its age (here,
    %(current_age)s) is less than its freshness lifetime (in this case,
    %(freshness_lifetime)s)."""
    }

class FRESHNESS_STALE_CACHE(Message):
    category = c.CACHING
    level = l.WARN
    summary = {
     'en': u"%(response)s has been served stale by a cache."
    }
    text = {
    'en': u"""An HTTP response is stale when its age (here, %(current_age)s)
    is equal to or exceeds its freshness lifetime (in this case,
    %(freshness_lifetime)s).<p>
    HTTP allows caches to use stale responses to satisfy requests only under
    exceptional circumstances; e.g., when they lose contact with the origin
    server. Either that has happened here, or the cache has ignored the
    response's freshness directives."""
    }

class FRESHNESS_STALE_ALREADY(Message):
    category = c.CACHING
    level = l.INFO
    summary = {
     'en': u"%(response)s is already stale."
    }
    text = {
    'en': u"""A cache considers a HTTP response stale when its age (here,
    %(current_age)s) is equal to or exceeds its freshness lifetime (in this
    case, %(freshness_lifetime)s).<p> HTTP allows caches to use stale
    responses to satisfy requests only under exceptional circumstances; e.g.,
    when they lose contact with the origin server."""
    }

class FRESHNESS_HEURISTIC(Message):
    category = c.CACHING
    level = l.WARN
    summary = {
     'en': u"%(response)s allows a cache to assign its own freshness \
lifetime."
    }
    text = {
     'en': u"""When responses with certain status codes don't have explicit
     freshness information (like a <code> Cache-Control: max-age</code>
     directive, or <code>Expires</code> header), caches are allowed to
     estimate how fresh it is using a heuristic.<p>
     Usually, but not always, this is done using the
     <code>Last-Modified</code> header. For example, if your response was last
     modified a week ago, a cache might decide to consider the response fresh
     for a day.<p>
     Consider adding a <code>Cache-Control</code> header; otherwise, it may be
     cached for longer or shorter than you'd like."""
    }

class FRESHNESS_NONE(Message):
    category = c.CACHING
    level = l.INFO
    summary = {
     'en': u"%(response)s can only be served by a cache under exceptional \
circumstances."
    }
    text = {
     'en': u"""%(response)s doesn't have explicit freshness information (like
     a <code> Cache-Control: max-age</code> directive, or <code>Expires</code>
     header), and this status code doesn't allow caches to calculate their
     own.<p>
     Therefore, while caches may be allowed to store it, they can't use it,
     except in unusual cirucumstances, such a when the origin server can't be
     contacted.<p> This behaviour can be prevented by using the
     <code>Cache-Control: must-revalidate</code> response directive.<p>
     Note that many caches will not store the response at all, because it is
     not generally useful to do so.
     """
    }

class FRESH_SERVABLE(Message):
    category = c.CACHING
    level = l.INFO
    summary = {
     'en': u"%(response)s may still be served by a cache once it becomes stale."
    }
    text = {
    'en': u"""HTTP allows stale responses to be served under some
    circumstances; for example, if the origin server can't be contacted, a
    stale response can be used (even if it doesn't have explicit freshness
    information).<p>
    This behaviour can be prevented by using the <code>Cache-Control:
    must-revalidate</code> response directive."""
    }

class STALE_SERVABLE(Message):
    category = c.CACHING
    level = l.INFO
    summary = {
     'en': u"%(response)s might be served by a cache, even though it is stale."
    }
    text = {
    'en': u"""HTTP allows stale responses to be served under some
    circumstances; for example, if the origin server can't be contacted, a
    stale response can be used (even if it doesn't have explicit freshness
    information).<p>
    This behaviour can be prevented by using the <code>Cache-Control:
    must-revalidate</code> response directive."""
    }

class FRESH_MUST_REVALIDATE(Message):
    category = c.CACHING
    level = l.INFO
    summary = {
     'en': u"%(response)s cannot be served by a cache once it becomes stale."
    }
    text = {
    'en': u"""The <code>Cache-Control: must-revalidate</code> directive
    forbids caches from using stale responses to satisfy requests.<p>For
    example, caches often use stale responses when they cannot connect to the
    origin server; when this directive is present, they will return an error
    rather than a stale response."""
    }

class STALE_MUST_REVALIDATE(Message):
    category = c.CACHING
    level = l.INFO
    summary = {
     'en': u"%(response)s cannot be served by a cache, because it is stale."
    }
    text = {
    'en': u"""The <code>Cache-Control: must-revalidate</code> directive
    forbids caches from using stale responses to satisfy requests.<p>For
    example, caches often use stale responses when they cannot connect to the
    origin server; when this directive is present, they will return an error
    rather than a stale response."""
    }

class FRESH_PROXY_REVALIDATE(Message):
    category = c.CACHING
    level = l.INFO
    summary = {
     'en': u"%(response)s cannot be served by a shared cache once it becomes \
stale."
    }
    text = {
    'en': u"""The presence of the <code>Cache-Control: proxy-revalidate</code>
    and/or <code>s-maxage</code> directives forbids shared caches (e.g., proxy
    caches) from using stale responses to satisfy requests.<p>For example,
    caches often use stale responses when they cannot connect to the origin
    server; when this directive is present, they will return an error rather
    than a stale response.<p>These directives do not affect private caches;
    for example, those in browsers."""
    }

class STALE_PROXY_REVALIDATE(Message):
    category = c.CACHING
    level = l.INFO
    summary = {
     'en': u"%(response)s cannot be served by a shared cache, because it is \
stale."
    }
    text = {
    'en': u"""The presence of the <code>Cache-Control: proxy-revalidate</code>
    and/or <code>s-maxage</code> directives forbids shared caches (e.g., proxy
    caches) from using stale responses to satisfy requests.<p>For example,
    caches often use stale responses when they cannot connect to the origin
    server; when this directive is present, they will return an error rather
    than a stale response.<p>These directives do not affect private caches;
    for example, those in browsers."""
    }

class CHECK_SINGLE(Message):
    category = c.CACHING
    level = l.WARN
    summary = {
     'en': u"Only one of the pre-check and post-check Cache-Control \
directives is present."
    }
    text = {
     'en': u"""Microsoft Internet Explorer implements two
     <code>Cache-Control</code> extensions, <code>pre-check</code> and
     <code>post-check</code>, to give more control over how its cache stores
     responses.<p> %(response)s uses only one of these directives; as a
     result, Internet Explorer will ignore the directive, since it requires
     both to be present.<p>
     See <a href="http://bit.ly/rzT0um">this blog entry</a> for more
     information.
     """
    }

class CHECK_NOT_INTEGER(Message):
    category = c.CACHING
    level = l.WARN
    summary = {
     'en': u"One of the pre-check/post-check Cache-Control directives has \
a non-integer value."
    }
    text = {
     'en': u"""Microsoft Internet Explorer implements two
     <code>Cache-Control</code> extensions, <code>pre-check</code> and
     <code>post-check</code>, to give more control over how its cache stores
     responses.<p> Their values are required to be integers, but here at least
     one is not. As a result, Internet Explorer will ignore the directive.<p>
     See <a href="http://bit.ly/rzT0um">this blog entry</a> for more
     information.
     """
    }

class CHECK_ALL_ZERO(Message):
    category = c.CACHING
    level = l.WARN
    summary = {
     'en': u"The pre-check and post-check Cache-Control directives are both \
'0'."
    }
    text = {
     'en': u"""Microsoft Internet Explorer implements two
     <code>Cache-Control</code> extensions, <code>pre-check</code> and
     <code>post-check</code>, to give more control over how its cache stores
     responses.<p> %(response)s gives a value of "0" for both; as a result,
     Internet Explorer will ignore the directive, since it requires both to be
     present.<p>
     In other words, setting these to zero has <strong>no effect</strong>
     (besides wasting bandwidth), and may trigger bugs in some beta versions
     of IE.<p>
     See <a href="http://bit.ly/rzT0um">this blog entry</a> for more
     information.
     """
    }

class CHECK_POST_BIGGER(Message):
    category = c.CACHING
    level = l.WARN
    summary = {
     'en': u"The post-check Cache-control directive's value is larger \
than pre-check's."
    }
    text = {
     'en': u"""Microsoft Internet Explorer implements two
     <code>Cache-Control</code> extensions, <code>pre-check</code> and
     <code>post-check</code>, to give more control over how its cache stores
     responses.<p> %(response)s assigns a higher value to
     <code>post-check</code> than to <code>pre-check</code>; this means that
     Internet Explorer will treat <code>post-check</code> as if its value is
     the same as <code>pre-check</code>'s.<p>
     See <a href="http://bit.ly/rzT0um">this blog entry</a> for more
     information.
     """
    }

class CHECK_POST_ZERO(Message):
    category = c.CACHING
    level = l.BAD
    summary = {
     'en': u"The post-check Cache-control directive's value is '0'."
    }
    text = {
     'en': u"""Microsoft Internet Explorer implements two
     <code>Cache-Control</code> extensions, <code>pre-check</code> and
     <code>post-check</code>, to give more control over how its cache stores
     responses.<p> %(response)s assigns a value of "0" to
     <code>post-check</code>, which means that Internet Explorer will reload
     the content as soon as it enters the browser cache, effectively
     <strong>doubling the load on the server</strong>.<p>
     See <a href="http://bit.ly/rzT0um">this blog entry</a> for more
     information.
     """
    }

class CHECK_POST_PRE(Message):
    category = c.CACHING
    level = l.INFO
    summary = {
     'en': u"%(response)s may be refreshed in the background by Internet \
Explorer."
    }
    text = {
     'en': u"""Microsoft Internet Explorer implements two
     <code>Cache-Control</code> extensions, <code>pre-check</code> and
     <code>post-check</code>, to give more control over how its cache stores
     responses.<p> Once it has been cached for more than %(post-check)s
     seconds, a new request will result in the cached response being served
     while it is refreshed in the background. However, if it has been cached
     for more than %(pre-check)s seconds, the browser will download a fresh
     response before showing it to the user.<p> Note that these directives do
     not have any effect on other clients or caches.<p>
     See <a href="http://bit.ly/rzT0um">this blog entry</a> for more
     information.
     """
    }


### General Validation

class NO_DATE_304(Message):
    category = c.VALIDATION
    level = l.WARN
    summary = {
    'en': u"304 responses need to have a Date header."
    }
    text = {
    'en': u"""HTTP requires <code>304 Not Modified</code> responses to 
    have a <code>Date</code> header in all but the most unusual 
    circumstances."""
    }

class MISSING_HDRS_304(Message):
    category = c.VALIDATION
    level = l.WARN
    summary = {
    'en': u"The %(subreq_type)s response is missing required headers."
    }
    text = {
    'en': u"""HTTP requires <code>304 Not Modified</code> responses to 
    have certain headers, if they are also present in a normal (e.g.,
    <code>200 OK</code> response).<p>
    %(response)s is missing the following headers:
    <code>%(missing_hdrs)s</code>.<p>
    This can affect cache operation; because the headers are missing,
    caches might remove them from their cached copies."""
    }

### ETag Validation

class INM_304(Message):
    category = c.VALIDATION
    level = l.GOOD
    summary = {
    'en': u"If-None-Match conditional requests are supported."
    }
    text = {
    'en': u"""HTTP allows clients to make conditional requests to see if a 
    copy that they hold is still valid. Since this response has an 
    <code>ETag</code>, clients should be able to use an 
    <code>If-None-Match</code> request header for validation. RED has done 
    this and found that the resource sends a <code>304 Not Modified</code> 
    response, indicating that it supports <code>ETag</code> validation."""
    }

class INM_FULL(Message):
    category = c.VALIDATION
    level = l.WARN
    summary = {
    'en': u"An If-None-Match conditional request returned the full content \
unchanged."
    }
    text = {
    'en': u"""HTTP allows clients to make conditional requests to see if a 
    copy that they hold is still valid. Since this response has an 
    <code>ETag</code>, clients should be able to use an 
    <code>If-None-Match</code> request header for validation.<p>
    RED has done this and found that the resource sends the same, full
    response even though it hadn't changed, indicating that it doesn't support
    <code>ETag</code> validation."""
    }

class INM_DUP_ETAG_WEAK(Message):
    category = c.VALIDATION
    level = l.INFO
    summary = {
    'en': u"During validation, the ETag didn't change, even though the \
response body did."
    }
    text = {
    'en': u"""<code>ETag</code>s are supposed to uniquely identify the
    response representation; if the content changes, so should the ETag.<p>
    However, HTTP allows reuse of an <code>ETag</code> if it's "weak", as long
    as the server is OK with the two different responses being considered
    as interchangeable by clients.<p>
    For example, if a small detail of a Web page changes, and it doesn't
    affect the overall meaning of the page, you can use the same weak 
    <code>ETag</code> to identify both versions.<p>
    If the changes are important, a different <code>ETag</code> should be 
    used.
    """
    }
    
class INM_DUP_ETAG_STRONG(Message):
    category = c.VALIDATION
    level = l.BAD
    summary = {
    'en': u"During validation, the ETag didn't change, even though the \
response body did."
    }
    text = {
    'en': u"""<code>ETag</code>s are supposed to uniquely identify the
    response representation; if the content changes, so should the ETag.<p>
    Here, the same <code>ETag</code> was used for two different responses
    during validation, which means that downstream clients and caches might
    confuse them.<p>
    If the changes between the two versions aren't important, and they can
    be used interchangeably, a "weak" ETag should be used; to do that, just
    prepend <code>W/</code>, to make it <code>W/%(etag)s</code>. Otherwise,
    a different <code>ETag</code> needs to be used.
    """
    }

class INM_UNKNOWN(Message):
    category = c.VALIDATION
    level = l.INFO
    summary = {
     'en': u"An If-None-Match conditional request returned the full \
content, but it had changed."
    }
    text = {
    'en': u"""HTTP allows clients to make conditional requests to see if a 
    copy that they hold is still valid. Since this response has an 
    <code>ETag</code>, clients should be able to use an 
    <code>If-None-Match</code> request header for validation.<p>
    RED has done this, but the response changed between the original request
    and the validating request, so RED can't tell whether or not
    <code>ETag</code> validation is supported."""
    }

class INM_STATUS(Message):
    category = c.VALIDATION
    level = l.INFO
    summary = {
    'en': u"An If-None-Match conditional request returned a %(inm_status)s \
status."
    }
    text = {
    'en': u"""HTTP allows clients to make conditional requests to see if a 
    copy that they hold is still valid. Since this response has an 
    <code>ETag</code>, clients should be able to use an 
    <code>If-None-Match</code> request header
    for validation. RED has done this, but the response had a 
    %(enc_inm_status)s status code, so RED can't tell whether or not 
    <code>ETag</code> validation is supported."""
    }

### Last-Modified Validation

class IMS_304(Message):
    category = c.VALIDATION
    level = l.GOOD
    summary = {
    'en': u"If-Modified-Since conditional requests are supported."
    }
    text = {
    'en': u"""HTTP allows clients to make conditional requests to see if a 
    copy that they hold is still valid. Since this response has a
    <code>Last-Modified</code> header, clients should be able to use an
    <code>If-Modified-Since</code> request header for validation.<p>
    RED has done this and found that the resource sends a
    <code>304 Not Modified</code> response, indicating that it supports
    <code>Last-Modified</code> validation."""
    }

class IMS_FULL(Message):
    category = c.VALIDATION
    level = l.WARN
    summary = {
    'en': u"An If-Modified-Since conditional request returned the full \
content unchanged."
    }
    text = {
    'en': u"""HTTP allows clients to make conditional requests to see if a 
    copy that they hold is still valid. Since this response has a
    <code>Last-Modified</code> header, clients should be able to use an
    <code>If-Modified-Since</code> request header for validation.<p>
    RED has done this and found that the resource sends a full response even
    though it hadn't changed, indicating that it doesn't support
    <code>Last-Modified</code> validation."""
    }

class IMS_UNKNOWN(Message):
    category = c.VALIDATION
    level = l.INFO
    summary = {
     'en': u"An If-Modified-Since conditional request returned the full \
content, but it had changed."
    }
    text = {
    'en': u"""HTTP allows clients to make conditional requests to see if a 
    copy that they hold is still valid. Since this response has a
    <code>Last-Modified</code> header, clients should be able to use an
    <code>If-Modified-Since</code> request header for validation.<p>
    RED has done this, but the response changed between the original request 
    and the validating request, so RED can't tell whether or not
    <code>Last-Modified</code> validation is supported."""
    }

class IMS_STATUS(Message):
    category = c.VALIDATION
    level = l.INFO
    summary = {
    'en': u"An If-Modified-Since conditional request returned a \
%(ims_status)s status."
    }
    text = {
    'en': u"""HTTP allows clients to make conditional requests to see if a 
    copy that they hold is still valid. Since this response has a
    <code>Last-Modified</code> header, clients should be able to use an
    <code>If-Modified-Since</code> request header for validation.<p>
    RED has done this, but the response had a %(enc_ims_status)s status code, 
    so RED can't tell whether or not <code>Last-Modified</code> validation is
    supported."""
    }

### Status checks

class UNEXPECTED_CONTINUE(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
     'en': u"A 100 Continue response was sent when it wasn't asked for."
    }
    text = {
     'en': u"""HTTP allows clients to ask a server if a request with a body
     (e.g., uploading a large file) will succeed before sending it, using
     a mechanism called "Expect/continue".<p>
     When used, the client sends an <code>Expect: 100-continue</code>, in
     the request headers, and if the server is willing to process it, it
     will send a <code> 100 Continue</code> status code to indicte that the
     request should continue.<p>
     This response has a <code>100 Continue</code> status code, but RED
     did not ask for it (with the <code>Expect</code> request header). Sending
     this status code without it being requested can cause interoperability
     problems."""
    }

class UPGRADE_NOT_REQUESTED(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
     'en': u"The protocol was upgraded without being requested."
    }
    text = {
     'en': u"""HTTP defines the <code>Upgrade</code> header as a means
     of negotiating a change of protocol; i.e., it allows you to switch
     the protocol on a given connection from HTTP to something else.<p>
     However, it must be first requested by the client; this response
     contains an <code>Upgrade</code> header, even though RED did not
     ask for it.<p>
     Trying to upgrade the connection without the client's participation
     obviously won't work."""
    }

class CREATED_SAFE_METHOD(Message):
    category = c.GENERAL
    level = l.WARN
    summary = {
     'en': u"A new resource was created in response to a safe request."
    }
    text = {
     'en': u"""The <code>201 Created</code> status code indicates that
     processing the request had the side effect of creating a new resource.<p>
     However, the request method that RED used (%(method)s) is defined as
     a "safe" method; that is, it should not have any side effects.<p>
     Creating resources as a side effect of a safe method can have unintended
     consequences; for example, search engine spiders and similar automated
     agents often follow links, and intermediaries sometimes re-try safe
     methods when they fail."""
    }

class CREATED_WITHOUT_LOCATION(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
     'en': u"A new resource was created without its location being sent."
    }
    text = {
     'en': u"""The <code>201 Created</code> status code indicates that
     processing the request had the side effect of creating a new resource.<p>
     HTTP specifies that the URL of the new resource is to be indicated in the
     <code>Location</code> header, but it isn't present in this response."""
    }

class CONTENT_RANGE_MEANINGLESS(Message):
    category = c.RANGE
    level = l.WARN
    summary = {
      'en': u"%(response)s shouldn't have a Content-Range header."
    }
    text = {
      'en': u"""HTTP only defines meaning for the <code>Content-Range</code>
      header in responses with a <code>206 Partial Content</code> or
      <code>416 Requested Range Not Satisfiable</code> status code.<p>
      Putting a <code>Content-Range</code> header in this response may
      confuse caches and clients."""
    }

class PARTIAL_WITHOUT_RANGE(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
     'en': u"%(response)s doesn't have a Content-Range header."
    }
    text = {
     'en': u"""The <code>206 Partial Response</code> status code indicates
     that the response body is only partial.<p> 
     However, for a response to be partial, it needs to have a
     <code>Content-Range</code> header to indicate what part of the full
     response it carries. This response does not have one, and as a result
     clients won't be able to process it."""
    }

class PARTIAL_NOT_REQUESTED(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
     'en': u"A partial response was sent when it wasn't requested."
    }
    text = {
     'en': u"""The <code>206 Partial Response</code> status code indicates 
     that the response body is only partial.<p>
     However, the client needs to ask for it with the <code>Range</code> 
     header.<p>
     RED did not request a partial response; sending one without the client
     requesting it leads to interoperability problems."""
    }

class REDIRECT_WITHOUT_LOCATION(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
     'en': u"Redirects need to have a Location header."
    }
    text = {
     'en': u"""The %(status)s status code redirects users to another URI. 
     The <code>Location</code> header is used to convey this URI, but a valid 
     one isn't present in this response."""
    }

class STATUS_DEPRECATED(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
     'en': u"The %(status)s status code is deprecated."
    }
    text = {
     'en': u"""When a status code is deprecated, it should not be used,
     because its meaning is not well-defined enough to ensure 
     interoperability."""
    }

class STATUS_RESERVED(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
     'en': u"The %(status)s status code is reserved."
    }
    text = {
     'en': u"""Reserved status codes can only be used by future, standard 
     protocol extensions; they are not for private use."""
    }

class STATUS_NONSTANDARD(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
     'en': u"%(status)s is not a standard HTTP status code."
    }
    text = {
     'en': u"""Non-standard status codes are not well-defined and 
     interoperable. Instead of defining your own status code, you should reuse 
     one of the more generic ones; for example, 400 for a client-side problem, 
     or 500 for a server-side problem."""
    }

class STATUS_BAD_REQUEST(Message):
    category = c.GENERAL
    level = l.WARN
    summary = {
     'en': u"The server didn't understand the request."
    }
    text = {
     'en': u""" """
    }

class STATUS_FORBIDDEN(Message):
    category = c.GENERAL
    level = l.INFO
    summary = {
     'en': u"The server has forbidden this request."
    }
    text = {
     'en': u""" """
    }

class STATUS_NOT_FOUND(Message):
    category = c.GENERAL
    level = l.INFO
    summary = {
     'en': u"The resource could not be found."
    }
    text = {
     'en': u"""The server couldn't find any resource to serve for the
     given URI."""
    }

class STATUS_NOT_ACCEPTABLE(Message):
    category = c.GENERAL
    level = l.INFO
    summary = {
     'en': u"The resource could not be found."
    }
    text = {
     'en': u""""""
    }

class STATUS_CONFLICT(Message):
    category = c.GENERAL
    level = l.INFO
    summary = {
     'en': u"The request conflicted with the state of the resource."
    }
    text = {
     'en': u""" """
    }

class STATUS_GONE(Message):
    category = c.GENERAL
    level = l.INFO
    summary = {
     'en': u"The resource is gone."
    }
    text = {
     'en': u"""The server previously had a resource at the given URI, but it
     is no longer there."""
    }

class STATUS_REQUEST_ENTITY_TOO_LARGE(Message):
    category = c.GENERAL
    level = l.INFO
    summary = {
     'en': u"The request body was too large for the server."
    }
    text = {
     'en': u"""The server rejected the request because the request body sent
     was too large."""
    }

class STATUS_URI_TOO_LONG(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
    'en': u"The server won't accept a URI this long (%(uri_len)s characters)."
    }
    text = {
    'en': u"""The %(status)s status code means that the server can't or 
    won't accept a request-uri this long."""
    }

class STATUS_UNSUPPORTED_MEDIA_TYPE(Message):
    category = c.GENERAL
    level = l.INFO
    summary = {
     'en': u"The resource doesn't support this media type in requests."
    }
    text = {
     'en': u""" """
    }

class STATUS_INTERNAL_SERVICE_ERROR(Message):
    category = c.GENERAL
    level = l.INFO
    summary = {
     'en': u"There was a general server error."
    }
    text = {
     'en': u""" """
    }

class STATUS_NOT_IMPLEMENTED(Message):
    category = c.GENERAL
    level = l.INFO
    summary = {
     'en': u"The server doesn't implement the request method."
    }
    text = {
     'en': u""" """
    }

class STATUS_BAD_GATEWAY(Message):
    category = c.GENERAL
    level = l.INFO
    summary = {
     'en': u"An intermediary encountered an error."
    }
    text = {
     'en': u""" """
    }

class STATUS_SERVICE_UNAVAILABLE(Message):
    category = c.GENERAL
    level = l.INFO
    summary = {
     'en': u"The server is temporarily unavailable."
    }
    text = {
     'en': u""" """
    }

class STATUS_GATEWAY_TIMEOUT(Message):
    category = c.GENERAL
    level = l.INFO
    summary = {
     'en': u"An intermediary timed out."
    }
    text = {
     'en': u""" """
    }

class STATUS_VERSION_NOT_SUPPORTED(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
     'en': u"The request HTTP version isn't supported."
    }
    text = {
     'en': u""" """
    }

class PARAM_STAR_QUOTED(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
     'en': u"The '%(param)s' parameter's value cannot be quoted."
    }
    text = {
     'en': u"""Parameter values that end in '*' have a specific format,
     defined in <a href="http://tools.ietf.org/html/rfc5987">RFC5987</a>,
     to allow non-ASCII text.<p>
     The <code>%(param)s</code> parameter on the <code>%(field_name)s</code>
     header has double-quotes around it, which is not valid."""
    }

class PARAM_STAR_ERROR(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
     'en': u"The %(param)s parameter's value is invalid."
    }
    text = {
     'en': u"""Parameter values that end in '*' have a specific format,
     defined in <a href="http://tools.ietf.org/html/rfc5987">RFC5987</a>,
     to allow non-ASCII text.<p>. 
     The <code>%(param)s</code> parameter on the <code>%(field_name)s</code>
     header is not valid; it needs to have three parts, separated by single
     quotes (')."""
    }

class PARAM_STAR_BAD(Message):
    category = c.GENERAL
    level = l.BAD
    summary = {
     'en': u"The %(param)s* parameter isn't allowed on the %(field_name)s \
header."
    }
    text = {
     'en': u"""Parameter values that end in '*' are reserved for 
     non-ascii text, as explained in <a 
     href="http://tools.ietf.org/html/rfc5987">RFC5987</a>.<p>
     The <code>%(param)s</code> parameter on the <code>%(field_name)s</code>
     does not allow this; you should use %(param)s without the "*" on the end (and without the associated encoding).<p>
     RED ignores the content of this parameter. 
     """
    }

class PARAM_STAR_NOCHARSET(Message):
    category = c.GENERAL
    level = l.WARN
    summary = {
     'en': u"The %(param)s parameter's value doesn't define an encoding."
    }
    text = {
     'en': u"""Parameter values that end in '*' have a specific format,
     defined in <a href="http://tools.ietf.org/html/rfc5987">RFC5987</a>,
     to allow non-ASCII text.<p>. 
     The <code>%(param)s<code> parameter on the <code>%(field_name)s</code>
     header doesn't declare its character encoding, which means that
     recipients can't understand it. It should be <code>UTF-8</code>."""
    }

class PARAM_STAR_CHARSET(Message):
    category = c.GENERAL
    level = l.WARN
    summary = {
     'en': u"The %(param)s parameter's value uses an encoding other than \
UTF-8."
    }
    text = {
     'en': u"""Parameter values that end in '*' have a specific format,
     defined in <a href="http://tools.ietf.org/html/rfc5987">RFC5987</a>,
     to allow non-ASCII text.<p>. 
     The <code>%(param)s</code> parameter on the <code>%(field_name)s</code>
     header uses the <code>'%(enc)s</code> encoding, which has
     interoperability issues on some browsers. It should be
     <code>UTF-8</code>."""
    }

class PARAM_REPEATS(Message):
    category = c.GENERAL
    level = l.WARN
    summary = {
     'en': u"The '%(param)s' parameter repeats in the %(field_name)s header."
    }
    text = {
     'en': u"""Parameters on the %(field_name)s header should not repeat; 
     implementations may handle them differently."""
    }

class PARAM_SINGLE_QUOTED(Message):
    category = c.GENERAL
    level = l.WARN
    summary = {
     'en': u"The '%(param)s' parameter on the %(field_name)s header is \
single-quoted."
    }
    text = {
     'en': u"""The <code>%(param)s</code>'s value on the %(field_name)s 
     header start and ends with a single quote ('). However, single quotes
     don't mean anything there.<p>
     This means that the value will be interpreted as
     <code>%(param_val)s</code>, <strong>not</strong>
     <code>%(param_val_unquoted)s</code>. If you intend the latter, drop
     the single quotes."""
    }

class DISPOSITION_UNKNOWN(Message):
    category = c.GENERAL
    level = l.WARN
    summary = {
     'en': u"The '%(disposition)s' Content-Disposition isn't known."
    }
    text = {
     'en': u"""The <code>Content-Disposition<code> header has two 
     widely-known values; <code>inline</code> and <code>attachment</code>.
     <code>%(disposition)s</code>  isn't recognised, and most implementations
     will default to handling it like <code>attachment</code>."""
    }

class DISPOSITION_OMITS_FILENAME(Message):
    category = c.GENERAL
    level = l.WARN
    summary = {
     'en': u"The Content-Disposition header doesn't have a 'filename' \
parameter."
    }
    text = {
     'en': u"""The <code>Content-Disposition</code> header suggests a 
     filename for clients to use when saving the file locally.<p>
     It should always contain a <code>filename</code> parameter, even when 
     the <code>filename*</code> parameter is used to carry an
     internationalised filename, so that browsers can fall back to an
     ASCII-only filename."""
    }

class DISPOSITION_FILENAME_PERCENT(Message):
    category = c.GENERAL
    level = l.WARN
    summary = {
     'en': u"The 'filename' parameter on the Content-Disposition header \
contains a '%%' character."
    }
    text = {
     'en': u"""The <code>Content-Disposition</code> header suggests a 
     filename for clients to use when saving the file locally, using 
     the <code>filename</code> parameter.<p>
     <a href="http://tools.ietf.org/html/rfc6266">RFC6266</a>
     specifies how to carry non-ASCII characters in this parameter. However,
     historically some (but not all) browsers have also decoded %%-encoded
     characters in the <code>filename</code> parameter, which means that
     they'll be treated differently depending on the browser you're using.<p>
     As a result, it's not interoperable to use percent characters in the
     <code>filename</code> parameter. Use the correct encoding in the 
     <code>filename*</code> parameter instead.
     """
    }

class DISPOSITION_FILENAME_PATH_CHAR(Message):
    category = c.GENERAL
    level = l.WARN
    summary = {
     'en': u"The filename in the Content-Disposition header contains a \
path character."
    }
    text = {
     'en': u"""The <code>Content-Disposition</code> header suggests a 
     filename for clients to use when saving the file locally, using 
     the <code>filename</code> and <code>filename*</code> parameters.<p>
     One of these parameters contains a path character ("\" or "/"), used
     to navigate between directories on common operating systems.<p>
     Because this can be used to attach the browser's host operating system
     (e.g., by saving a file to a system directory), browsers will usually
     ignore these paramters, or remove path information.<p>
     You should remove these characters.
     """
    }
    
class LINK_REV(Message):
    category = c.GENERAL
    level=l.WARN
    summary = {
     'en': u"The 'rev' parameter on the Link header is deprecated."
    }
    text = {
     'en': u"""The <code>Link</code> header, defined by 
     <a href="http://tools.ietf.org/html/rfc5988#section-5">RFC5988</a>, 
     uses the <code>rel</code> parameter to communicate the type of a link.
     <code>rev</code> is deprecated by that specification because it is 
     often confusing.<p>
     Use <code>rel</code> and an appropriate relation.
     """
    }

class LINK_BAD_ANCHOR(Message):
    category = c.GENERAL
    level=l.WARN
    summary = {
     'en': u"The 'anchor' parameter on the %(link)s Link header isn't a URI."
    }
    text = {
     'en': u"""The <code>Link</code> header, defined by 
     <a href="http://tools.ietf.org/html/rfc5988#section-5">RFC5988</a>, 
     uses the <code>anchor</code> parameter to define the context URI for 
     the link.<p>
     This parameter can be an absolute or relative URI; however, 
     <code>%(anchor)s</code> is neither.
     """
    }

class SET_COOKIE_NO_VAL(Message):
    category = c.GENERAL
    level=l.BAD
    summary = {
     'en': u"%(response)s has a Set-Cookie header that can't be parsed."
    }
    text = {
     'en': u"""This <code>Set-Cookie</code> header can't be parsed into a 
     name and a value; it must start with a <code>name=value</code>
     structure.<p>
     <p>Browsers will ignore this cookie."""
    }

class SET_COOKIE_NO_NAME(Message):
    category = c.GENERAL
    level=l.BAD
    summary = {
     'en': u"%(response)s has a Set-Cookie header without a cookie-name."
    }
    text = {
     'en': u"""This <code>Set-Cookie</code> header has an empty name; there
     needs to be a name before the <code>=</code>.<p>
     <p>Browsers will ignore this cookie."""
    }

class SET_COOKIE_BAD_DATE(Message):
    category = c.GENERAL
    level=l.WARN
    summary = {
     'en': u"The %(cookie_name)s Set-Cookie header has an invalid Expires \
date."
    }
    text = {
     'en': u"""The <code>expires</code> date on this <code>Set-Cookie</code>
     header isn't valid; see 
     <a href="http://tools.ietf.org/html/rfc6265">RFC6265</a> for details 
     of the correct format.
     """
    }

class SET_COOKIE_EMPTY_MAX_AGE(Message):
    category = c.GENERAL
    level=l.WARN
    summary = {
     'en': u"The %(cookie_name)s Set-Cookie header has an empty Max-Age."
    }
    text = {
     'en': u"""The <code>max-age</code> parameter on this
     <code>Set-Cookie</code> header doesn't have a value.<p>
     Browsers will ignore the <code>max-age</code> value as a result."""
    }

class SET_COOKIE_NON_DIGIT_MAX_AGE(Message):
    category = c.GENERAL
    level=l.WARN
    summary = {
     'en': u"The %(cookie_name)s Set-Cookie header has a non-numeric Max-Age."
    }
    text = {
     'en': u"""The <code>max-age</code> parameter on this
     <code>Set-Cookie</code> header isn't numeric.<p>
     Browsers will ignore the <code>max-age</code> value as a result."""
    }

class SET_COOKIE_EMPTY_DOMAIN(Message):
    category = c.GENERAL
    level=l.WARN
    summary = {
     'en': u"The %(cookie_name)s Set-Cookie header has an empty domain."
    }
    text = {
     'en': u"""The <code>domain</code> parameter on this
     <code>Set-Cookie</code> header is empty.<p>
     Browsers will probably ignore it as a result."""
    }

class SET_COOKIE_UNKNOWN_ATTRIBUTE(Message):
    category = c.GENERAL
    level=l.WARN
    summary = {
     'en': u"The %(cookie_name)s Set-Cookie header has an unknown attribute, \
'%(attribute)s'."
    }
    text = {
     'en': u"""This <code>Set-Cookie</code> header has an extra parameter,
     "%(attribute)s".<p>
     Browsers will ignore it.
     """
    }


if __name__ == '__main__':
    # do a sanity check on all of the defined messages
    import re, types
    for n, v in locals().items():
        if type(v) is types.ClassType and issubclass(v, Message) \
          and n != "Message":
            print "checking", n
            assert v.category in c.__class__.__dict__.values(), n
            assert v.level in l.__class__.__dict__.values(), n
            assert type(v.summary) is types.DictType, n
            assert v.summary != {}, n
            assert v.summary.has_key('en'), n
            assert not re.search("\s{2,}", v.summary['en']), n
            assert type(v.text) is types.DictType, n
            assert v.text != {}, n
            assert v.text.has_key('en'), n
