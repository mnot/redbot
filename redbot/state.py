#!/usr/bin/env python

"""
The Resource Expert Droid State container.

RedState holds all test-related state that's useful for analysis; ephemeral
objects (e.g., the HTTP client machinery) are kept elsewhere.
"""

__author__ = "Mark Nottingham <mnot@mnot.net>"
__copyright__ = """\
Copyright (c) 2008-2013 Mark Nottingham

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

import urllib
import urlparse

import thor.http.error as httperr
import redbot.speak as rs
from redbot.message import HttpRequest, HttpResponse


class RedState(object):
    """
    Holder for test state.
    """
    
    def __init__(self, iri, method, req_hdrs, req_body, check_type):
        self.check_type = check_type
        self.notes = []
        self.subreqs = {} # sub-requests' RedState objects
        self.request = HttpRequest(self.notes, check_type)
        self.response = HttpResponse(self.notes, check_type)
        self.request.method = method
        self.request.headers = req_hdrs or []
        self.request.payload = req_body
        
        # FIXME: put in HttpRequest
        try:
            self.uri = self.iri_to_uri(iri)
        except (ValueError, UnicodeError), why:
            self.response.http_error = httperr.UrlError(why[0])
            self.uri = None

    def __repr__(self):
        status = [self.__class__.__module__ + "." + self.__class__.__name__]
        status.append("%s {%s}" % (self.request.method, self.uri))
        status.append("type %s" % self.check_type)
        return "<%s at %#x>" % (", ".join(status), id(self))

    def __getstate__(self):
        state = self.__dict__.copy()
        if state.has_key('add_note'):
            del state['add_note']
        return state
        
    def add_note(self, subject, note, subreq=None, **kw):
        "Set a note."
        kw['response'] = rs.response.get(
            self.check_type, rs.response['this']
        )['en']
        self.notes.append(note(subject, subreq, kw))
        
    # TODO: move to message.HttpRequest
    @staticmethod
    def iri_to_uri(iri):
        "Takes a Unicode string that can contain an IRI and emits a URI."
        scheme, authority, path, query, frag = urlparse.urlsplit(iri)
        scheme = scheme.encode('utf-8')
        if ":" in authority:
            host, port = authority.split(":", 1)
            authority = host.encode('idna') + ":%s" % port
        else:
            authority = authority.encode('idna')
        path = urllib.quote(
          path.encode('utf-8'), 
          safe="/;%[]=:$&()+,!?*@'~"
        )
        query = urllib.quote(
          query.encode('utf-8'), 
          safe="/;%[]=:$&()+,!?*@'~"
        )
        frag = urllib.quote(
          frag.encode('utf-8'), 
          safe="/;%[]=:$&()+,!?*@'~"
        )
        return urlparse.urlunsplit((scheme, authority, path, query, frag))
    