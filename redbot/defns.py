"""
Header- and Status-specific detail / definitions

Each should be in the form:

  HDR_HEADER_NAME = {'lang': u'message'}
or
  STATUS_NNN = {'lang': u'message'}

where HEADER_NAME is the header's field name in all capitals and with hyphens
replace with underscores, NNN is the three-digit status code, lang' is a
language tag, and 'message' is a description of the header that may
contain HTML.

The following %(var)s style variable interpolations are available:
  field_name - the name of the header

PLEASE NOTE: the description IS NOT ESCAPED, and therefore all variables to be
interpolated into it need to be escaped.
"""

HDR_KEEP_ALIVE = {
    'en': u"""The <code>Keep-Alive</code> header is completely optional; it
    is defined primarily because the <code>keep-alive</code> connection token
    implies that such a header exists, not because anyone actually uses it.<p>
    Some implementations (e.g., <a href="http://httpd.apache.org/">Apache</a>)
    do generate a <code>Keep-Alive</code> header to convey how many requests
    they're willing to serve on a single connection, what the connection
    timeout is and other information. However, this isn't usually used by
    clients.<p>
    It's safe to remove this header if you wish to save a few bytes in the
    response."""
}

HDR_NNCOECTION = \
HDR_CNEONCTION = \
HDR_YYYYYYYYYY = \
HDR_XXXXXXXXXX = \
HDR_X_CNECTION = \
HDR__ONNECTION = {
     'en': u"""
     The <code>%(field_name)s</code> field usually means that a HTTP load
     balancer, proxy or other intermediary in front of the server has
     rewritten the <code>Connection</code> header, to allow it to insert its
     own.<p>
     Usually, this is done so that clients won't see <code>Connection:
     close</code> so that the connection can be reused.<p>
     It takes this form because the most efficient way of assuring that
     clients don't see the header is to rearrange or change individual
     characters in its name.
     """
}

HDR_CTEONNT_LENGTH = {
     'en': u"""
     The <code>%(field_name)s</code> field usually means that a HTTP load
     balancer, proxy or other intermediary in front of the server has
     rewritten the <code>Content-Length</code> header, to allow it to insert
     its own.<p> Usually, this is done because an intermediary has dynamically
     compressed the response.<p>
     It takes this form because the most efficient way of assuring that
     clients don't see the header is to rearrange or change individual
     characters in its name.
     """
}


HDR_X_PAD_FOR_NETSCRAPE_BUG = \
HDR_X_PAD = \
HDR_XX_PAD = \
HDR_X_BROWSERALIGNMENT = {
     'en': u"""The <code>%(field_name)s</code> header is used to "pad" the
     response header size.<p>
     Very old versions of the Netscape browser had a
     bug whereby a response whose headers were exactly 256 or 257 bytes long,
     the browser would consider the response (e.g., an image) invalid.<p>
     Since the affected browsers (specifically, Netscape 2.x, 3.x and 4.0 up 
     to beta 2) are no longer widely used, it's probably safe to omit this 
     header.
     """
}

HDR_CONNECTION = {
    'en': u"""The <code>Connection</code> header allows senders to specify
        which headers are hop-by-hop; that is, those that are not forwarded
        by intermediaries. <p>It also indicates options that are
        desired for this particular connection; e.g., <code>close</code> means
        that it should not be reused."""
}

HDR_CONTENT_DISPOSITION = {
    'en': u"""The <code>Content-Disposition</code> header suggests a name
    to use when saving the file.<p>
    When the disposition (the first value) is set to <code>attachment</code>,
    it also prompts browsers to download the file, rather than display it.<p>
    See <a href="http://tools.ietf.org/html/rfc6266">RFC6266</a> for
    details."""
}

HDR_CONTENT_LENGTH = {
    'en': u"""The <code>Content-Length</code> header indicates the size
        of the body, in number of bytes. In responses to the HEAD
        method, it indicates the size of the body that would have been sent
        had the request been a GET.<p>
        If Content-Length is incorrect, persistent connections will not work,
        and caches may not store the response (since they can't be sure if
        they have the whole response)."""
}

HDR_DATE = {
    'en': u"""The <code>Date</code> header represents the time
        when the message was generated, regardless of caching that
        happened since.<p>
        It is used by caches as input to expiration calculations, and to
        detect clock drift."""
}

HDR_HOST = {
    'en': u"""The <code>Host</code> header specifies the host
        and port number (if it's not the default) of the resource
        being requested.<p>
        HTTP/1.1 requires servers to reject requests without a 
        <code>Host</code> header."""
}

HDR_TE = {
    'en': u"""The <code>TE</code> header indicates what
        transfer-codings the client is willing to accept in the
        response, and whether or not it is willing to accept
        trailer fields after the body when the response uses chunked
        transfer-coding.<p>
        The most common transfer-coding, <code>chunked</code>, doesn't need
        to be listed in <code>TE</code>."""
}

HDR_TRAILER = {
    'en': u"""The <code>Trailer</code> header indicates that the given set of
        header fields will be present in the trailer of the message, after the 
        body."""
}

HDR_TRANSFER_ENCODING = {
    'en': u"""The <code>Transfer-Encoding</code> header indicates what
        (if any) type of transformation has been applied to
        the message body.<p>
        This differs from <code>Content-Encoding</code> in that
        transfer-codings are a property of the message, not of the
        representation; i.e., it will be removed by the next "hop", whereas
        content-codings are end-to-end.<p> 
        The most commonly used transfer-coding is <code>chunked</code>, which
        allows persistent connections to be used without knowing the entire
        body's length."""
}

HDR_UPGRADE = {
    'en': u"""The <code>Upgrade</code> header allows the client to
        specify what additional communication protocols it
        supports and would like to use if the server finds
        it appropriate to switch protocols. Servers use it to confirm
        upgrade to a specific protocol."""
}

HDR_VIA = {
    'en': u"""The <code>Via</code> header is added to requests and responses
    by proxies and other HTTP intermediaries.
        It can
        be used to help avoid request loops and identify the protocol
        capabilities of all senders along the request/response chain."""
}

HDR_ALLOW = {
    'en': u"""The <code>Allow</code> header advertises the set of methods
        that are supported by the resource."""
}

HDR_EXPECT = {
    'en': u"""The <code>Expect</code> header is used to indicate that
        particular server behaviors are required by the client.<p>
        Currently, it has one use; the <code>100-continue</code> directive,
        which indicates that the client wants the server to indicate that the
        request is acceptable before the request body is sent.<p>
        If the expectation isn't met, the server will generate a
        <code>417 Expectation Failed</code> response."""
}

HDR_FROM = {
    'en': u"""The <code>From</code> header contains an
        e-mail address for the user.<p>
        It is not commonly used, because servers don't often record or
        otherwise use it."""
}

HDR_LOCATION = {
    'en': u"""The <code>Location</code> header is used in <code>3xx</code>
        responses to redirect the recipient to a different location to
        complete the request.<p>In <code>201 Created</code> responses, it
        identifies a newly created resource.<p>
"""
}

HDR_MAX_FORWARDS = {
    'en': u"""The <code>Max-Forwards</code> header allows
        for the TRACE and OPTIONS methods to limit the
        number of times the message can be forwarded the
        request to the next server (e.g., proxy or gateway).<p>
        This can be useful when the client is attempting to trace a
        request which appears to be looping."""
}

HDR_REFERER = {
    'en': u"""The <code>Referer</code> [sic] header allows the client to
        specify the address of the resource from where the request URI was
        obtained (the "referrer", albeit misspelled)."""
}

HDR_RETRY_AFTER = {
    'en': u"""The <code>Retry-After</code> header can be used with a
        <code>503 Service Unavailable</code> response to indicate how long
        the service is expected to be unavailable to the
        requesting client.<p>
        The value of this field can be either a date or an integer
        number of seconds."""
}

HDR_SERVER = {
    'en': u"""The <code>Server</code> header contains information about
        the software used by the origin server to handle the
        request."""
}

HDR_USER_AGENT = {
    'en': u"""The <code>User-Agent</code> header contains information
        about the user agent originating the request. """
}

HDR_ACCEPT = {
    'en': u"""The <code>Accept</code> header can be used to specify
        the media types which are acceptable for the
        response."""
}

HDR_ACCEPT_CHARSET = {
    'en': u"""The <code>Accept-Charset</code> header can be used to
        indicate what character sets are acceptable for the
        response."""
}

HDR_ACCEPT_ENCODING = {
    'en': u"""The <code>Accept-Encoding</code> header can be used to
        restrict the content-codings that are
        acceptable in the response."""
}

HDR_ACCEPT_LANGUAGE = {
    'en': u"""The <code>Accept-Language</code> header can be used to
        restrict the set of natural languages
        that are preferred as a response to the request."""
}

HDR_CONTENT_ENCODING = {
    'en': u"""The <code>Content-Encoding</code> header's value
        indicates what additional content codings have been
        applied to the body, and thus what decoding
        mechanisms must be applied in order to obtain the
        media-type referenced by the Content-Type header
        field.<p>
        Content-Encoding is primarily used to allow a
        document to be compressed without losing the
        identity of its underlying media type; e.g.,
        <code>gzip</code> and <code>deflate</code>."""
}

HDR_CONTENT_LANGUAGE = {
    'en': u"""The <code>Content-Language</code> header describes the
        natural language(s) of the intended audience.
        Note that this might not convey all of the
        languages used within the body."""
}

HDR_CONTENT_LOCATION = {
    'en': u"""The <code>Content-Location</code> header can used to
        supply an address for the representation when it is accessible from a
        location separate from the request URI."""
}

HDR_CONTENT_MD5 = {
    'en': u"""The <code>Content-MD5</code> header is
        an MD5 digest of the body, and  provides an end-to-end
        message integrity check (MIC).<p>
        Note that while a MIC is good for
        detecting accidental modification of the body
        in transit, it is not proof against malicious
        attacks."""
}

HDR_CONTENT_TYPE = {
    'en': u"""The <code>Content-Type</code> header indicates the media
        type of the body sent to the recipient or, in
        the case of responses to the HEAD method, the media type that
        would have been sent had the request been a GET."""
}

HDR_MIME_VERSION = {
    'en': u"""HTTP is not a MIME-compliant protocol. However, HTTP/1.1
        messages can include a single MIME-Version general-
        header field to indicate what version of the MIME
        protocol was used to construct the message. Use of
        the MIME-Version header field indicates that the
        message is in full compliance with the MIME
        protocol."""
}

HDR_ETAG = {
    'en': u"""The <code>ETag</code> header provides an opaque identifier
    for the representation."""
}

HDR_IF_MATCH = {
    'en': u"""The <code>If-Match</code> header makes a request
        conditional. A client that has one or more
        representations previously obtained from the resource can
        verify that one of them is current by
        including a list of their associated entity tags in
        the If-Match header field.<p>
        This allows
        efficient updates of cached information with a
        minimum amount of transaction overhead. It is also
        used, on updating requests, to prevent inadvertent
        modification of the wrong version of a resource. As
        a special case, the value "*" matches any current
        representation of the resource."""
}

HDR_IF_MODIFIED_SINCE = {
    'en': u"""The <code>If-Modified-Since</code> header is used with a
        method to make it conditional: if the requested
        variant has not been modified since the time
        specified in this field, a representation will not be
        returned from the server; instead, a 304 (Not
        Modified) response will be returned without any
        body."""
}

HDR_IF_NONE_MATCH = {
    'en': u"""The <code>If-None-Match</code> header makes a request
        conditional. A client that has one or
        more representations previously obtained from the resource
        can verify that none of them is current by
        including a list of their associated entity tags in
        the If-None-Match header field.<p>
        This allows efficient updates of cached
        information with a minimum amount of transaction
        overhead. It is also used to prevent a method (e.g.
        PUT) from inadvertently modifying an existing
        resource when the client believes that the resource
        does not exist."""
}

HDR_IF_UNMODIFIED_SINCE = {
    'en': u"""The <code>If-Unmodified-Since</code> header makes a request
        conditional."""
}

HDR_LAST_MODIFIED = {
    'en': u"""The <code>Last-Modified</code> header indicates the time
        that the origin server believes the
        representation was last modified."""
}

HDR_ACCEPT_RANGES = {
    'en': u"""The <code>Accept-Ranges</code> header allows the server to
        indicate that it accepts range requests for a
        resource."""
}

HDR_CONTENT_RANGE = {
    'en': u"""The <code>Content-Range</code> header is sent with a
        partial body to specify where in the full
        body the partial body should be applied."""
}

HDR_AGE = {
    'en': u"""The <code>Age</code> header conveys the sender's estimate
        of the amount of time since the response (or its
        validation) was generated at the origin server."""
}

HDR_CACHE_CONTROL = {
    'en': u"""The <code>Cache-Control</code> header is used to specify
        directives that must be obeyed by all caches along
        the request/response chain. Cache
        directives are unidirectional in that the presence
        of a directive in a request does not imply that the
        same directive is in effect in the response."""
}

HDR_EXPIRES = {
    'en': u"""The <code>Expires</code> header gives a time after
        which the response is considered stale."""
}

HDR_PRAGMA = {
    'en': u"""The <code>Pragma</code> header is used to include
        implementation-specific directives that might apply
        to any recipient along the request/response chain.<p>
        This header is deprecated, in favour of <code>Cache-Control</code>.
"""
}

HDR_VARY = {
    'en': u"""The <code>Vary</code> header indicates the set
        of request headers that determines whether a cache is permitted to
        use the response to reply to a subsequent request
        without validation.<p>
        In uncacheable or stale responses, the Vary field value advises the
        user agent about the criteria that were used to select the
        representation."""
}

HDR_WARNING = {
    'en': u"""The <code>Warning</code> header is used to carry additional
        information about the status or transformation of a
        message that might not be reflected in it.
        This information is typically used to warn about
        possible incorrectness introduced by caching
        operations or transformations applied to the
        body of the message."""
}

HDR_AUTHORIZATION = {
    'en': u"""The <code>Authorization</code> request header
        contains authentication information
        for the user agent to the origin server."""
}

HDR_PROXY_AUTHENTICATE = {
    'en': u"""The <code>Proxy-Authenticate</code> response header
        consists of a challenge
        that indicates the authentication scheme and
        parameters applicable to the proxy for this request-
        target."""
}

HDR_PROXY_AUTHORIZATION = {
    'en': u"""The <code>Proxy-Authorization</code> request header
        contains authentication information for the
        user agent to the proxy and/or realm of the
        resource being requested."""
}

HDR_WWW_AUTHENTICATE = {
    'en': u"""The <code>WWW-Authenticate</code> response header
        consists of at least one challenge that
        indicates the authentication scheme(s) and
        parameters applicable."""
}

HDR_SET_COOKIE = {
    'en': u"""The <code>Set-Cookie</code> response header sets
    a stateful "cookie" on the client, to be included in future
    requests to the server."""
}

HDR_SET_COOKIE2 = {
    'en': u"""The <code>Set-Cookie2</code> header has been 
        deprecated; use <code>Set-Cookie</code> instead."""
}

HDR_X_CACHE = {
    'en': u"""The <code>X-Cache</code> header is used by some caches to
    indicate whether or not the response was served from cache; if it
    contains <code>HIT</code>, it was."""
}

HDR_X_CACHE_LOOKUP = {
    'en': u"""The <code>X-Cache-Lookup</code> header is used by some caches
    to show whether there was a response in cache for this URL; if it
    contains <code>HIT</code>, it was in cache (but not necessarily used).    
    """
}