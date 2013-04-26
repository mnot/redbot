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

import base64
import hashlib
import re
import time
import urllib
import urlparse
import zlib

from redbot.message import link_parse
from redbot.message.headers import process_headers
from redbot.formatter import f_num
import redbot.speak as rs
from redbot.message.uri_syntax import URI

import thor.http.error as httperr

### configuration
MAX_URI = 8000

class HttpMessage(object):
    """
    Base class for HTTP message state.
    """
    def __init__(self, notes=None, name=None):
        self.is_request = None
        self.version = ""
        self.base_uri = ""
        self.start_time = None
        self.complete = False
        self.complete_time = None
        self.headers = []
        self.parsed_headers = {}
        self.header_length = 0
        self.payload = ""  # bytes, not unicode
        self.payload_len = 0
        self.payload_md5 = None
        self.payload_sample = []  # [(offset, chunk)]{,4} bytes, not unicode
        self.character_encoding = None
        self.decoded_len = 0
        self.decoded_md5 = None
        self._decoded_procs = []
        self._decode_ok = True # turn False if we have a problem
        self._link_parser = None
        self.transfer_length = 0
        self.trailers = []
        self.http_error = None  # any parse errors encountered; see httperr
        self._context = {}
        self._md5_processor = hashlib.new('md5')
        self._md5_post_processor = hashlib.new('md5')
        self._gzip_processor = zlib.decompressobj(-zlib.MAX_WBITS)
        self._in_gzip_body = False
        self._gzip_header_buffer = ""
        self.name = name
        if notes is None:
            self.notes = []
        else:
            self.notes = notes

    def set_decoded_procs(self, decoded_procs):
        "Set a list of processors for the decoded body."
        self._decoded_procs = decoded_procs

    def set_link_procs(self, link_procs):
        "Set a list of link processors that get called upon each link."
        self._link_parser = link_parse.HTMLLinkParser(
            self.base_uri, link_procs)
        
    def set_headers(self, headers):
        """
        Feed a list of (key, value) header tuples in and process them.
        """
        self.headers = headers
        process_headers(self)
        self.character_encoding = self.parsed_headers.get(
            'content-type', (None, {})
        )[1].get('charset', 'utf-8') # default isn't UTF-8, but oh well
        
    def feed_body(self, chunk):
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
            decoded_chunk = self._process_content_codings(chunk)
            if self._decode_ok:
                for processor in self._decoded_procs:
                    # TODO: figure out why raising an error in a body_proc
                    # results in a "server dropped the connection" instead of
                    # a hard error.
                    processor(self, decoded_chunk)
                if self._link_parser:
                    self._link_parser.feed(self, decoded_chunk)
        
    def body_done(self, complete, trailers=None):
        """
        Signal that the body is done. Complete should be True if we 
        know it's complete.
        """
        # TODO: check trailers
        self.complete = complete
        self.trailers = trailers or []
        self.payload_md5 = self._md5_processor.digest()
        self.decoded_md5 = self._md5_post_processor.digest()

        if self.is_request or \
          (not self.is_head_response and self.status_code not in ['304']):
            # check payload basics
            if self.parsed_headers.has_key('content-length'):
                if self.payload_len == self.parsed_headers['content-length']:
                    self.add_note('header-content-length', rs.CL_CORRECT)
                else:
                    self.add_note('header-content-length', 
                                    rs.CL_INCORRECT,
                                    body_length=f_num(self.payload_len)
                    )
            if self.parsed_headers.has_key('content-md5'):
                c_md5_calc = base64.encodestring(self.payload_md5)[:-1]
                if self.parsed_headers['content-md5'] == c_md5_calc:
                    self.add_note('header-content-md5', rs.CMD5_CORRECT)
                else:
                    self.add_note('header-content-md5', 
                                  rs.CMD5_INCORRECT, calc_md5=c_md5_calc)

    def _process_content_codings(self, chunk):
        """
        Decode a chunk according to the message's content-encoding header.
        
        Currently supports gzip.
        """
        content_codings = self.parsed_headers.get('content-encoding', [])
        content_codings.reverse()
        for coding in content_codings:
            # TODO: deflate support
            if coding in ['gzip', 'x-gzip'] and self._decode_ok:
                if not self._in_gzip_body:
                    self._gzip_header_buffer += chunk
                    try:
                        chunk = self._read_gzip_header(
                            self._gzip_header_buffer
                        )
                        self._in_gzip_body = True
                    except IndexError:
                        return '' # not a full header yet
                    except IOError, gzip_error:
                        self.add_note('header-content-encoding',
                                        rs.BAD_GZIP,
                                        gzip_error=str(gzip_error)
                        )
                        self._decode_ok = False
                        return
                try:
                    chunk = self._gzip_processor.decompress(chunk)
                except zlib.error, zlib_error:
                    self.add_note(
                        'header-content-encoding', 
                        rs.BAD_ZLIB,
                        zlib_error=str(zlib_error),
                        ok_zlib_len=f_num(self.payload_sample[-1][0]),
                        chunk_sample=chunk[:20].encode('string_escape')
                    )
                    self._decode_ok = False
                    return
            else:
                # we can't handle other codecs, so punt on body processing.
                self._decode_ok = False
                return
        self._md5_post_processor.update(chunk)
        self.decoded_len += len(chunk)
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
            'add_note', 
            '_md5_processor', 
            '_gzip_processor', 
            '_md5_post_processor'
        ]:
            if state.has_key(key):
                del state[key]
        return state

    def set_context(self, **kw):
        "Set the note context."
        self._context = kw
        
    def add_note(self, subject, note, subreq=None, **kw):
        "Set a note."
        kw.update(self._context)
        kw['response'] = rs.response.get(
            self.name, rs.response['this']
        )['en']
        self.notes.append(note(subject, subreq, kw))
        
        
class HttpRequest(HttpMessage):
    """
    A HTTP Request message.
    """
    def __init__(self, notes=None, name=None):
        HttpMessage.__init__(self, notes, name)
        self.is_request = True
        self.method = None
        self.uri = None
        
    def set_iri(self, iri):
        """
        Given an IRI or URI, convert to a URI and make sure it's sensible.
        """
        try:
            self.uri = self.iri_to_uri(iri)
        except (ValueError, UnicodeError), why:
            self.http_error = httperr.UrlError(why[0])
            return
        if not re.match("^\s*%s\s*$" % URI, self.uri, re.VERBOSE):
            self.add_note('uri', rs.URI_BAD_SYNTAX)
        if '#' in self.uri:
            # chop off the fragment
            self.uri = self.uri[:self.uri.index('#')]
        if len(self.uri) > MAX_URI:
            self.add_note('uri',
                rs.URI_TOO_LONG,
                uri_len=f_num(len(self.uri))
            )

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

        
class HttpResponse(HttpMessage):
    """
    A HTTP Response message.
    """
    def __init__(self, notes=None, name=None):
        HttpMessage.__init__(self, notes, name)
        self.is_request = False
        self.is_head_response = False
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
    def __init__(self, notes=None, name=None):
        HttpResponse.__init__(self, notes, name)
        self.base_uri = "http://www.example.com/foo/bar/baz.html?bat=bam"
        self.start_time = time.time()
        self.status_phrase = ""
        self.note_classes = []

    def add_note(self, subject, note, **kw):
        "Record the classes of notes set."
        self.notes.append(note(subject, None, kw))
        self.note_classes.append(note.__name__)

    def set_context(self, **kw):
        "Don't need context for testing."
        pass
