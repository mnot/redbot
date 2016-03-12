#!/usr/bin/env python

"""
The Resource Expert Droid Status Code Checker.
"""


from thor.http import header_dict, get_header, safe_methods
import redbot.speak as rs


class StatusChecker:
    """
    Given a response, check out the status code and perform 
    appropriate tests on it.
    
    Additional tests will be performed if the request is available.
    """
    def __init__(self, response, request=None):
        assert response.is_request is False
        self.request = request
        self.response = response
        try:
            status_m = getattr(self, "status%s" % response.status_code.encode('ascii', 'ignore'))
        except AttributeError:
            self.add_note('status', rs.STATUS_NONSTANDARD)
            return
        status_m()

    def add_note(self, name, note, **kw):
        if name:
            subject = 'status %s' % name
        else:
            subject = 'status'
        self.response.add_note(
            subject, 
            note,
            status=self.response.status_code,
            **kw
        )

    def status100(self):        # Continue
        if self.request and not "100-continue" in get_header(
            self.request.headers, 'expect'):
            self.add_note('', rs.UNEXPECTED_CONTINUE)
    def status101(self):        # Switching Protocols
        if self.request \
        and not 'upgrade' in header_dict(self.request.headers).keys():
            self.add_note('', rs.UPGRADE_NOT_REQUESTED)
    def status102(self):        # Processing
        pass
    def status200(self):        # OK
        pass
    def status201(self):        # Created
        if self.request and self.request.method in safe_methods:
            self.add_note('status', 
                rs.CREATED_SAFE_METHOD, 
                method=self.request.method
            )
        if not self.response.parsed_headers.has_key('location'):
            self.add_note('header-location', rs.CREATED_WITHOUT_LOCATION)
    def status202(self):        # Accepted
        pass
    def status203(self):        # Non-Authoritative Information
        pass
    def status204(self):        # No Content
        pass
    def status205(self):        # Reset Content
        pass
    def status206(self):        # Partial Content
        if self.request \
        and not "range" in header_dict(self.request.headers).keys():
            self.add_note('', rs.PARTIAL_NOT_REQUESTED)
        if not self.response.parsed_headers.has_key('content-range'):
            self.add_note('header-location', rs.PARTIAL_WITHOUT_RANGE)
    def status207(self):        # Multi-Status
        pass
    def status226(self):        # IM Used
        pass
    def status300(self):        # Multiple Choices
        pass
    def status301(self):        # Moved Permanently
        if not self.response.parsed_headers.has_key('location'):
            self.add_note('header-location', rs.REDIRECT_WITHOUT_LOCATION)
    def status302(self):        # Found
        if not self.response.parsed_headers.has_key('location'):
            self.add_note('header-location', rs.REDIRECT_WITHOUT_LOCATION)
    def status303(self):        # See Other
        if not self.response.parsed_headers.has_key('location'):
            self.add_note('header-location', rs.REDIRECT_WITHOUT_LOCATION)
    def status304(self):        # Not Modified
        if not self.response.parsed_headers.has_key('date'):
            self.add_note('status', rs.NO_DATE_304)
    def status305(self):        # Use Proxy
        self.add_note('', rs.STATUS_DEPRECATED)
    def status306(self):        # Reserved
        self.add_note('', rs.STATUS_RESERVED)
    def status307(self):        # Temporary Redirect
        if not self.response.parsed_headers.has_key('location'):
            self.add_note('header-location', rs.REDIRECT_WITHOUT_LOCATION)
    def status308(self):        # Permanent Redirect
        if not self.response.parsed_headers.has_key('location'):
            self.add_note('header-location', rs.REDIRECT_WITHOUT_LOCATION)
    def status400(self):        # Bad Request
        self.add_note('', rs.STATUS_BAD_REQUEST)
    def status401(self):        # Unauthorized
        pass
    def status402(self):        # Payment Required
        pass
    def status403(self):        # Forbidden
        self.add_note('', rs.STATUS_FORBIDDEN)
    def status404(self):        # Not Found
        self.add_note('', rs.STATUS_NOT_FOUND)
    def status405(self):        # Method Not Allowed
        pass # TODO: show allowed methods?
    def status406(self):        # Not Acceptable
        self.add_note('', rs.STATUS_NOT_ACCEPTABLE)
    def status407(self):        # Proxy Authentication Required
        pass
    def status408(self):        # Request Timeout
        pass
    def status409(self):        # Conflict
        self.add_note('', rs.STATUS_CONFLICT)
    def status410(self):        # Gone
        self.add_note('', rs.STATUS_GONE)
    def status411(self):        # Length Required
        pass
    def status412(self):        # Precondition Failed
        pass # TODO: test to see if it's true, alert if not
    def status413(self):        # Request Entity Too Large
        self.add_note('', rs.STATUS_REQUEST_ENTITY_TOO_LARGE)
    def status414(self):        # Request-URI Too Long
        if self.request:
            uri_len = "(%s characters)" % len(self.request.uri)
        else:
            uri_len = ""
        self.add_note('uri', rs.STATUS_URI_TOO_LONG, uri_len=uri_len)
    def status415(self):        # Unsupported Media Type
        self.add_note('', rs.STATUS_UNSUPPORTED_MEDIA_TYPE)
    def status416(self):        # Requested Range Not Satisfiable
        pass # TODO: test to see if it's true, alter if not
    def status417(self):        # Expectation Failed
        pass # TODO: explain, alert if it's 100-continue
    def status422(self):        # Unprocessable Entity
        pass
    def status423(self):        # Locked
        pass
    def status424(self):        # Failed Dependency
        pass
    def status426(self):        # Upgrade Required
        pass
    def status500(self):        # Internal Server Error
        self.add_note('', rs.STATUS_INTERNAL_SERVICE_ERROR)
    def status501(self):        # Not Implemented
        self.add_note('', rs.STATUS_NOT_IMPLEMENTED)
    def status502(self):        # Bad Gateway
        self.add_note('', rs.STATUS_BAD_GATEWAY)
    def status503(self):        # Service Unavailable
        self.add_note('', rs.STATUS_SERVICE_UNAVAILABLE)
    def status504(self):        # Gateway Timeout
        self.add_note('', rs.STATUS_GATEWAY_TIMEOUT)
    def status505(self):        # HTTP Version Not Supported
        self.add_note('', rs.STATUS_VERSION_NOT_SUPPORTED)
    def status506(self):        # Variant Also Negotiates
        pass
    def status507(self):        # Insufficient Storage
        pass
    def status510(self):        # Not Extended
        pass
