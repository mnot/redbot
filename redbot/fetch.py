#!/usr/bin/env python

"""
The Resource Expert Droid Fetcher.

RedFetcher fetches a single URI and analyses that response for common
problems and other interesting characteristics. It only makes one request,
based upon the provided headers.
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

import base64
import urllib
import urlparse

import thor
import thor.http.error as httperr

from redbot import __version__
from redbot.formatter import f_num
import redbot.speak as rs
from redbot.state import RedState
from redbot.message.status import StatusChecker
from redbot.message.cache import checkCaching

class RedHttpClient(thor.http.HttpClient):
    "Thor HttpClient for RedFetcher"
    connect_timeout = 10
    read_timeout = 15
    

class RedFetcher(RedState):
    """
    Fetches the given URI (with the provided method, headers and body) and
    calls:
      - status_cb as it progresses, and
      - every function in the body_procs list with each chunk of the body, and
      - done_cb when all tasks are done.
    If provided, type indicates the type of the request, and is used to
    help set notes and status_cb appropriately.
    
    The done() method is called when the response is done, NOT when all 
    tasks are done. It can add tasks by calling add_task().

    """
    client = RedHttpClient()

    def __init__(self, iri, method="GET", req_hdrs=None, req_body=None,
                 status_cb=None, body_procs=None, check_type=None):
        RedState.__init__(self, check_type)
        self.check_type = check_type
        self.request.method = method
        self.request.headers = req_hdrs or []
        self.request.payload = req_body
        self.exchange = None
        self.status_cb = status_cb
        self.body_procs = body_procs or []
        self.done_cb = None
        self.outstanding_tasks = 0
        self._st = [] # TEMPORARY
        try:
            self.uri = self.iri_to_uri(iri)
        except (ValueError, UnicodeError), why:
            self.response.http_error = httperr.UrlError(why[0])
            self.uri = None

    def __repr__(self):
        status = [self.__class__.__module__ + "." + self.__class__.__name__]
        if hasattr(self, 'state'):
            status.append("%s {%s}" % (
                self.request.method or "???", self.uri or "???"
            ))
            status.append("%s tasks" % self.outstanding_tasks or "?")
        return "<%s at %#x>" % (", ".join(status), id(self))

    def __getstate__(self):
        state = self.__dict__.copy()
        del state['status_cb']
        del state['body_procs']
        del state['exchange']
        return state

    def add_task(self, task, *args):
        "Remeber that we've started a task."
        self.outstanding_tasks += 1
        self._st.append('add_task(%s)' % str(task))
        task(*args, done_cb=self.finish_task)
        
    def finish_task(self):
        "Note that we've finished a task, and see if we're done."
        self.outstanding_tasks -= 1
        self._st.append('finish_task()')
        assert self.outstanding_tasks >= 0, self._st
        if self.outstanding_tasks == 0:
            if self.done_cb:
                self.done_cb()
                self.done_cb = None
            # clean up potentially cyclic references
            self.status_cb = None
            self.body_procs = None

    def done(self):
        "Callback for when the response is complete and analysed."
        raise NotImplementedError

    def preflight(self):
        """
        Callback to check to see if we should bother running. Return True 
        if so; False if not. 
        """
        return True

    def run(self, done_cb=None):
        """
        Make an asynchronous HTTP request to uri, calling status_cb as it's
        updated and done_cb when it's done. Reason is used to explain what the
        request is in the status callback.
        """
        self.outstanding_tasks += 1
        self._st.append('run(%s)' % str(done_cb))
        self.done_cb = done_cb
        if not self.preflight() or self.uri == None:
            # generally a good sign that we're not going much further.
            self.finish_task()
            return
        if 'user-agent' not in [i[0].lower() for i in self.request.headers]:
            self.request.headers.append(
                (u"User-Agent", u"RED/%s (http://redbot.org/)" % __version__))    
        self.exchange = self.client.exchange()
        self.exchange.on('response_start', self._response_start)
        self.exchange.on('response_body', self._response_body)
        self.exchange.on('response_done', self._response_done)
        self.exchange.on('error', self._response_error)
        if self.status_cb and self.check_type:
            self.status_cb("fetching %s (%s)" % (self.uri, self.check_type))
        req_hdrs = [
            (k.encode('ascii', 'replace'), v.encode('latin-1', 'replace')) \
            for (k, v) in self.request.headers
        ]
        self.exchange.request_start(self.request.method, self.uri, req_hdrs)
        self.request.start_time = thor.time()
        if self.request.payload != None:
            self.exchange.request_body(self.request.payload)
        self.exchange.request_done([])

    def _response_start(self, status, phrase, res_headers):
        "Process the response start-line and headers."
        self._st.append('_response_start(%s, %s)' % (status, phrase))
        res = self.response
        res.start_time = thor.time()
        res.version = self.exchange.res_version
        res.status_code = status.decode('iso-8859-1', 'replace')
        res.status_phrase = phrase.decode('iso-8859-1', 'replace')
        res.set_headers(res_headers)
        StatusChecker(self.response, self.request)
        checkCaching(self.response, self.request)

    def _response_body(self, chunk):
        "Process a chunk of the response body."
        self.response.feed_body(chunk, self.body_procs)

    def _response_done(self, trailers):
        "Finish analysing the response, handling any parse errors."
        self._st.append('_response_done()')
        res = self.response
        res.complete_time = thor.time()
        res.transfer_length = self.exchange.input_transfer_length
        res.header_length = self.exchange.input_header_length
        res.body_done(True, trailers)
        if self.status_cb and self.check_type:
            self.status_cb("fetched %s (%s)" % (self.uri, self.check_type))
        self.done()
        self.finish_task()

    def _response_error(self, error):
        "Handle an error encountered while fetching the response."
        self._st.append('_response_error(%s)' % (str(error)))
        res = self.response
        res.complete_time = thor.time()
        res.http_error = error
        if isinstance(error, httperr.BodyForbiddenError):
            self.add_note('header-none', rs.BODY_NOT_ALLOWED)
#        elif isinstance(error, httperr.ExtraDataErr):
#            res.payload_len += len(err.get('detail', ''))
        elif isinstance(error, httperr.ChunkError):
            err_msg = error.detail[:20] or ""
            self.add_note('header-transfer-encoding', rs.BAD_CHUNK,
                chunk_sample=err_msg.encode('string_escape')
            )
        self.done()
        self.finish_task()

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


if "__main__" == __name__:
    import sys
    def status_p(msg):
        "Print status"
        print msg
    class TestFetcher(RedFetcher):
        "Test a fetcher."
        def done(self):
            print self.notes
    T = TestFetcher(
         sys.argv[1], 
         req_hdrs=[(u'Accept-Encoding', u'gzip')], 
         status_cb=status_p, 
         check_type='test'
    )
    T.run()
    thor.run()
