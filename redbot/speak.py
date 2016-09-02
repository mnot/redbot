"""
A collection of notes that the RED can emit.

PLEASE NOTE: the summary field is automatically HTML escaped, so it can contain arbitrary text (as
long as it's unicode).

However, the longer text field IS NOT ESCAPED, and therefore all variables to be interpolated into
it need to be escaped to be safe for use in HTML.
"""

from cgi import escape as e_html
from markdown import markdown

# URLs for relevant RFCs
rfc_base = u"http://httpwg.org/specs"
rfc7230 = u"%s/rfc7230.html" % rfc_base
rfc7231 = u"%s/rfc7231.html" % rfc_base
rfc7232 = u"%s/rfc7232.html" % rfc_base
rfc7233 = u"%s/rfc7233.html" % rfc_base
rfc7234 = u"%s/rfc7234.html" % rfc_base
rfc7235 = u"%s/rfc7235.html" % rfc_base
rfc5988 = u"%s/rfc5988.html" % rfc_base
rfc6265 = u"%s/rfc6265.html" % rfc_base


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

class URI_TOO_LONG(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = u"The URI is very long (%(uri_len)s characters)."
    text = u"""\
Long URIs aren't supported by some implementations, including proxies. A reasonable upper size
limit is 8192 characters."""

class URI_BAD_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"The URI's syntax isn't valid."
    text = u"""\
This isn't a valid URI. Look for illegal characters and other problems; see
[RFC3986](http://www.ietf.org/rfc/rfc3986.txt) for more information."""

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

class FIELD_NAME_BAD_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u'"%(field_name)s" is not a valid header field-name.'
    text = u"""\
Header names are limited to the TOKEN production in HTTP; i.e., they can't contain parenthesis,
angle brackes (<>), ampersands (@), commas, semicolons, colons, backslashes (\\), forward
slashes (/), quotes, square brackets ([]), question marks, equals signs (=), curly brackets ({})
spaces or tabs."""

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

class BAD_GZIP(Note):
    category = categories.CONNEG
    level = levels.BAD
    summary = u"%(response)s was compressed using GZip, but the header wasn't \
valid."
    text = u"""\
GZip-compressed responses have a header that contains metadata. %(response)s's header wasn't valid;
the error encountered was "`%(gzip_error)s`"."""

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

class LM_FUTURE(Note):
    category = categories.CACHING
    level = levels.BAD
    summary = u"The Last-Modified time is in the future."
    text = u"""\
The `Last-Modified` header indicates the last point in time that the resource has changed.
%(response)s's `Last-Modified` time is in the future, which doesn't have any defined meaning in
HTTP."""

class LM_PRESENT(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = u"The resource last changed %(last_modified_string)s."
    text = u"""\
The `Last-Modified` header indicates the last point in time that the resource has changed. It is
used in HTTP for validating cached responses, and for calculating heuristic freshness in caches.

This resource last changed %(last_modified_string)s."""

class CONTENT_TRANSFER_ENCODING(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = u"The Content-Transfer-Encoding header isn't necessary in HTTP."
    text = u"""\
`Content-Transfer-Encoding` is a MIME header, not a HTTP header; it's only used when HTTP messages
are moved over MIME-based protocols (e.g., SMTP), which is uncommon.

You can safely remove this header.
    """

class MIME_VERSION(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = u"The MIME-Version header isn't necessary in HTTP."
    text = u"""\
`MIME_Version` is a MIME header, not a HTTP header; it's only used when HTTP messages are moved
over MIME-based protocols (e.g., SMTP), which is uncommon.

You can safely remove this header.
    """





### Body

class CL_CORRECT(Note):
    category = categories.GENERAL
    level = levels.GOOD
    summary = u'The Content-Length header is correct.'
    text = u"""\
`Content-Length` is used by HTTP to delimit messages; that is, to mark the end of one message and
the beginning of the next. RED has checked the length of the body and found the `Content-Length` to
be correct."""

class CL_INCORRECT(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"%(response)s's Content-Length header is incorrect."
    text = u"""\
`Content-Length` is used by HTTP to delimit messages; that is, to mark the end of one message and
the beginning of the next. RED has checked the length of the body and found the `Content-Length` is
not correct. This can cause problems not only with connection handling, but also caching, since an
incomplete response is considered uncacheable.

The actual body size sent was %(body_length)s bytes."""

class CMD5_CORRECT(Note):
    category = categories.GENERAL
    level = levels.GOOD
    summary = u'The Content-MD5 header is correct.'
    text = u"""\
`Content-MD5` is a hash of the body, and can be used to ensure integrity of the response. RED has
checked its value and found it to be correct."""

class CMD5_INCORRECT(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u'The Content-MD5 header is incorrect.'
    text = u"""\
`Content-MD5` is a hash of the body, and can be used to ensure integrity of the response. RED has
checked its value and found it to be incorrect; i.e., the given `Content-MD5` does not match what
RED thinks it should be (%(calc_md5)s)."""

### Clock

class DATE_CORRECT(Note):
    category = categories.GENERAL
    level = levels.GOOD
    summary = u"The server's clock is correct."
    text = u"""\
HTTP's caching model assumes reasonable synchronisation between clocks on the server and client;
using RED's local clock, the server's clock appears to be well-synchronised."""

class DATE_INCORRECT(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"The server's clock is %(clock_skew_string)s."
    text = u"""\
Using RED's local clock, the server's clock does not appear to be well-synchronised.

HTTP's caching model assumes reasonable synchronisation between clocks on the server and client;
clock skew can cause responses that should be cacheable to be considered uncacheable (especially if
their freshness lifetime is short).

Ask your server administrator to synchronise the clock, e.g., using
[NTP](http://en.wikipedia.org/wiki/Network_Time_Protocol Network Time Protocol).
    
Apparent clock skew can also be caused by caching the response without adjusting the `Age` header;
e.g., in a reverse proxy or Content Delivery network. See [this
paper](http://www2.research.att.com/~edith/Papers/HTML/usits01/index.html) for more information. """

class AGE_PENALTY(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = u"It appears that the Date header has been changed by an intermediary."
    text = u"""\
It appears that this response has been cached by a reverse proxy or Content Delivery Network,
because the `Age` header is present, but the `Date` header is more recent than it indicates.

Generally, reverse proxies should either omit the `Age` header (if they have another means of
determining how fresh the response is), or leave the `Date` header alone (i.e., act as a normal
HTTP cache).

See [this paper](http://j.mp/S7lPL4) for more information."""

class DATE_CLOCKLESS(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = u"%(response)s doesn't have a Date header."
    text = u"""\
Although HTTP allowes a server not to send a `Date` header if it doesn't have a local clock, this
can make calculation of the response's age inexact."""

class DATE_CLOCKLESS_BAD_HDR(Note):
    category = categories.CACHING
    level = levels.BAD
    summary = u"Responses without a Date aren't allowed to have Expires or Last-Modified values."
    text = u"""\
Because both the `Expires` and `Last-Modified` headers are date-based, it's necessary to know when
the message was generated for them to be useful; otherwise, clock drift, transit times between
nodes as well as caching could skew their application."""

### Caching

class METHOD_UNCACHEABLE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = u"Responses to the %(method)s method can't be stored by caches."
    text = u"""\
"""

class CC_MISCAP(Note):
    category = categories.CACHING
    level = levels.WARN
    summary = u"The %(cc)s Cache-Control directive appears to have incorrect \
capitalisation."
    text = u"""\
Cache-Control directive names are case-sensitive, and will not be recognised by most
implementations if the capitalisation is wrong.

Did you mean to use %(cc_lower)s instead of %(cc)s?"""

class CC_DUP(Note):
    category = categories.CACHING
    level = levels.WARN
    summary = u"The %(cc)s Cache-Control directive appears more than once."
    text = u"""\
The %(cc)s Cache-Control directive is only defined to appear once; it is used more than once here,
so implementations may use different instances (e.g., the first, or the last), making their
behaviour unpredictable."""

class NO_STORE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = u"%(response)s can't be stored by a cache."
    text = u"""\
The `Cache-Control: no-store` directive indicates that this response can't be stored by a cache."""

class PRIVATE_CC(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = u"%(response)s only allows a private cache to store it."
    text = u"""\
The `Cache-Control: private` directive indicates that the response can only be stored by caches
that are specific to a single user; for example, a browser cache. Shared caches, such as those in
proxies, cannot store it."""

class PRIVATE_AUTH(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = u"%(response)s only allows a private cache to store it."
    text = u"""\
Because the request was authenticated and this response doesn't contain a `Cache-Control: public`
directive, this response can only be stored by caches that are specific to a single user; for
example, a browser cache. Shared caches, such as those in proxies, cannot store it."""

class STOREABLE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = u"""\
%(response)s allows all caches to store it."""
    text = u"""\
A cache can store this response; it may or may not be able to use it to satisfy a particular
request."""

class NO_CACHE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = u"%(response)s cannot be served from cache without validation."
    text = u"""\
The `Cache-Control: no-cache` directive means that while caches **can** store this
response, they cannot use it to satisfy a request unless it has been validated (either with an
`If-None-Match` or `If-Modified-Since` conditional) for that request."""

class NO_CACHE_NO_VALIDATOR(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = u"%(response)s cannot be served from cache without validation."
    text = u"""\
The `Cache-Control: no-cache` directive means that while caches **can** store this response, they
cannot use it to satisfy a request unless it has been validated (either with an `If-None-Match` or
`If-Modified-Since` conditional) for that request.

%(response)s doesn't have a `Last-Modified` or `ETag` header, so it effectively can't be used by a
cache."""

class VARY_ASTERISK(Note):
    category = categories.CACHING
    level = levels.WARN
    summary = u"Vary: * effectively makes this response uncacheable."
    text = u"""\
`Vary *` indicates that responses for this resource vary by some aspect that can't (or won't) be
described by the server. This makes this response effectively uncacheable."""

class VARY_USER_AGENT(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = u"Vary: User-Agent can cause cache inefficiency."
    text = u"""\
Sending `Vary: User-Agent` requires caches to store a separate copy of the response for every
`User-Agent` request header they see.

Since there are so many different `User-Agent`s, this can "bloat" caches with many copies of the
same thing, or cause them to give up on storing these responses at all.

Consider having different URIs for the various versions of your content instead; this will give
finer control over caching without sacrificing efficiency."""

class VARY_HOST(Note):
    category = categories.CACHING
    level = levels.WARN
    summary = u"Vary: Host is not necessary."
    text = u"""\
Some servers (e.g., [Apache](http://httpd.apache.org/) with
[mod_rewrite](http://httpd.apache.org/docs/2.4/mod/mod_rewrite.html)) will send `Host` in the
`Vary` header, in the belief that since it affects how the server selects what to send back, this
is necessary.

This is not the case; HTTP specifies that the URI is the basis of the cache key, and the URI
incorporates the `Host` header.

The presence of `Vary: Host` may make some caches not store an otherwise cacheable response (since
some cache implementations will not store anything that has a `Vary` header)."""

class VARY_COMPLEX(Note):
    category = categories.CACHING
    level = levels.WARN
    summary = u"This resource varies in %(vary_count)s ways."
    text = u"""\
The `Vary` mechanism allows a resource to describe the dimensions that its responses vary, or
change, over; each listed header is another dimension.

Varying by too many dimensions makes using this information impractical."""

class PUBLIC(Note):
    category = categories.CACHING
    level = levels.WARN
    summary = u"Cache-Control: public is rarely necessary."
    text = u"""\
The `Cache-Control: public` directive makes a response cacheable even when the request had an
`Authorization` header (i.e., HTTP authentication was in use).

Therefore, HTTP-authenticated (NOT cookie-authenticated) resources _may_ have use for `public` to
improve cacheability, if used judiciously.

However, other responses **do not need to contain `public`**; it does not make the
response "more cacheable", and only makes the response headers larger."""

class CURRENT_AGE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = u"%(response)s has been cached for %(age)s."
    text = u"""\
The `Age` header indicates the age of the response; i.e., how long it has been cached since it was
generated. HTTP takes this as well as any apparent clock skew into account in computing how old the
response already is."""

class FRESHNESS_FRESH(Note):
    category = categories.CACHING
    level = levels.GOOD
    summary = u"%(response)s is fresh until %(freshness_left)s from now."
    text = u"""\
A response can be considered fresh when its age (here, %(current_age)s) is less than its freshness
lifetime (in this case, %(freshness_lifetime)s)."""

class FRESHNESS_STALE_CACHE(Note):
    category = categories.CACHING
    level = levels.WARN
    summary = u"%(response)s has been served stale by a cache."
    text = u"""\
An HTTP response is stale when its age (here, %(current_age)s) is equal to or exceeds its freshness
lifetime (in this case, %(freshness_lifetime)s).

HTTP allows caches to use stale responses to satisfy requests only under exceptional circumstances;
e.g., when they lose contact with the origin server. Either that has happened here, or the cache
has ignored the response's freshness directives."""

class FRESHNESS_STALE_ALREADY(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = u"%(response)s is already stale."
    text = u"""\
A cache considers a HTTP response stale when its age (here, %(current_age)s) is equal to or exceeds
its freshness lifetime (in this case, %(freshness_lifetime)s).

HTTP allows caches to use stale responses to satisfy requests only under exceptional circumstances;
e.g., when they lose contact with the origin server."""

class FRESHNESS_HEURISTIC(Note):
    category = categories.CACHING
    level = levels.WARN
    summary = u"%(response)s allows a cache to assign its own freshness lifetime."
    text = u"""\
When responses with certain status codes don't have explicit freshness information (like a `
Cache-Control: max-age` directive, or `Expires` header), caches are allowed to estimate how fresh
it is using a heuristic.

Usually, but not always, this is done using the `Last-Modified` header. For example, if your
response was last modified a week ago, a cache might decide to consider the response fresh for a
day.

Consider adding a `Cache-Control` header; otherwise, it may be cached for longer or shorter than
you'd like."""

class FRESHNESS_NONE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = u"%(response)s can only be served by a cache under exceptional circumstances."
    text = u"""\
%(response)s doesn't have explicit freshness information (like a ` Cache-Control: max-age`
directive, or `Expires` header), and this status code doesn't allow caches to calculate their own.

Therefore, while caches may be allowed to store it, they can't use it, except in unusual
cirucumstances, such a when the origin server can't be contacted.

This behaviour can be prevented by using the `Cache-Control: must-revalidate` response directive.

Note that many caches will not store the response at all, because it is not generally useful to do
so."""

class FRESH_SERVABLE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = u"%(response)s may still be served by a cache once it becomes stale."
    text = u"""\
HTTP allows stale responses to be served under some circumstances; for example, if the origin
server can't be contacted, a stale response can be used (even if it doesn't have explicit freshness
information).

This behaviour can be prevented by using the `Cache-Control: must-revalidate` response directive."""

class STALE_SERVABLE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = u"%(response)s might be served by a cache, even though it is stale."
    text = u"""\
HTTP allows stale responses to be served under some circumstances; for example, if the origin
server can't be contacted, a stale response can be used (even if it doesn't have explicit freshness
information).

This behaviour can be prevented by using the `Cache-Control: must-revalidate` response directive."""

class FRESH_MUST_REVALIDATE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = u"%(response)s cannot be served by a cache once it becomes stale."
    text = u"""\
The `Cache-Control: must-revalidate` directive forbids caches from using stale responses to satisfy
requests.

For example, caches often use stale responses when they cannot connect to the origin server; when
this directive is present, they will return an error rather than a stale response."""

class STALE_MUST_REVALIDATE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = u"%(response)s cannot be served by a cache, because it is stale."
    text = u"""\
The `Cache-Control: must-revalidate` directive forbids caches from using stale responses to satisfy
requests.

For example, caches often use stale responses when they cannot connect to the origin server; when
this directive is present, they will return an error rather than a stale response."""

class FRESH_PROXY_REVALIDATE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = u"%(response)s cannot be served by a shared cache once it becomes stale."
    text = u"""\
The presence of the `Cache-Control: proxy-revalidate` and/or `s-maxage` directives forbids shared
caches (e.g., proxy caches) from using stale responses to satisfy requests.

For example, caches often use stale responses when they cannot connect to the origin server; when
this directive is present, they will return an error rather than a stale response.

These directives do not affect private caches; for example, those in browsers."""

class STALE_PROXY_REVALIDATE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = u"%(response)s cannot be served by a shared cache, because it is stale."
    text = u"""\
The presence of the `Cache-Control: proxy-revalidate` and/or `s-maxage` directives forbids shared
caches (e.g., proxy caches) from using stale responses to satisfy requests.

For example, caches often use stale responses when they cannot connect to the origin server; when
this directive is present, they will return an error rather than a stale response.

These directives do not affect private caches; for example, those in browsers."""

class CHECK_SINGLE(Note):
    category = categories.CACHING
    level = levels.WARN
    summary = u"Only one of the pre-check and post-check Cache-Control directives is present."
    text = u"""\
Microsoft Internet Explorer implements two `Cache-Control` extensions, `pre-check` and
`post-check`, to give more control over how its cache stores responses.

%(response)s uses only one of these directives; as a result, Internet Explorer will ignore the
directive, since it requires both to be present.

See [this blog entry](http://bit.ly/rzT0um) for more information.
     """

class CHECK_NOT_INTEGER(Note):
    category = categories.CACHING
    level = levels.WARN
    summary = u"One of the pre-check/post-check Cache-Control directives has a non-integer value."
    text = u"""\
Microsoft Internet Explorer implements two `Cache-Control` extensions, `pre-check` and
`post-check`, to give more control over how its cache stores responses.

Their values are required to be integers, but here at least one is not. As a result, Internet
Explorer will ignore the directive.

See [this blog entry](http://bit.ly/rzT0um) for more information."""

class CHECK_ALL_ZERO(Note):
    category = categories.CACHING
    level = levels.WARN
    summary = u"The pre-check and post-check Cache-Control directives are both '0'."
    text = u"""\
Microsoft Internet Explorer implements two `Cache-Control` extensions, `pre-check` and
`post-check`, to give more control over how its cache stores responses.

%(response)s gives a value of "0" for both; as a result, Internet Explorer will ignore the
directive, since it requires both to be present.

In other words, setting these to zero has **no effect** (besides wasting bandwidth),
and may trigger bugs in some beta versions of IE.

See [this blog entry](http://bit.ly/rzT0um) for more information."""

class CHECK_POST_BIGGER(Note):
    category = categories.CACHING
    level = levels.WARN
    summary = u"The post-check Cache-control directive's value is larger than pre-check's."
    text = u"""\
Microsoft Internet Explorer implements two `Cache-Control` extensions, `pre-check` and
`post-check`, to give more control over how its cache stores responses.

%(response)s assigns a higher value to `post-check` than to `pre-check`; this means that Internet
Explorer will treat `post-check` as if its value is the same as `pre-check`'s.

See [this blog entry](http://bit.ly/rzT0um) for more information."""

class CHECK_POST_ZERO(Note):
    category = categories.CACHING
    level = levels.BAD
    summary = u"The post-check Cache-control directive's value is '0'."
    text = u"""\
Microsoft Internet Explorer implements two `Cache-Control` extensions, `pre-check` and
`post-check`, to give more control over how its cache stores responses.

%(response)s assigns a value of "0" to `post-check`, which means that Internet Explorer will reload
the content as soon as it enters the browser cache, effectively **doubling the load on the server**.

See [this blog entry](http://bit.ly/rzT0um) for more information."""

class CHECK_POST_PRE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = u"%(response)s may be refreshed in the background by Internet Explorer."
    text = u"""\
Microsoft Internet Explorer implements two `Cache-Control` extensions, `pre-check` and
`post-check`, to give more control over how its cache stores responses.

Once it has been cached for more than %(post_check)s seconds, a new request will result in the
cached response being served while it is refreshed in the background. However, if it has been
cached for more than %(pre_check)s seconds, the browser will download a fresh response before
showing it to the user.

Note that these directives do not have any effect on other clients or caches.

See [this blog entry](http://bit.ly/rzT0um) for more information."""


### General Validation

class NO_DATE_304(Note):
    category = categories.VALIDATION
    level = levels.WARN
    summary = u"304 responses need to have a Date header."
    text = u"""\
HTTP requires `304 Not Modified` responses to have a `Date` header in all but the most unusual
circumstances."""

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

### ETag Validation


### Last-Modified Validation


### Status checks

class UNEXPECTED_CONTINUE(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"A 100 Continue response was sent when it wasn't asked for."
    text = u"""\
HTTP allows clients to ask a server if a request with a body (e.g., uploading a large file) will
succeed before sending it, using a mechanism called "Expect/continue".

When used, the client sends an `Expect: 100-continue`, in the request headers, and if the server is
willing to process it, it will send a `100 Continue` status code to indicate that the request
should continue.

This response has a `100 Continue` status code, but RED did not ask for it (with the `Expect`
request header). Sending this status code without it being requested can cause interoperability
problems."""

class UPGRADE_NOT_REQUESTED(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"The protocol was upgraded without being requested."
    text = u"""\
HTTP defines the `Upgrade` header as a means of negotiating a change of protocol; i.e., it allows
you to switch the protocol on a given connection from HTTP to something else.

However, it must be first requested by the client; this response contains an `Upgrade` header, even
though RED did not ask for it.

Trying to upgrade the connection without the client's participation obviously won't work."""

class CREATED_SAFE_METHOD(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = u"A new resource was created in response to a safe request."
    text = u"""\
The `201 Created` status code indicates that processing the request had the side effect of creating
a new resource.

However, the request method that RED used (%(method)s) is defined as a "safe" method; that is, it
should not have any side effects.

Creating resources as a side effect of a safe method can have unintended consequences; for example,
search engine spiders and similar automated agents often follow links, and intermediaries sometimes
re-try safe methods when they fail."""

class CREATED_WITHOUT_LOCATION(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"A new resource was created without its location being sent."
    text = u"""\
The `201 Created` status code indicates that processing the request had the side effect of creating
a new resource.

HTTP specifies that the URL of the new resource is to be indicated in the `Location` header, but it
isn't present in this response."""


class PARTIAL_WITHOUT_RANGE(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"%(response)s doesn't have a Content-Range header."
    text = u"""\
The `206 Partial Response` status code indicates that the response body is only partial.

However, for a response to be partial, it needs to have a `Content-Range` header to indicate what
part of the full response it carries. This response does not have one, and as a result clients
won't be able to process it."""

class PARTIAL_NOT_REQUESTED(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"A partial response was sent when it wasn't requested."
    text = u"""\
The `206 Partial Response` status code indicates that the response body is only partial.

However, the client needs to ask for it with the `Range` header.

RED did not request a partial response; sending one without the client requesting it leads to
interoperability problems."""

class REDIRECT_WITHOUT_LOCATION(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"Redirects need to have a Location header."
    text = u"""\
The %(status)s status code redirects users to another URI. The `Location` header is used to convey
this URI, but a valid one isn't present in this response."""

class STATUS_DEPRECATED(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"The %(status)s status code is deprecated."
    text = u"""\
When a status code is deprecated, it should not be used, because its meaning is not well-defined
enough to ensure interoperability."""

class STATUS_RESERVED(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"The %(status)s status code is reserved."
    text = u"""\
Reserved status codes can only be used by future, standard protocol extensions; they are not for
private use."""

class STATUS_NONSTANDARD(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"%(status)s is not a standard HTTP status code."
    text = u"""\
Non-standard status codes are not well-defined and interoperable. Instead of defining your own
status code, you should reuse one of the more generic ones; for example, 400 for a client-side
problem, or 500 for a server-side problem."""

class STATUS_BAD_REQUEST(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = u"The server didn't understand the request."
    text = u"""\
 """

class STATUS_FORBIDDEN(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = u"The server has forbidden this request."
    text = u"""\
 """

class STATUS_NOT_FOUND(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = u"The resource could not be found."
    text = u"""\
The server couldn't find any resource to serve for the
     given URI."""

class STATUS_NOT_ACCEPTABLE(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = u"The resource could not be found."
    text = u"""\
"""

class STATUS_CONFLICT(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = u"The request conflicted with the state of the resource."
    text = u"""\
 """

class STATUS_GONE(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = u"The resource is gone."
    text = u"""\
The server previously had a resource at the given URI, but it is no longer there."""

class STATUS_REQUEST_ENTITY_TOO_LARGE(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = u"The request body was too large for the server."
    text = u"""\
The server rejected the request because the request body sent was too large."""

class STATUS_URI_TOO_LONG(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"The server won't accept a URI this long %(uri_len)s."
    text = u"""\
The %(status)s status code means that the server can't or won't accept a request-uri this long."""

class STATUS_UNSUPPORTED_MEDIA_TYPE(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = u"The resource doesn't support this media type in requests."
    text = u"""\
 """

class STATUS_INTERNAL_SERVICE_ERROR(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = u"There was a general server error."
    text = u"""\
 """

class STATUS_NOT_IMPLEMENTED(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = u"The server doesn't implement the request method."
    text = u"""\
 """

class STATUS_BAD_GATEWAY(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = u"An intermediary encountered an error."
    text = u"""\
 """

class STATUS_SERVICE_UNAVAILABLE(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = u"The server is temporarily unavailable."
    text = u"""\
 """

class STATUS_GATEWAY_TIMEOUT(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = u"An intermediary timed out."
    text = u"""\
 """

class STATUS_VERSION_NOT_SUPPORTED(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"The request HTTP version isn't supported."
    text = u"""\
 """



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
