"""
red_speak.py - A collection of messages that the RED can emit.

Copyright (c) 2009 Mark Nottingham

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

###########################################################################

Each should be in the form:

MESSAGE_ID = (classification, level, 
    {'lang': 'message'}
    {'lang': 'long message'}
)

where 'lang' is a language tag, 'message' is a string (NO HTML) that
contains the message in that language, and 'long message' is a longer
explanation that may contain HTML.

Both message forms may contain %(var)s style variable interpolation.
"""


# message classifications
GENERAL = "General"
CACHING = "Caching"
CONNECTION = "Connection"
TESTS = "Tests"

# message levels
GOOD = 'good'
BAD = 'bad'
INFO = 'info'
WARN = 'warning'

URI_TOO_LONG = (GENERAL, BAD,
    {
    'en': "The URI is very long (%(uri_len)s characters)."
    },
    {
    'en': "Long URIs aren't supported by some implementations, including proxies. \
    A reasonable upper size limit is 8192 characters."
    }
)

SERVER_URI_TOO_LONG = (GENERAL, BAD,
    {
    'en': "The server won't accept a URI this long (%(uri_len)s characters)."
    },
    {
    'en': """The %(status)s status code means that the server can't or won't accept
    a request-uri this long."""
    }
)

URI_BAD_SYNTAX = (GENERAL, BAD,
    {
    'en': "The URI's syntax isn't valid."
    },
    {
    'en': """This URI doesn't validate successfully. Look for illegal characters \
    and other problems; see <a href='http://www.ietf.org/rfc/rfc3986.txt'>RFC3986</a> 
    for more information."""
    }
)

FIELD_NAME_BAD_SYNTAX = (GENERAL, BAD,
    {
     'en': '"%(field_name)s" is not a valid header field-name.'
    },
    {
    'en': "Header field names are limited to the TOKEN production in HTTP; i.e., \
    they can't contain parenthesis, angle brackes (&lt;&gt;), ampersands (@), \
    commas, semicolons, colons, backslashes (\\), forward slashes (/), quotes, \
    square brackets ([]), question marks, equals signs (=), curly brackets ({}) \
    spaces or tabs."
    }
)

HEADER_BLOCK_TOO_LARGE = (GENERAL, BAD,
    {
    'en': "This response's headers are very large (%(header_block_size)s)."
    },
    {
    'en': """Some implementations have limits on the total size of headers
    that they'll accept. For example, Squid's default configuration limits
    header blocks to 20k."""
    }
)

HEADER_TOO_LARGE = (GENERAL, BAD,
    {
    'en': "The %(header_name)s header is very large (%(header_size)s)."
    },
    {
    'en': """Some implementations limit the size of any single header line."""
    }
)

SINGLE_HEADER_REPEAT = (GENERAL, BAD,
    {
    'en': "Only one %(field_name)s header is allowed in a response."
    },
    {
    'en': """This header is designed to only occur once in a message. When it 
    occurs more than once, a receiver needs to choose the one to use, which
    can lead to interoperability problems, since different implementations may
    choose different instances to use."""
    }
)

BAD_SYNTAX = (GENERAL, BAD,
    {
    'en': "The %(field_name)s header's syntax isn't valid."
    },
    {
    'en': """The value for this header doesn't conform to that specified for it; see
    its definition for more information."""
    }
)

BAD_CC_SYNTAX = (GENERAL, BAD,
    {
     'en': "The %(bad_cc_attr)s Cache-Control directive's syntax is incorrect."
    },
    {
     'en': "This value must be an integer."
    }
)

RANGE_CORRECT = (TESTS, GOOD,
    {
    'en': "A ranged request returned the correct partial content."
    },
    {
    'en': """This resource advertises support for ranged requests with 
    <code>Accept-Ranges</code>; that is, it allows clients to specify that only 
    part of it should be sent. RED has tested this by requesting part 
    of this response, which was returned correctly."""
    }
)

RANGE_INCORRECT = (TESTS, BAD,
    {
    'en': 'A ranged request returned partial content, but it was incorrect.'
    },
    {
    'en': """This resource advertises support for ranged requests with 
    <code>Accept-Ranges</code>; that is, it allows clients to specify that only 
    part of the response should be sent. RED has tested this by requesting part 
    of this response, but the partial response doesn't correspond with the full 
    response retrieved at the same time. This could indicate that the range 
    implementation isn't working properly.
    <p>RED expected: %(range_expected)s
    <p>RED received: %(range_received)s"""
    }
)

RANGE_FULL = (TESTS, BAD,
    {
    'en': "A ranged request returned the full rather than partial content."
    },
    {
    'en': """This resource advertises support for ranged requests with 
    <code>Accept-Ranges</code>; that is, it allows clients to specify that only 
    part of the response should be sent. RED has tested this by requesting part 
    of this response, but the entire response was returned. In other words, 
    although the resource advertises support for partial content, it
    doesn't appear to actually do so."""
    }
)

RANGE_STATUS = (TESTS, INFO,
    {
    'en': "A ranged request returned a %(range_status)s status."
    },
    {
    'en': """This resource advertises support for ranged requests; that is, it allows
    clients to specify that only part of the response should be sent. RED has tested
    this by requesting part of this response, but a %(range_status)s 
    response code was returned, which RED was not expecting."""
    }
)

RANGE_NEG_MISMATCH = (TESTS, BAD,
    {
     'en': "Partial responses don't have the same support for compression that full ones do."
    },
    {
     'en': """This resource supports ranged requests and also supports negotiation for
     gzip compression, but doesn't support compression for both full and partial responses."""
    }
)

AGE_NOT_INT = (CACHING, BAD,
    {
    'en': "The Age header's value should be an integer."
    },
    {
    'en': """The <code>Age</code> header indicates the age of the response; i.e., 
    how long it has been cached since it was generated. The value given was not 
    an integer, so it is not a valid age."""
    }
)

AGE_NEGATIVE = (CACHING, BAD,
    {
    'en': "The Age headers' value must be a positive integer."
    },
    {
    'en': """The <code>Age</code> header indicates the age of the response; i.e., 
    how long it has been cached since it was generated. The value given was 
    negative, so it is not a valid age."""
    }
)

CL_CORRECT = (CONNECTION, GOOD,
    {
    'en': 'The Content-Length header is correct.'
    },
    {
    'en': """<code>Content-Length</code> is used by HTTP to delimit messages; 
    that is, to mark the end of one message and the beginning of the next. RED 
    has checked the length of the body and found the <code>Content-Length</code> 
    to be correct."""
    }
)

CL_INCORRECT = (CONNECTION, BAD,
    {
    'en': 'The Content-Length header is incorrect (actual body size: %(body_length)s).'
    },
    {
    'en': """<code>Content-Length</code> is used by HTTP to delimit messages; 
    that is, to mark the end of one message and the beginning of the next. RED 
    has checked the length of the body and found the <code>Content-Length</code> 
    is not correct. This can cause problems not only with connection handling, 
    but also caching, since an incomplete response is considered uncacheable."""
    }
)

CMD5_CORRECT = (GENERAL, GOOD, 
    {
    'en': 'The Content-MD5 header is correct.'
    },
    {
    'en': """<code>Content-MD5</code> is a hash of the body, and can be used to 
    ensure integrity of the response. RED has checked its value and found it to 
    be correct."""
    }
)

CMD5_INCORRECT = (GENERAL, BAD,
    {
    'en': 'The Content-MD5 header is incorrect.'
    },
    {
    'en': """<code>Content-MD5</code> is a hash of the body, and can be used to 
    ensure integrity of the response. RED has checked its value and found it to 
    be incorrect; i.e., the given <code>Content-MD5</code> does not match what 
    RED thinks it should be (%(calc_md5)s)."""
    }
)

CONNEG_GZIP = (GENERAL, GOOD,
    {
    'en': 'Content negotiation for gzip compression is supported.'
    },
    {
    'en': """HTTP supports compression of responses by negotiating for 
    <code>Content-Encoding</code>. When RED asked for a compressed response, 
    the resource provided one."""
    }
)

CONNEG_NO_GZIP = (GENERAL, INFO,
    {
    'en': 'Content negotiation for gzip compression isn\'t supported.'
    },
    {
    'en': """HTTP supports compression of responses by negotiating for 
    <code>Content-Encoding</code>. When RED asked for a compressed response, 
    the resource did not provide one."""
    }
)

CONNEG_NO_VARY = (GENERAL, BAD,
    {
    'en': "This response is negotiated, but doesn't have an appropriate Vary header."
    },
    {
    'en': """Any response that's content negotiated needs to have a
    <code>Vary</code> header that reflects the header(s) used to select the
    response.<p>
    This response was negotiated for <code>gzip</code> content encoding, so
    the <code>Vary</code> header needs to contain <code>Accept-Encoding</code>,
    the request header used."""
    }
)

CONNEG_GZIP_WITHOUT_ASKING = (GENERAL, BAD,
    {
    'en': "A gzip-compressed response was sent when it wasn't asked for."
    },
    {
    'en': """HTTP supports compression of responses by negotiating for 
    <code>Content-Encoding</code>. Even though RED didn't ask for a compressed 
    response, the resource provided one anyway. Doing so can break clients that 
    aren't expecting a compressed response."""
    }
)

BAD_DATE_SYNTAX = (GENERAL, BAD,
    {
    'en': "The %(field_name)s header's value isn't a valid date."
    },
    {
    'en': """HTTP dates have very specific syntax, and sending an invalid date can 
    cause a number of problems, especially around caching. Common problems include
    sending "1 May" instead of "01 May" (the month is a fixed-width field), and 
    sending a date in a timezone other than GMT. See 
    <a href="http://www.w3.org/Protocols/rfc2616/rfc2616-sec3.html#sec3.3">the 
    HTTP specification</a> for more information."""
    }
)

DATE_CORRECT = (GENERAL, GOOD,
    {
    'en': "The server's clock is correct."
    },
    {
    'en': """HTTP's caching model assumes reasonable synchronisation between 
    clocks on the server and client; using RED's local clock, the server's clock 
    appears to be well-synchronised."""
    }
)

DATE_INCORRECT = (CACHING, BAD,
    {
    'en': "The server's clock is %(clock_skew_string)s."
    },
    {
    'en': """HTTP's caching model assumes reasonable synchronisation between 
    clocks on the server and client; using RED's local clock, the server's clock 
    does not appear to be well-synchronised. Problems can include responses that 
    should be cacheable not being cacheable (especially if their freshness
    lifetime is short)."""
    }
)

DATE_CLOCKLESS = (CACHING, WARN,
    {
     'en': "This response doesn't have a Date header."
    },
    {
     'en': """Although HTTP allowes a server not to send a <code>Date</code> header if it
     doesn't have a local clock, this can make calculation of the response's age
     inexact."""
    }
)

DATE_CLOCKLESS_BAD_HDR = (CACHING, BAD,
    {
     'en': "Responses without a Date aren't allowed to have Expires or Last-Modified values."
    },
    {
     'en': """Because both the <code>Expires</code> and <code>Last-Modified</code>
     headers are date-based, it's necessary to know when the message was generated
     for them to be useful; otherwise, clock drift, transit times between nodes as 
     well as caching could skew their application."""
    }
)

INM_304 = (CACHING, GOOD,
    {
    'en': "If-None-Match conditional requests are supported."
    },
    {
    'en': """HTTP allows clients to make conditional requests to see if a copy 
    that they hold is still valid. Since this response has an <code>ETag</code>, 
    clients should be able to use an <code>If-None-Match</code> request header 
    for validation. RED has done this and found that the resource sends a 
    <code>304 Not Modified</code> response, indicating that it supports 
    <code>ETag</code> validation."""
    }
)

INM_FULL = (CACHING, BAD,
    {
    'en': "An If-None-Match conditional request returned the full content unchanged."
    },
    {
    'en': """HTTP allows clients to make conditional requests to see if a copy 
    that they hold is still valid. Since this response has an <code>ETag</code>, 
    clients should be able to use an <code>If-None-Match</code> request header 
    for validation. RED has done this and found that the resource sends a full 
    response even though it hadn't changed, indicating that it doesn't support 
    <code>ETag</code> validation."""
    }
)

INM_UNKNOWN = (CACHING, INFO,
    {
     'en': "An If-None-Match conditional request returned the full content, but it had changed."
    },
    {
    'en': """HTTP allows clients to make conditional requests to see if a copy 
    that they hold is still valid. Since this response has an <code>ETag</code>, 
    clients should be able to use an <code>If-None-Match</code> request header 
    for validation. RED has done this, but the response changed between the 
    original request and the validating request, so RED can't tell whether or 
    not <code>ETag</code> validation is supported."""
    }
)

INM_STATUS = (CACHING, INFO,
    {
    'en': "An If-None-Match conditional request returned a %(inm_status)s status."
    },
    {
    'en': """HTTP allows clients to make conditional requests to see if a copy 
    that they hold is still valid. Since this response has an <code>ETag</code>, 
    clients should be able to use an <code>If-None-Match</code> request header 
    for validation. RED has done this, but the response had a %(inm_status)s 
    status code, so RED can't tell whether or not <code>ETag</code> validation 
    is supported."""
    }
)

LM_FUTURE = (CACHING, BAD,
    {
    'en': "The Last-Modified time is in the future."
    },
    {
    'en': """The <code>Last-Modified</code> header indicates the last point in 
    time that the resource has changed. This response's 
    <code>Last-Modified</code> time is in the future, which doesn't have any 
    defined meaning in HTTP."""
    }
)

LM_PRESENT = (CACHING, INFO, 
    {
    'en': "The resource last changed %(last_modified_string)s."
    },
    {
    'en': """The <code>Last-Modified</code> header indicates the last point in 
    time that the resource has changed. It is used in HTTP for validating cached
    responses, and for calculating heuristic freshness in caches."""
    }
)

IMS_304 = (CACHING, GOOD,
    {
    'en': "If-Modified-Since conditional requests are supported."
    },
    {
    'en': """HTTP allows clients to make conditional requests to see if a copy 
    that they hold is still valid. Since this response has a 
    <code>Last-Modified</code> header, clients should be able to use an 
    <code>If-Modified-Since</code> request header for validation.<p>
    RED has done this and found that the resource sends a 
    <code>304 Not Modified</code> response, indicating that it supports 
    <code>Last-Modified</code> validation."""
    }
)

IMS_FULL = (CACHING, BAD,
    {
    'en': "An If-Modified-Since conditional request returned the full content unchanged."
    },
    {
    'en': """HTTP allows clients to make conditional requests to see if a copy 
    that they hold is still valid. Since this response has a 
    <code>Last-Modified</code> header, clients should be able to use an 
    <code>If-Modified-Since</code> request header for validation.<p>
    RED has done this and found that the resource sends a full response even 
    though it hadn't changed, indicating that it doesn't support 
    <code>Last-Modified</code> validation."""
    }
)

IMS_UNKNOWN = (CACHING, INFO,
    {
     'en': "An If-Modified-Since conditional request returned the full content, but it had changed."
    },
    {
    'en': """HTTP allows clients to make conditional requests to see if a copy 
    that they hold is still valid. Since this response has a 
    <code>Last-Modified</code> header, clients should be able to use an 
    <code>If-Modified-Since</code> request header for validation.<p>
    RED has done this, but the response changed between the original request and 
    the validating request, so RED can't tell whether or not 
    <code>Last-Modified</code> validation is supported."""
    }
)

IMS_STATUS = (CACHING, INFO,
    {
    'en': "An If-Modified-Since conditional request returned a %(ims_status)s status."
    },
    {
    'en': """HTTP allows clients to make conditional requests to see if a copy 
    that they hold is still valid. Since this response has a 
    <code>Last-Modified</code> header, clients should be able to use an 
    <code>If-Modified-Since</code> request header for validation.<p>
    RED has done this, but the response had a %(ims_status)s status code, so 
    RED can't tell whether or not <code>Last-Modified</code> validation is 
    supported."""
    }
)

MIME_VERSION = (GENERAL, INFO, 
    {
    'en': "The MIME-Version header generally isn't necessary in HTTP."
    },
    {
    'en': """<code>MIME_Version</code> is a MIME header, not a HTTP header; it's 
    only used when HTTP messages are moved over MIME-based protocols 
    (e.g., SMTP), which is uncommon."""
    }
)

PRAGMA_NO_CACHE = (CACHING, BAD,
    {
    'en': "Pragma: no-cache is a request directive, not a response directive."
    },
    {
    'en': """<code>Pragma</code> is a very old request header that is sometimes 
    used as a response header, even though this is not specified behaviour. 
    <code>Cache-Control: no-cache</code> is more appropriate."""
    }
)

PRAGMA_OTHER = (GENERAL, BAD,
    {
    'en': """Pragma only defines the 'no-cache' request directive, and is 
    deprecated for other uses."""
    },
    {
    'en': """<code>Pragma</code> is a very old request header that is sometimes 
    used as a response header, even though this is not specified behaviour."""
    }
)

VARY_ASTERISK = (CACHING, BAD,
    {
    'en': "Vary: * effectively makes responses for this URI uncacheable."
    },
    {
    'en': """<code>Vary *</code> indicates that responses for this resource vary 
    by some aspect that can't (or won't) be described by the server. This makes 
    this response effectively uncacheable."""
    }
)

VARY_USER_AGENT = (CACHING, BAD,
    {
     'en': "Vary: User-Agent is bad practice."
    },
    {
    'en': """"""
    }
)

VARY_INCONSISTENT = (CACHING, BAD,
    {
    'en': "The resource doesn't send Vary consistently."
    },
    {
    'en': """HTTP requires that the <code>Vary</code> response header be sent 
    consistently for all responses if they change based upon different aspects 
    of the request. This resource has both compressed and uncompressed variants 
    available, negotiated by the <code>Accept-Encoding</code> request header, 
    but it sends different Vary headers for each; '%(conneg_vary)s' when the 
    response is compressed, and '%(no_conneg_vary)s' when it is not. This can 
    cause problems for downstream caches, because they cannot consistently 
    determine what the cache key for a given URI is."""
    }
)

ETAG_DOESNT_CHANGE = (GENERAL, BAD,
    {
    'en': "The ETag doesn't change between representations."
    },
    {
    'en': """HTTP requires that the <code>ETag</code>s for two different 
    responses associated with the same URI be different as well, to help caches 
    and other receivers disambiguate them. This resource, however, sent the same
    ETag for both the compressed and uncompressed versions of it (negotiated by 
    <code>Accept-Encoding</code>. This can cause interoperability problems, 
    especially with caches."""
    }
)

VIA_PRESENT = (GENERAL, INFO,
    {
    'en': "An intermediary ('%(via_string)s') is present."
    },
    {
    'en': """The <code>Via</code> header indicates that an intermediary is 
    present between RED and the origin server for the resource."""
    }
)

NO_CACHE = (CACHING, INFO,
    {
     'en': "This response cannot be served from cache without validation."
    },
    {
     'en': """The <code>Cache-Control: no-store</code> directive means that 
     while caches <strong>can</strong> store this response, they cannot use
     it to satisfy a request unless it has been validated (either with an 
     <code>If-None-Match</code> or <code>If-Modified-Since</code> conditional) 
     for that request.<p>
     If the response doesn't have a <code>Last-Modified</code> or
     <code>ETag</code> header, it effectively can't be used by a cache."""
    }
)

CURRENT_AGE = (CACHING, INFO,
    {
     'en': "This response has been cached for %(current_age)s."
    },
    {
    'en': """The <code>Age</code> header indicates the age of the response; 
    i.e., how long it has been cached since it was generated. HTTP takes this 
    as well as any apparent clock skew into account in computing how old the 
    response already is."""
    }
)

FRESHNESS_FRESH = (CACHING, GOOD,
    {
     'en': "This response is fresh until %(freshness_left)s from now."
    },
    {
    'en': """A response can be considered fresh when its age (here, %(current_age)s)
    is less than its freshness lifetime (in this case, %(freshness_lifetime)s)."""
    }
)

FRESHNESS_STALE = (CACHING, INFO,
    {
     'en': "This response is stale."
    },
    {
    'en': """A cache considers a HTTP response stale when its age (here, %(current_age)s)
    is equal to or exceeds its freshness lifetime (in this case, %(freshness_lifetime)s)."""
    }
)

HEURISTIC_FRESHNESS = (CACHING, INFO,
    {
     'en': "A cache is allowed to calculate freshness using a heuristic." 
    },
    {
     'en': """When the response doesn't have explicit freshness information (like a <code>
     Cache-Control: max-age</code> directive, or <code>Expires</code> header), caches are
     allowed to estimate how fresh the response is using a heuristic.<p>
     Usually, but not always, this is done using the <code>Last-Modified</code> header. For 
     example, if your response was last modified a week ago, a cache might decide to consider
     the response fresh for a day."""
    }
)

STALE_SERVABLE = (CACHING, INFO,
    {
     'en': "This response can be served stale by caches."
    },
    {
    'en': """HTTP allows stale responses to be served under some circumstances; 
    for example, if the origin server can't be contacted, a stale response can 
    be used (even if it doesn't have explicit freshness information).<p>This 
    behaviour can be prevented by using the <code>Cache-Control: must-revalidate</code> 
    response directive."""
    }
)

STALE_MUST_REVALIDATE = (CACHING, INFO,
    {
     'en': "This response cannot be served stale by caches."
    },
    {
    'en': """The <code>Cache-Control: must-revalidate</code> directive forbids 
    caches from using stale responses to satisfy requests.<p>For example, 
    caches often use stale responses when they cannot connect to the origin 
    server; when this directive is present, they will return an error rather 
    than a stale response."""
    }
)

STALE_PROXY_REVALIDATE = (CACHING, INFO,
    {
     'en': "This response cannot be served stale by shared caches."
    },
    {
    'en': """The presence of the <code>Cache-Control: proxy-revalidate</code> 
    and/or <code>s-maxage</code> directives forbids shared caches (e.g., proxy 
    caches) from using stale responses to satisfy requests.<p>For example, 
    caches often use stale responses when they cannot connect to the origin 
    server; when this directive is present, they will return an error rather 
    than a stale response.<p>These directives do not affect private caches; for 
    example, those in browsers."""
    }
)

METHOD_UNCACHEABLE = (CACHING, INFO,
    {
     'en': "Responses to the %(method)s method can't be stored by caches."
    },
    {
    'en': """"""
    }
)

NO_STORE = (CACHING, INFO,
    {
     'en': "This response can't be stored by a cache."
    },
    {
    'en': """The <code>Cache-Control: no-store</code> directive indicates that 
    this response can't be stored by a cache."""
    }
)

PRIVATE_CC = (CACHING, INFO,
    {
     'en': "This response can only be stored by a private cache."
    },
    {
    'en': """The <code>Cache-Control: private</code> directive indicates that the
    response can only be stored by caches that are specific to a single user; for
    example, a browser cache. Shared caches, such as those in proxies, cannot store
    it."""
    }
)

PRIVATE_AUTH = (CACHING, INFO,
    {
     'en': "This response can only be stored by a private cache."
    },
    {
    'en': """Because the request was authenticated and this response doesn't contain
    a <code>Cache-Control: public</code> directive, this response can only be 
    stored by caches that are specific to a single user; for example, a browser 
    cache. Shared caches, such as those in proxies, cannot store
    it."""
    }
)

REDIRECT_WITHOUT_LOCATION = (GENERAL, BAD,
    {
     'en': "Redirects need to have a Location header."
    },
    {
     'en': """The %(status)s status code redirects users to another URI. The
     <code>Location</code> header is used to convey this URI, but a valid one
     isn't present in this response."""
    }
)

DEPRECATED_STATUS = (GENERAL, BAD,
    {
     'en': "The %(status)s status code is deprecated."
    },
    {
     'en': """When a status code is deprecated, it should not be used, 
     because its meaning is not well-defined enough to ensure interoperability."""
    }
)

RESERVED_STATUS = (GENERAL, BAD,
    {
     'en': "The %(status)s status code is reserved."
    },
    {
     'en': """Reserved status codes can only be used by future, standard protocol
     extensions; they are not for private use."""
    }
)

NONSTANDARD_STATUS = (GENERAL, BAD,
    {
     'en': "%(status)s is not a standard HTTP status code."
    },
    {
     'en': """Non-standard status codes are not well-defined and interoperable.
     Instead of defining your own status code, you should reuse one of the more
     generic ones; for example, 400 for a client-side problem, or 500 for a 
     server-side problem."""
    }
)