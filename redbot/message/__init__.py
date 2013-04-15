#!/usr/bin/env python

"""
All checks that can be performed on a message in isolation.
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


import hashlib
import time
import zlib

from redbot.message.headers import process_headers
from redbot.formatter import f_num
import redbot.speak as rs


class HttpMessage(object):
    """
    Base class for HTTP message state.
    """
    def __init__(self, messages=None, check_type=None):
        self.is_request = None
        self.is_head_response = False
        self.version = ""
        self.base_uri = ""
        self.start_time = None
        self.complete = False
        self.complete_time = None
        self.headers = []
        self.clean_headers = []
        self.parsed_headers = {}
        self.header_length = 0
        self.payload = ""  # bytes, not unicode
        self.payload_len = 0
        self.payload_md5 = None
        self.payload_sample = []  # [(offset, chunk)]{,4} bytes, not unicode
        self.character_encoding = None
        self.uncompressed_len = 0
        self.uncompressed_md5 = None
        self.transfer_length = 0
        self.trailers = []
        self.http_error = None  # any parse errors encountered; see httperr
        self._context = {}
        self._md5_processor = hashlib.new('md5')
        self._md5_post_processor = hashlib.new('md5')
        self._gzip_processor = zlib.decompressobj(-zlib.MAX_WBITS)
        self._in_gzip_body = False
        self._gzip_header_buffer = ""
        self._gzip_ok = True # turn False if we have a problem
        self.check_type = check_type
        if messages is None:
            self.messages = []
        else:
            self.messages = messages
        
    def feed_headers(self, headers):
        """
        Feed a list of (key, value) header tuples in and process them.
        """
        self.headers = headers
        process_headers(self)
        self.character_encoding = self.parsed_headers.get(
            'content-type', (None, {})
        )[1].get('charset', 'utf-8') # default isn't UTF-8, but oh well
        
    def feed_body(self, chunk, body_procs=None):
        """
        Feed a chunk of the body in.
        
        If body_procs is a non-empty list, each processor will be 
        run over the chunk.
        """
        self.payload_sample.append((self.payload_len, chunk))
        if len(self.payload_sample) > 4: # TODO: bytes, not chunks
            self.payload_sample.pop(0)
        self._md5_processor.update(chunk)
        self.payload_len += len(chunk)
        if (not self.is_request) and self.status_code == "206":
            # only store 206; don't try to understand it
            self.payload += chunk
        else:
            chunk = self._process_content_codings(chunk)
            if self._gzip_ok and body_procs:
                for processor in body_procs:
                    # TODO: figure out why raising an error in a body_proc
                    # results in a "server dropped the connection" instead of
                    # a hard error.
                    processor(self, chunk)
        
    def body_done(self, trailers=None):
        """
        Signal that the body is done.
        """
        # TODO: check trailers
        self.trailers = trailers or []
        self.payload_md5 = self._md5_processor.digest()
        self.uncompressed_md5 = self._md5_post_processor.digest()

        if self.is_request or (not self.is_head_response and self.status_code not in ['304']):
            # check payload basics
            if self.parsed_headers.has_key('content-length'):
                if self.payload_len == self.parsed_headers['content-length']:
                    self.set_message('header-content-length', rs.CL_CORRECT)
                else:
                    self.set_message('header-content-length', 
                                    rs.CL_INCORRECT,
                                    body_length=f_num(self.payload_len)
                    )
            if self.parsed_headers.has_key('content-md5'):
                c_md5_calc = base64.encodestring(self.payload_md5)[:-1]
                if self.parsed_headers['content-md5'] == c_md5_calc:
                    self.set_message('header-content-md5', rs.CMD5_CORRECT)
                else:
                    self.set_message('header-content-md5', rs.CMD5_INCORRECT, calc_md5=c_md5_calc)

    def _process_content_codings(self, chunk):
        """
        Decode a chunk according to the message's content-encoding header.
        
        Currently supports gzip.
        """
        content_codings = self.parsed_headers.get('content-encoding', [])
        content_codings.reverse()
        for coding in content_codings:
            # TODO: deflate support
            if coding in ['gzip', 'x-gzip'] and self._gzip_ok:
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
                        self.set_message('header-content-encoding',
                                        rs.BAD_GZIP,
                                        gzip_error=str(gzip_error)
                        )
                        self._gzip_ok = False
                        return
                try:
                    chunk = self._gzip_processor.decompress(chunk)
                except zlib.error, zlib_error:
                    self.set_message(
                        'header-content-encoding', 
                        rs.BAD_ZLIB,
                        zlib_error=str(zlib_error),
                        ok_zlib_len=f_num(self.payload_sample[-1][0]),
                        chunk_sample=chunk[:20].encode('string_escape')
                    )
                    self._gzip_ok = False
                    return
            else:
                # we can't handle other codecs, so punt on body processing.
                return
        self._md5_post_processor.update(chunk)
        self.uncompressed_len += len(chunk)
        return chunk

    @staticmethod
    def _read_gzip_header(content):
        """
        Parse a string for a GZIP header; if present, return remainder of
        gzipped content.
        """
        # adapted from gzip.py
        gz_flags = {
            'FTEXT': 1,
            'FHCRC': 2,
            'FEXTRA': 4,
            'FNAME': 8,
            'FCOMMENT': 16
        }
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
        if flag & gz_flags['FEXTRA']:
            # Read & discard the extra field, if present
            xlen = ord(content_l.pop())
            xlen = xlen + 256*ord(content_l.pop())
            content_l = content_l[xlen:]
        if flag & gz_flags['FNAME']:
            # Read and discard a null-terminated string 
            # containing the filename
            while True:
                st1 = content_l.pop()
                if not content_l or st1 == '\000':
                    break
        if flag & gz_flags['FCOMMENT']:
            # Read and discard a null-terminated string containing a comment
            while True:
                st2 = content_l.pop()
                if not content_l or st2 == '\000':
                    break
        if flag & gz_flags['FHCRC']:
            content_l = content_l[2:]   # Read & discard the 16-bit header CRC
        return "".join(content_l)

    def __repr__(self):
        status = [self.__class__.__module__ + "." + self.__class__.__name__]
        return "<%s at %#x>" % (", ".join(status), id(self))

    def __getstate__(self):
        state = self.__dict__.copy()
        for key in [
            'set_message', 
            '_md5_processor', 
            '_gzip_processor', 
            '_md5_post_processor'
        ]:
            if state.has_key(key):
                del state[key]
        return state

    def set_context(self, **kw):
        "Set the message context."
        self._context = kw
        
    def set_message(self, subject, msg, subreq=None, **kw):
        "Set a message."
        kw.update(self._context)
        kw['response'] = rs.response.get(
            self.check_type, rs.response['this']
        )['en']
        self.messages.append(msg(subject, subreq, kw))
        
        
class HttpRequest(HttpMessage):
    """
    A HTTP Request message.
    """
    def __init__(self, messages=None, check_type=None):
        HttpMessage.__init__(self, messages, check_type)
        self.is_request = True
        self.method = None
        self.url = None

        
class HttpResponse(HttpMessage):
    """
    A HTTP Response message.
    """
    def __init__(self, messages=None, check_type=None):
        HttpMessage.__init__(self, messages, check_type)
        self.is_request = False
        self.status_code = None
        self.status_phrase = ""
        self.freshness_lifetime = None
        self.age = None
        self.store_shared = None
        self.store_private = None


class DummyMsg(HttpResponse):
    """
    A dummy HTTP message, for testing.
    """
    def __init__(self, messages=None, check_type=None):
        HttpResponse.__init__(self, messages, check_type)
        self.base_uri = "http://www.example.com/foo/bar/baz.html?bat=bam"
        self.start_time = time.time()
        self.status_phrase = ""
        self.msg_classes = []

    def set_message(self, subject, msg, **kw):
        "Record the classes of messages set."
        self.messages.append(msg(subject, None, kw))
        self.msg_classes.append(msg.__name__)

    def set_context(self, **kw):
        "Don't need context for testing."
        pass
