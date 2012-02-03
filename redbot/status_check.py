#!/usr/bin/env python

"""
The Resource Expert Droid Response Analyser.

Provides two classes: ResponseHeaderParser and ResponseStatusChecker.

Both take a RedFetcher instance (post-done()) as their only argument.

ResponseHeaderParser will examine the response headers and set messages
on the RedFetcher instance as appropriate. It will also parse the
headers and populate parsed_hdrs.

ResponseStatusChecker will examine the response based upon its status
code and also set messages as appropriate.

ResponseHeaderParser MUST be called on the RedFetcher instance before
running ResponseStatusChecker, because it relies on the headers being
parsed.

See red.py for the main RED engine and webui.py for the Web front-end.
red_fetcher.py is the actual response fetching engine.
"""

__version__ = "1"
__author__ = "Mark Nottingham <mnot@mnot.net>"
__copyright__ = """\
Copyright (c) 2008-2011 Mark Nottingham

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

from cgi import escape as e

import thor.http

import redbot.speak as rs


class ResponseStatusChecker:
    """
    Given a RED, check out the status
    code and perform appropriate tests on it.
    """
    def __init__(self, red):
        self.red = red
        try:
            getattr(self, "status%s" % red.res_status)()
        except AttributeError:
            self.set_message('status', rs.STATUS_NONSTANDARD)

    def set_message(self, name, msg, **kw):
        if name:
            subject = 'status %s' % name
        else:
            subject = 'status'
        self.red.set_message(
            subject, 
            msg,
            status=self.red.res_status,
            enc_status=e(self.red.res_status),
            **kw
        )

    def status100(self):        # Continue
        if not "100-continue" in thor.http.get_header(self.red.req_hdrs, 'expect'):
            self.set_message('', rs.UNEXPECTED_CONTINUE)
    def status101(self):        # Switching Protocols
        if not 'upgrade' in thor.http.header_dict(self.red.req_hdrs).keys():
            self.set_message('', rs.UPGRADE_NOT_REQUESTED)
    def status102(self):        # Processing
        pass
    def status200(self):        # OK
        pass
    def status201(self):        # Created
        if self.red.method in thor.http.safe_methods:
            self.set_message('status', 
                rs.CREATED_SAFE_METHOD, 
                method=self.red.method
            )
        if not self.red.parsed_hdrs.has_key('location'):
            self.set_message('header-location', rs.CREATED_WITHOUT_LOCATION)
    def status202(self):        # Accepted
        pass
    def status203(self):        # Non-Authoritative Information
        pass
    def status204(self):        # No Content
        pass
    def status205(self):        # Reset Content
        pass
    def status206(self):        # Partial Content
        if not "range" in thor.http.header_dict(self.red.req_hdrs).keys():
            self.set_message('', rs.PARTIAL_NOT_REQUESTED)
        if not self.red.parsed_hdrs.has_key('content-range'):
            self.set_message('header-location', rs.PARTIAL_WITHOUT_RANGE)
    def status207(self):        # Multi-Status
        pass
    def status226(self):        # IM Used
        pass
    def status300(self):        # Multiple Choices
        pass
    def status301(self):        # Moved Permanently
        if not self.red.parsed_hdrs.has_key('location'):
            self.set_message('header-location', rs.REDIRECT_WITHOUT_LOCATION)
    def status302(self):        # Found
        if not self.red.parsed_hdrs.has_key('location'):
            self.set_message('header-location', rs.REDIRECT_WITHOUT_LOCATION)
    def status303(self):        # See Other
        if not self.red.parsed_hdrs.has_key('location'):
            self.set_message('header-location', rs.REDIRECT_WITHOUT_LOCATION)
    def status304(self):        # Not Modified
        if not self.red.parsed_hdrs.has_key('date'):
            self.set_message('status', rs.NO_DATE_304)
    def status305(self):        # Use Proxy
        self.set_message('', rs.STATUS_DEPRECATED)
    def status306(self):        # Reserved
        self.set_message('', rs.STATUS_RESERVED)
    def status307(self):        # Temporary Redirect
        if not self.red.parsed_hdrs.has_key('location'):
            self.set_message('header-location', rs.REDIRECT_WITHOUT_LOCATION)
    def status400(self):        # Bad Request
        self.set_message('', rs.STATUS_BAD_REQUEST)
    def status401(self):        # Unauthorized
        pass # TODO: prompt for credentials
    def status402(self):        # Payment Required
        pass
    def status403(self):        # Forbidden
        self.set_message('', rs.STATUS_FORBIDDEN)
    def status404(self):        # Not Found
        self.set_message('', rs.STATUS_NOT_FOUND)
    def status405(self):        # Method Not Allowed
        pass # TODO: show allowed methods?
    def status406(self):        # Not Acceptable
        self.set_message('', rs.STATUS_NOT_ACCEPTABLE)
    def status407(self):        # Proxy Authentication Required
        pass
    def status408(self):        # Request Timeout
        pass
    def status409(self):        # Conflict
        self.set_message('', rs.STATUS_CONFLICT)
    def status410(self):        # Gone
        self.set_message('', rs.STATUS_GONE)
    def status411(self):        # Length Required
        pass
    def status412(self):        # Precondition Failed
        pass # TODO: test to see if it's true, alert if not
    def status413(self):        # Request Entity Too Large
        self.set_message('', rs.STATUS_REQUEST_ENTITY_TOO_LARGE)
    def status414(self):        # Request-URI Too Long
        self.set_message('uri', rs.STATUS_URI_TOO_LONG,
                        uri_len=len(self.red.uri))
    def status415(self):        # Unsupported Media Type
        self.set_message('', rs.STATUS_UNSUPPORTED_MEDIA_TYPE)
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
        self.set_message('', rs.STATUS_INTERNAL_SERVICE_ERROR)
    def status501(self):        # Not Implemented
        self.set_message('', rs.STATUS_NOT_IMPLEMENTED)
    def status502(self):        # Bad Gateway
        self.set_message('', rs.STATUS_BAD_GATEWAY)
    def status503(self):        # Service Unavailable
        self.set_message('', rs.STATUS_SERVICE_UNAVAILABLE)
    def status504(self):        # Gateway Timeout
        self.set_message('', rs.STATUS_GATEWAY_TIMEOUT)
    def status505(self):        # HTTP Version Not Supported
        self.set_message('', rs.STATUS_VERSION_NOT_SUPPORTED)
    def status506(self):        # Variant Also Negotiates
        pass
    def status507(self):        # Insufficient Storage
        pass
    def status510(self):        # Not Extended
        pass
