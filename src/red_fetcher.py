#!/usr/bin/env python

"""
The Resource Expert Droid Fetcher.

RedFetcher fetches a single URI and analyses that response for common
problems and other interesting characteristics. It only makes one request,
based upon the provided headers.

See red.py for the main RED engine and webui.py for the Web front-end.
"""

__version__ = "1"
__author__ = "Mark Nottingham <mnot@mnot.net>"
__copyright__ = """\
Copyright (c) 2008-2009 Mark Nottingham

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
import socket
import time
import zlib
from cgi import escape as e

import nbhttp
import red_speak as rs 
import response_analyse as ra

outstanding_requests = 0 # how many requests we have left

class RedFetcher: 
    """
    Fetches the given URI (with the provided method, headers and body) and calls:
      - status_cb as it progresses, and
      - every function in the body_procs list with each chunk of the body, and
      - done when it's done.
    If provided, type indicates the type of the request, and is used to
    help set messages and status_cb appropriately. 
    
    Messages is a list of messages, each of which being a tuple that 
    follows the following form:
      (
       subject,     # The subject(s) of the msg, as a space-separated string.
                    # e.g., "header-cache-control header-expires"
       message,     # The message structure; see red.speak.py
       subrequest,  # Optionally, a RedFetcher object representing a
                    # request with additional details about another request
                    # made in order to generate the message
       **variables  # Optionally, key=value pairs intended for interpolation
                    # into the message; e.g., time_left="5d3h"
      )
    """

    def __init__(self, uri, method="GET", req_hdrs=None, req_body=None,
                 status_cb=None, body_procs=None, req_type=None):
        self.uri = uri
        self.method = method
        self.req_hdrs = req_hdrs or []
        self.req_body = req_body
        self.status_cb = status_cb
        self.body_procs = body_procs or []
        self.type = req_type
        self.res_version = ""
        self.res_status = None
        self.res_phrase = ""
        self.res_hdrs = []
        self.parsed_hdrs = {}
        self.res_body = "" # note: only partial responses get this populated; bytes, not unicode
        self.res_body_len = 0
        self.res_body_md5 = None
        self.res_body_sample = [] # array of (offset, chunk), max size 4. Bytes, not unicode.
        self.res_complete = False
        self.timestamp = None # when the request was started
        self.res_error = None # any parse errors encountered; see nbhttp.error
        self.messages = []
        self._md5_processor = hashlib.md5()
        self._decompress = zlib.decompressobj(-zlib.MAX_WBITS).decompress
        self._in_gzip_body = False
        self._gzip_header_buffer = ""
        self._gzip_ok = True # turn False if we have a problem
        try:
            self._makeRequest()
        except socket.gaierror:
            self._response_done(nbhttp.error.ERR_CONNECT)
        
    def setMessage(self, subject, msg, subreq=None, **vrs):
        "Set a message."
        vrs['response'] = rs.response.get(self.type, rs.response['this'])['en']
        self.messages.append((subject, msg, subreq, vrs))

    def done(self):
        "Callback for when the response is complete and analysed."
        raise NotImplementedError

    def _makeRequest(self):
        """
        Make an asynchronous HTTP request to uri, calling status_cb as it's updated and
        done_cb when it's done. Reason is used to explain what the request is in the
        status callback.
        """
        global outstanding_requests
        outstanding_requests += 1
        c = nbhttp.Client(self._response_start)
        if self.status_cb and self.type:
            self.status_cb("fetching %s (%s)" % (self.uri, self.type))
        req_body, req_done = c.req_start(self.method, self.uri, self.req_hdrs, nbhttp.dummy)
        if outstanding_requests == 1:
            nbhttp.run()
        if self.req_body != None:
            req_body(self.req_body)
        req_done(None)

    def _response_start(self, version, status, phrase, res_headers, res_pause):
        "Process the response start-line and headers."
        self.timestamp = time.time()
        self.res_version = version
        self.res_status = status.decode('iso-8859-1', 'replace')
        self.res_phrase = phrase.decode('iso-8859-1', 'replace')
        self.res_hdrs = res_headers
        ra.ResponseHeaderParser(self)
        ra.ResponseStatusChecker(self)
        return self._response_body, self._response_done

    def _response_body(self, chunk):
        "Process a chunk of the response body."
        self._md5_processor.update(chunk)
        self.res_body_sample.append((self.res_body_len, chunk))
        if len(self.res_body_sample) > 4:
            self.res_body_sample.pop(0)
        self.res_body_len += len(chunk)
        if self.res_status == "206":
            # Store only partial responses completely, for error reporting
            self.res_body += chunk
            # Don't actually try to make sense of a partial body...
            return
        content_codings = self.parsed_hdrs.get('content-encoding', [])
        content_codings.reverse()
        for coding in content_codings:
            # TODO: deflate support
            if coding == 'gzip' and self._gzip_ok:
                if not self._in_gzip_body:
                    self._gzip_header_buffer += chunk
                    try:
                        chunk = self._read_gzip_header(self._gzip_header_buffer)
                        self._in_gzip_body = True
                    except IndexError:
                        return # not a full header yet
                    except IOError, gzip_error:
                        self.setMessage('header-content-encoding', rs.BAD_GZIP,
                                        gzip_error=e(str(gzip_error))
                                        )
                        self._gzip_ok = False
                        return
                try:
                    chunk = self._decompress(chunk)
                except zlib.error, zlib_error:
                    self.setMessage('header-content-encoding', rs.BAD_ZLIB,
                                    zlib_error=e(str(zlib_error)),
                                    ok_zlib_len=self.res_body_sample[-1][0],
                                    chunk_sample=e(chunk[:20].encode('string_escape'))
                                    )
                    self._gzip_ok = False
                    return
            else:
                # we can't handle other codecs, so punt on body processing.
                return
        if self._gzip_ok:
            for processor in self.body_procs:
                processor(self, chunk)

    def _response_done(self, err):
        "Finish anaylsing the response, handling any parse errors."
        global outstanding_requests
        self.res_complete = True
        self.res_error = err
        if self.status_cb and self.type:
            self.status_cb("fetched %s (%s)" % (self.uri, self.type))
        self.res_body_md5 = self._md5_processor.digest()
        if err == None:
            pass
        elif err['desc'] == nbhttp.error.ERR_BODY_FORBIDDEN['desc']:
            self.setMessage('header-none', rs.BODY_NOT_ALLOWED)
        elif err['desc'] == nbhttp.error.ERR_EXTRA_DATA['desc']:
            self.res_body_len += len(err.get('detail', ''))
        elif err['desc'] == nbhttp.error.ERR_CHUNK['desc']:
            self.setMessage('header-transfer-encoding', rs.BAD_CHUNK,
                                chunk_sample=e(err.get('detail', '')[:20]))
        elif err['desc'] == nbhttp.error.ERR_CONNECT['desc']:
            self.res_complete = False
        elif err['desc'] == nbhttp.error.ERR_LEN_REQ['desc']:
            pass # FIXME: length required
        elif err['desc'] == nbhttp.error.ERR_URL['desc']:
            self.res_complete = False
        else:
            raise AssertionError, "Unknown response error: %s" % err

        # check payload basics
        if self.parsed_hdrs.has_key('content-length'):
            if self.res_body_len == self.parsed_hdrs['content-length']:
                self.setMessage('header-content-length', rs.CL_CORRECT)
            else:
                self.setMessage('header-content-length', rs.CL_INCORRECT, 
                                         body_length=self.res_body_len)                    
        if self.parsed_hdrs.has_key('content-md5'):
            c_md5_calc = base64.encodestring(self.res_body_md5)[:-1]
            if self.parsed_hdrs['content-md5'] == c_md5_calc:
                self.setMessage('header-content-md5', rs.CMD5_CORRECT)
            else:
                self.setMessage('header-content-md5', rs.CMD5_INCORRECT, 
                                         calc_md5=c_md5_calc)
        # analyse, check to see if we're done
        self.done()
        outstanding_requests -= 1
        if outstanding_requests == 0:
            nbhttp.stop()

    @staticmethod
    def _read_gzip_header(content):
        "Parse a GZIP header"
        # adapted from gzip.py
        FTEXT, FHCRC, FEXTRA, FNAME, FCOMMENT = 1, 2, 4, 8, 16
        if len(content) < 10: 
            raise IndexError, "Header not complete yet"
        magic = content[:2]
        if magic != '\037\213':
            raise IOError, u'Not a gzip header (magic is hex %s, should be 1f8b)' % magic.encode('hex-codec')
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
            # Read and discard a null-terminated string containing the filename
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
    req_hdrs = [('Accept-Encoding', 'gzip')]
    def status_p(msg):
        print msg
    class TestFetcher(RedFetcher):
        def done(self):
            print self.messages
    TestFetcher(uri, req_hdrs=req_hdrs, status_cb=status_p, type='test')