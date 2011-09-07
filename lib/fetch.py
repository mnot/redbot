#!/usr/bin/env python

"""
The Resource Expert Droid Fetcher.

RedFetcher fetches a single URI and analyses that response for common
problems and other interesting characteristics. It only makes one request,
based upon the provided headers.

See droid.py for the main RED engine and webui.py for the Web front-end.
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

import base64
import hashlib
import zlib
from cgi import escape as e

import thor
import thor.http.error as httperr

from redbot.cache_check import checkCaching
import redbot.speak as rs
import redbot.response_analyse as ra
from redbot.response_analyse import f_num
from redbot.state import RedState

class RedHttpClient(thor.HttpClient):
    connect_timeout = 8
    read_timeout = 8
    

class RedFetcher(object):
    """
    Fetches the given URI (with the provided method, headers and body) and
    calls:
      - status_cb as it progresses, and
      - every function in the body_procs list with each chunk of the body, and
      - done_cb when all tasks are done.
    If provided, type indicates the type of the request, and is used to
    help set messages and status_cb appropriately.
    
    The done() method is called when the response is done, NOT when all 
    tasks are done. It can add tasks by calling add_task().

    """
    client = RedHttpClient()

    def __init__(self, iri, method="GET", req_hdrs=None, req_body=None,
                 status_cb=None, body_procs=None, req_type=None):
        self.state = RedState(iri, method, req_hdrs, req_body, req_type)
        self.status_cb = status_cb
        self.body_procs = body_procs or []
        self.done_cb = None
        self.outstanding_tasks = 0
        self._md5_processor = hashlib.md5()
        self._gzip_processor = zlib.decompressobj(-zlib.MAX_WBITS)
        self._md5_post_processor = hashlib.md5()
        self._in_gzip_body = False
        self._gzip_header_buffer = ""
        self._gzip_ok = True # turn False if we have a problem

    def __getstate__(self):
        state = self.__dict__.copy()
        del state['status_cb']
        del state['body_procs']
        del state['_md5_processor']
        del state['_gzip_processor']
        del state['exchange']
        del state['_md5_post_processor']
        return state

    def add_task(self, task, *args):
        self.outstanding_tasks += 1
        task(*args, done_cb=self.finish_task)
        
    def finish_task(self):
        self.outstanding_tasks -= 1
        assert self.outstanding_tasks >= 0
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
        self.done_cb = done_cb
        state = self.state
        if not self.preflight() or state.uri == None:
            # generally a good sign that we're not going much further.
            self.finish_task()
            return
        if 'user-agent' not in [i[0].lower() for i in state.req_hdrs]:
            state.req_hdrs.append(
                ("User-Agent", "RED/%s (http://redbot.org/)" % __version__))    
        self.exchange = self.client.exchange()
        self.exchange.on('response_start', self._response_start)
        self.exchange.on('response_body', self._response_body)
        self.exchange.on('response_done', self._response_done)
        self.exchange.on('error', self._response_error)
        if self.status_cb and state.type:
            self.status_cb("fetching %s (%s)" % (state.uri, state.type))
        self.exchange.request_start(state.method, state.uri, state.req_hdrs)
        state.req_ts = thor.time()
        if state.req_body != None:
            self.exchange.request_body(state.req_body)
        self.exchange.request_done([])

    def _response_start(self, status, phrase, res_headers):
        "Process the response start-line and headers."
        state = self.state
        state.res_ts = thor.time()
        state.res_version = self.exchange.res_version
        state.res_status = status.decode('iso-8859-1', 'replace')
        state.res_phrase = phrase.decode('iso-8859-1', 'replace')
        state.res_hdrs = res_headers
        ra.ResponseHeaderParser(state)
        ra.ResponseStatusChecker(state)
        state.res_body_enc = state.parsed_hdrs.get(
            'content-type', [None, {}]
        )[1].get('charset', 'utf-8') # default isn't really UTF-8, but oh well

    def _response_body(self, chunk):
        "Process a chunk of the response body."
        state = self.state
        state.res_body_sample.append((state.res_body_len, chunk))
        if len(state.res_body_sample) > 4:
            state.res_body_sample.pop(0)
        self._md5_processor.update(chunk)
        state.res_body_len += len(chunk)
        if state.res_status == "206":
            # Store only partial responses completely, for error reporting
            state.res_body += chunk
            state.res_body_decode_len += len(chunk)
            # Don't actually try to make sense of a partial body...
            return
        content_codings = state.parsed_hdrs.get('content-encoding', [])
        content_codings.reverse()
        for coding in content_codings:
            # TODO: deflate support
            if coding == 'gzip' and self._gzip_ok:
                if not self._in_gzip_body:
                    self._gzip_header_buffer += chunk
                    try:
                        chunk = self._read_gzip_header(
                            self._gzip_header_buffer
                        )
                        self._in_gzip_body = True
                    except IndexError:
                        return # not a full header yet
                    except IOError, gzip_error:
                        state.setMessage('header-content-encoding',
                                        rs.BAD_GZIP,
                                        gzip_error=e(str(gzip_error))
                        )
                        self._gzip_ok = False
                        return
                try:
                    chunk = self._gzip_processor.decompress(chunk)
                except zlib.error, zlib_error:
                    state.setMessage(
                        'header-content-encoding', 
                        rs.BAD_ZLIB,
                        zlib_error=e(str(zlib_error)),
                        ok_zlib_len=f_num(state.res_body_sample[-1][0]),
                        chunk_sample=e(chunk[:20].encode('string_escape'))
                    )
                    self._gzip_ok = False
                    return
            else:
                # we can't handle other codecs, so punt on body processing.
                return
        self._md5_post_processor.update(chunk)
        state.res_body_decode_len += len(chunk)
        if self._gzip_ok:
            for processor in self.body_procs:
                # TODO: figure out why raising an error in a body_proc
                # results in a "server dropped the connection" instead of
                # a hard error.
                processor(self.state, chunk)

    def _response_done(self, trailers):
        "Finish anaylsing the response, handling any parse errors."
        state = self.state
        state.res_complete = True
        state.res_done_ts = thor.time()
        state.transfer_length = self.exchange.input_transfer_length
        state.header_length = self.exchange.input_header_length
        # TODO: check trailers
        if self.status_cb and state.type:
            self.status_cb("fetched %s (%s)" % (state.uri, state.type))
        state.res_body_md5 = self._md5_processor.digest()
        state.res_body_post_md5 = self._md5_post_processor.digest()
        checkCaching(state)

        if state.method not in ['HEAD'] and state.res_status not in ['304']:
            # check payload basics
            if state.parsed_hdrs.has_key('content-length'):
                if state.res_body_len == state.parsed_hdrs['content-length']:
                    state.setMessage('header-content-length', rs.CL_CORRECT)
                else:
                    state.setMessage('header-content-length', 
                                    rs.CL_INCORRECT,
                                    body_length=f_num(state.res_body_len)
                    )
            if state.parsed_hdrs.has_key('content-md5'):
                c_md5_calc = base64.encodestring(state.res_body_md5)[:-1]
                if state.parsed_hdrs['content-md5'] == c_md5_calc:
                    state.setMessage('header-content-md5', rs.CMD5_CORRECT)
                else:
                    state.setMessage('header-content-md5', rs.CMD5_INCORRECT,
                                     calc_md5=c_md5_calc)
        self.done()
        self.finish_task()

    def _response_error(self, error):
        state = self.state
        state.res_done_ts = thor.time()
        state.res_error = error
        if isinstance(error, httperr.BodyForbiddenError):
            state.setMessage('header-none', rs.BODY_NOT_ALLOWED)
#        elif isinstance(error, httperr.ExtraDataErr):
#            state.res_body_len += len(err.get('detail', ''))
        elif isinstance(error, httperr.ChunkError):
            state.setMessage('header-transfer-encoding', rs.BAD_CHUNK,
                chunk_sample=e(
                    error.get('detail', '')[:20].encode('string_escape')
                )
            )
        self.done()
        self.finish_task()

    @staticmethod
    def _read_gzip_header(content):
        """
        Parse a string for a GZIP header; if present, return remainder of
        gzipped content.
        """
        # adapted from gzip.py
        FTEXT, FHCRC, FEXTRA, FNAME, FCOMMENT = 1, 2, 4, 8, 16
        if len(content) < 10:
            raise IndexError, "Header not complete yet"
        magic = content[:2]
        if magic != '\037\213':
            raise IOError, \
                u'Not a gzip header (magic is hex %s, should be 1f8b)' % \
                magic.encode('hex-codec')
        method = ord( content[2:3] )
        if method != 8:
            raise IOError, 'Unknown compression method'
        flag = ord( content[3:4] )
        content_l = list(content[10:])
        if flag & FEXTRA:
            # Read & discard the extra field, if present
            xlen = ord(content_l.pop())
            xlen = xlen + 256*ord(content_l.pop())
            content_l = content_l[xlen:]
        if flag & FNAME:
            # Read and discard a null-terminated string 
            # containing the filename
            while True:
                s = content_l.pop()
                if not content_l or s == '\000':
                    break
        if flag & FCOMMENT:
            # Read and discard a null-terminated string containing a comment
            while True:
                s = content_l.pop()
                if not content_l or s == '\000':
                    break
        if flag & FHCRC:
            content_l = content_l[2:]   # Read & discard the 16-bit header CRC
        return "".join(content_l)



if "__main__" == __name__:
    import sys
    uri = sys.argv[1]
    test_req_hdrs = [('Accept-Encoding', 'gzip')]
    def status_p(msg):
        print msg
    class TestFetcher(RedFetcher):
        def done(self):
            print self.state.messages
    tf = TestFetcher(
        uri, req_hdrs=test_req_hdrs, status_cb=status_p, req_type='test'
    )
    tf.run()
    thor.run()
