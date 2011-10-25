#!/usr/bin/env python

"""
The Resource Expert Droid State container.

RedState holds all test-related state that's useful for analysis; ephemeral
objects (e.g., the HTTP client machinery) are kept elsewhere.
"""

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

import urllib
import urlparse

import thor.http.error as httperr
import redbot.speak as rs


class RedState(object):
    """
    Holder for test state.

    Messages is a list of messages, each of which being a tuple that
    follows the following form:
      (
       subject,     # The subject(s) of the msg, as a space-separated string.
                    # e.g., "header-cache-control header-expires"
       message,     # The message structure; see red_speak.py
       subrequest,  # Optionally, the req_type of a RedState object
                    # (stored in .subreqs) representing a
                    # subrequest made in order to generate the message
       **variables  # Optionally, key=value pairs intended for interpolation
                    # into the message; e.g., time_left="5d3h"
      )
    """
    
    def __init__(self, iri, method, req_hdrs, req_body, req_type):
        self.method = method
        self.req_hdrs = req_hdrs or []
        self.req_body = req_body
        self.type = req_type
        self.req_ts = None # when the request was started
        self.res_ts = None # when the response was started
        self.res_done_ts = None # when the response was finished
        # response attributes; populated by RedFetcher
        self.res_version = ""
        self.res_status = None
        self.res_phrase = ""
        self.res_hdrs = []
        self.parsed_hdrs = {}
        self.res_body = "" # note: only partial responses; bytes, not unicode
        self.res_body_len = 0
        self.res_body_md5 = None
        self.res_body_sample = [] # [(offset, chunk)]{,4} Bytes, not unicode
        self.res_body_enc = None
        self.res_body_decode_len = 0
        self.res_complete = False
        self.transfer_length = None
        self.header_length = None
        self.res_error = None # any parse errors encountered; see httperr
        # interesting things about the response; set by a variety of things
        self.messages = [] # messages (see above)
        self.subreqs = {} # sub-requests' RedState objects
        try:
            self.uri = self.iri_to_uri(iri)
        except (ValueError, UnicodeError), why:
            self.res_error = httperr.UrlError(why)
            self.uri = None

    def __repr__(self):
        status = [self.__class__.__module__ + "." + self.__class__.__name__]
        status.append("%s {%s}" % (self.method, self.uri))
        status.append("type %s" % self.type)
        return "<%s at %#x>" % (", ".join(status), id(self))

    def __getstate__(self):
        state = self.__dict__.copy()
        if state.has_key('set_message'):
            del state['set_message']
        return state
        
    def set_message(self, subject, msg, subreq=None, **kw):
        "Set a message."
        kw['response'] = rs.response.get(
            self.type, rs.response['this']
        )['en']
        self.messages.append(msg(subject, subreq, kw))
        
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
