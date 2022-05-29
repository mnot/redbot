# pylint: disable=too-many-public-methods

"""
The Resource Expert Droid Status Code Checker.
"""

from functools import partial
from typing import List

from thor.http import header_names, safe_methods

from redbot.message import HttpRequest, HttpResponse
from redbot.speak import Note, levels, categories
from redbot.type import StrHeaderListType


def get_header(hdr_tuples: StrHeaderListType, name: str) -> List[str]:
    """
    Given a list of (name, value) header tuples and a header name (lowercase),
    return a list of all values for that header.

    This includes header lines with multiple values separated by a comma;
    such headers will be split into separate values. As a result, it is NOT
    safe to use this on headers whose values may include a comma (e.g.,
    Set-Cookie, or any value with a quoted string).
    """
    return [
        v.strip()
        for v in sum(
            [l.split(",") for l in [i[1] for i in hdr_tuples if i[0].lower() == name]],
            [],
        )
    ]


class StatusChecker:
    """
    Given a response, check out the status code and perform
    appropriate tests on it.

    Additional tests will be performed if the request is available.
    """

    def __init__(self, response: HttpResponse, request: HttpRequest = None) -> None:
        assert response.is_request is False
        self.request = request
        self.response = response
        self.add_note = partial(response.add_note, status=response.status_code)
        try:
            status_m = getattr(self, f"status{response.status_code}")
        except AttributeError:
            self.add_note("status", STATUS_NONSTANDARD)
            return
        status_m()

    def status100(self) -> None:  # Continue
        if self.request and not "100-continue" in get_header(
            self.request.headers, "expect"
        ):
            self.add_note("status", UNEXPECTED_CONTINUE)

    def status101(self) -> None:  # Switching Protocols
        if self.request and "upgrade" not in header_names(self.request.headers):
            self.add_note("status", UPGRADE_NOT_REQUESTED)

    def status102(self) -> None:  # Processing
        pass

    def status200(self) -> None:  # OK
        pass

    def status201(self) -> None:  # Created
        if self.request and self.request.method in safe_methods:
            self.add_note("status", CREATED_SAFE_METHOD, method=self.request.method)
        if "location" not in self.response.parsed_headers:
            self.add_note("header-location", CREATED_WITHOUT_LOCATION)

    def status202(self) -> None:  # Accepted
        pass

    def status203(self) -> None:  # Non-Authoritative Information
        pass

    def status204(self) -> None:  # No Content
        pass

    def status205(self) -> None:  # Reset Content
        pass

    def status206(self) -> None:  # Partial Content
        if self.request and "range" not in header_names(self.request.headers):
            self.add_note("", PARTIAL_NOT_REQUESTED)
        if "content-range" not in self.response.parsed_headers:
            self.add_note("header-location", PARTIAL_WITHOUT_RANGE)

    def status207(self) -> None:  # Multi-Status
        pass

    def status226(self) -> None:  # IM Used
        pass

    def status300(self) -> None:  # Multiple Choices
        pass

    def status301(self) -> None:  # Moved Permanently
        if "location" not in self.response.parsed_headers:
            self.add_note("header-location", REDIRECT_WITHOUT_LOCATION)

    def status302(self) -> None:  # Found
        if "location" not in self.response.parsed_headers:
            self.add_note("header-location", REDIRECT_WITHOUT_LOCATION)

    def status303(self) -> None:  # See Other
        if "location" not in self.response.parsed_headers:
            self.add_note("header-location", REDIRECT_WITHOUT_LOCATION)

    def status304(self) -> None:  # Not Modified
        if "date" not in self.response.parsed_headers:
            self.add_note("status", NO_DATE_304)

    def status305(self) -> None:  # Use Proxy
        self.add_note("", STATUS_DEPRECATED)

    def status306(self) -> None:  # Reserved
        self.add_note("", STATUS_RESERVED)

    def status307(self) -> None:  # Temporary Redirect
        if "location" not in self.response.parsed_headers:
            self.add_note("header-location", REDIRECT_WITHOUT_LOCATION)

    def status308(self) -> None:  # Permanent Redirect
        if "location" not in self.response.parsed_headers:
            self.add_note("header-location", REDIRECT_WITHOUT_LOCATION)

    def status400(self) -> None:  # Bad Request
        self.add_note("", STATUS_BAD_REQUEST)

    def status401(self) -> None:  # Unauthorized
        pass

    def status402(self) -> None:  # Payment Required
        pass

    def status403(self) -> None:  # Forbidden
        self.add_note("", STATUS_FORBIDDEN)

    def status404(self) -> None:  # Not Found
        self.add_note("", STATUS_NOT_FOUND)

    def status405(self) -> None:  # Method Not Allowed
        pass

    def status406(self) -> None:  # Not Acceptable
        self.add_note("", STATUS_NOT_ACCEPTABLE)

    def status407(self) -> None:  # Proxy Authentication Required
        pass

    def status408(self) -> None:  # Request Timeout
        pass

    def status409(self) -> None:  # Conflict
        self.add_note("", STATUS_CONFLICT)

    def status410(self) -> None:  # Gone
        self.add_note("", STATUS_GONE)

    def status411(self) -> None:  # Length Required
        pass

    def status412(self) -> None:  # Precondition Failed
        pass

    def status413(self) -> None:  # Request Entity Too Large
        self.add_note("", STATUS_REQUEST_ENTITY_TOO_LARGE)

    def status414(self) -> None:  # Request-URI Too Long
        if self.request:
            uri_len = f"({len(self.request.uri)} characters)"
        else:
            uri_len = ""
        self.add_note("uri", STATUS_URI_TOO_LONG, uri_len=uri_len)

    def status415(self) -> None:  # Unsupported Media Type
        self.add_note("", STATUS_UNSUPPORTED_MEDIA_TYPE)

    def status416(self) -> None:  # Requested Range Not Satisfiable
        pass

    def status417(self) -> None:  # Expectation Failed
        pass

    def status418(self) -> None:
        self.add_note("", STATUS_IM_A_TEAPOT)

    def status422(self) -> None:  # Unprocessable Entity
        pass

    def status423(self) -> None:  # Locked
        pass

    def status424(self) -> None:  # Failed Dependency
        pass

    def status426(self) -> None:  # Upgrade Required
        pass

    def status500(self) -> None:  # Internal Server Error
        self.add_note("", STATUS_INTERNAL_SERVICE_ERROR)

    def status501(self) -> None:  # Not Implemented
        self.add_note("", STATUS_NOT_IMPLEMENTED)

    def status502(self) -> None:  # Bad Gateway
        self.add_note("", STATUS_BAD_GATEWAY)

    def status503(self) -> None:  # Service Unavailable
        self.add_note("", STATUS_SERVICE_UNAVAILABLE)

    def status504(self) -> None:  # Gateway Timeout
        self.add_note("", STATUS_GATEWAY_TIMEOUT)

    def status505(self) -> None:  # HTTP Version Not Supported
        self.add_note("", STATUS_VERSION_NOT_SUPPORTED)

    def status506(self) -> None:  # Variant Also Negotiates
        pass

    def status507(self) -> None:  # Insufficient Storage
        pass

    def status510(self) -> None:  # Not Extended
        pass


class NO_DATE_304(Note):
    category = categories.VALIDATION
    level = levels.WARN
    summary = "304 responses need to have a Date header."
    text = """\
HTTP requires `304 Not Modified` responses to have a `Date` header in all but the most unusual
circumstances."""


class UNEXPECTED_CONTINUE(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = "A 100 Continue response was sent when it wasn't asked for."
    text = """\
HTTP allows clients to ask a server if a request with a body (e.g., uploading a large file) will
succeed before sending it, using a mechanism called "Expect/continue".

When used, the client sends an `Expect: 100-continue`, in the request headers, and if the server is
willing to process it, it will send a `100 Continue` status code to indicate that the request
should continue.

This response has a `100 Continue` status code, but REDbot did not ask for it (with the `Expect`
request header). Sending this status code without it being requested can cause interoperability
problems."""


class UPGRADE_NOT_REQUESTED(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = "The protocol was upgraded without being requested."
    text = """\
HTTP defines the `Upgrade` header as a means of negotiating a change of protocol; i.e., it allows
you to switch the protocol on a given connection from HTTP to something else.

However, it must be first requested by the client; this response contains an `Upgrade` header, even
though REDbot did not ask for it.

Trying to upgrade the connection without the client's participation obviously won't work."""


class CREATED_SAFE_METHOD(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = "A new resource was created in response to a safe request."
    text = """\
The `201 Created` status code indicates that processing the request had the side effect of creating
a new resource.

However, the request method that REDbot used (%(method)s) is defined as a "safe" method; that is, it
should not have any side effects.

Creating resources as a side effect of a safe method can have unintended consequences; for example,
search engine spiders and similar automated agents often follow links, and intermediaries sometimes
re-try safe methods when they fail."""


class CREATED_WITHOUT_LOCATION(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = "A new resource was created without its location being sent."
    text = """\
The `201 Created` status code indicates that processing the request had the side effect of creating
a new resource.

HTTP specifies that the URL of the new resource is to be indicated in the `Location` header, but it
isn't present in this response."""


class PARTIAL_WITHOUT_RANGE(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = "%(response)s doesn't have a Content-Range header."
    text = """\
The `206 Partial Response` status code indicates that the response body is only partial.

However, for a response to be partial, it needs to have a `Content-Range` header to indicate what
part of the full response it carries. This response does not have one, and as a result clients
won't be able to process it."""


class PARTIAL_NOT_REQUESTED(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = "A partial response was sent when it wasn't requested."
    text = """\
The `206 Partial Response` status code indicates that the response body is only partial.

However, the client needs to ask for it with the `Range` header.

REDbot did not request a partial response; sending one without the client requesting it leads to
interoperability problems."""


class REDIRECT_WITHOUT_LOCATION(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = "Redirects need to have a Location header."
    text = """\
The %(status)s status code redirects users to another URI. The `Location` header is used to convey
this URI, but a valid one isn't present in this response."""


class STATUS_DEPRECATED(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = "The %(status)s status code is deprecated."
    text = """\
When a status code is deprecated, it should not be used, because its meaning is not well-defined
enough to ensure interoperability."""


class STATUS_RESERVED(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = "The %(status)s status code is reserved."
    text = """\
Reserved status codes can only be used by future, standard protocol extensions; they are not for
private use."""


class STATUS_NONSTANDARD(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = "%(status)s is not a standard HTTP status code."
    text = """\
Non-standard status codes are not well-defined and interoperable. Instead of defining your own
status code, you should reuse one of the more generic ones; for example, 400 for a client-side
problem, or 500 for a server-side problem."""


class STATUS_BAD_REQUEST(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = "The server didn't understand the request."
    text = """\
 """


class STATUS_FORBIDDEN(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = "The server has forbidden this request."
    text = """\
 """


class STATUS_NOT_FOUND(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = "The resource could not be found."
    text = """\
The server couldn't find any resource to serve for the
     given URI."""


class STATUS_NOT_ACCEPTABLE(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = "The resource could not be found."
    text = """\
"""


class STATUS_CONFLICT(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = "The request conflicted with the state of the resource."
    text = """\
 """


class STATUS_GONE(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = "The resource is gone."
    text = """\
The server previously had a resource at the given URI, but it is no longer there."""


class STATUS_REQUEST_ENTITY_TOO_LARGE(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = "The request body was too large for the server."
    text = """\
The server rejected the request because the request body sent was too large."""


class STATUS_URI_TOO_LONG(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = "The server won't accept a URI this long %(uri_len)s."
    text = """\
The %(status)s status code means that the server can't or won't accept a request-uri this long."""


class STATUS_UNSUPPORTED_MEDIA_TYPE(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = "The resource doesn't support this media type in requests."
    text = """\
 """


class STATUS_IM_A_TEAPOT(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = "The server returned 418 I'm a Teapot, an easter egg defined in RFC 2324."
    text = """\
RFC 2324 was an April 1 RFC that lampooned the various ways HTTP was abused; one such abuse
was the definition of the application-specific 418 (I'm a Teapot) status code. In the
intervening years, this status code has been widely implemented as an "easter egg".

This status code is not a part of HTTP and hence it might not be supported by some strict
standards-compliant clients.
"""


class STATUS_INTERNAL_SERVICE_ERROR(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = "There was a general server error."
    text = """\
 """


class STATUS_NOT_IMPLEMENTED(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = "The server doesn't implement the request method."
    text = """\
 """


class STATUS_BAD_GATEWAY(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = "An intermediary encountered an error."
    text = """\
 """


class STATUS_SERVICE_UNAVAILABLE(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = "The server is temporarily unavailable."
    text = """\
 """


class STATUS_GATEWAY_TIMEOUT(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = "An intermediary timed out."
    text = """\
 """


class STATUS_VERSION_NOT_SUPPORTED(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = "The request HTTP version isn't supported."
    text = """\
 """
