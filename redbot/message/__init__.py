#!/usr/bin/env python

"""
All checks that can be performed on a message in isolation.
"""

import base64
import hashlib
import re
import time
import urllib
import urlparse
import zlib

from redbot.message.headers import HeaderProcessor
from redbot.formatter import f_num
from redbot.speak import Note, levels, categories, response

from redbot.syntax import rfc3986

import thor

### configuration
MAX_URI = 8000

class HttpMessage(thor.events.EventEmitter):
    """
    Base class for HTTP message state.

    Emits "chunk" for each chunk of the response body (after decoding Content-Encoding).
    """
    def __init__(self, add_note, name=None):
        thor.events.EventEmitter.__init__(self)
        if not hasattr(self, 'add_note'):
            self.add_note = add_note
        self.name = name
        self.is_request = None
        self.version = ""
        self.base_uri = ""
        self.start_time = None
        self.complete = False
        self.complete_time = None
        self.headers = []
        self.parsed_headers = {}
        self.header_length = 0
        self.payload = ""  # bytes, not unicode. Only used for 206 responses
        self.payload_len = 0
        self.payload_md5 = None
        self.payload_sample = []  # [(offset, chunk)]{,4} bytes, not unicode
        self.character_encoding = None
        self.decoded_len = 0
        self.decoded_md5 = None
        self.decoded_sample = "" # first decoded_sample_size bytes
        self.decoded_sample_size = 128 * 1024
        self._decoded_sample_seen = 0
        self.decoded_sample_complete = True
        self._decode_ok = True # turn False if we have a problem
        self.transfer_length = 0
        self.trailers = []
        self.http_error = None  # any parse errors encountered; see httperr
        self._md5_processor = hashlib.new('md5')
        self._md5_post_processor = hashlib.new('md5')
        self._gzip_processor = zlib.decompressobj(-zlib.MAX_WBITS)
        self._in_gzip_body = False
        self._gzip_header_buffer = ""

    def __repr__(self):
        status = [self.__class__.__module__ + "." + self.__class__.__name__]
        return "<%s at %#x>" % (", ".join(status), id(self))

    def __getstate__(self):
        state = self.__dict__.copy()
        for key in [
                '_md5_processor',
                '_md5_post_processor',
                '_gzip_processor',
        ]:
            if state.has_key(key):
                del state[key]
        return state

    def set_headers(self, headers):
        """
        Feed a list of (key, value) header tuples in and process them.
        """
        self.headers = headers
        HeaderProcessor(self)
        self.character_encoding = self.parsed_headers.get(
            'content-type', (None, {})
        )[1].get('charset', 'utf-8') # default isn't UTF-8, but oh well
        self.emit("headers_available")

    def feed_body(self, chunk):
        """
        Feed a chunk of the body in.

        If body_procs is a non-empty list, each processor will be
        run over the chunk.

        decoded_sample is also populated.
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
                if self._decoded_sample_seen + len(decoded_chunk) < self.decoded_sample_size:
                    self.decoded_sample += decoded_chunk
                    self._decoded_sample_seen += len(decoded_chunk)
                elif self._decoded_sample_seen < self.decoded_sample_size:
                    max_chunk = self.decoded_sample_size - self._decoded_sample_seen
                    self.decoded_sample += decoded_chunk[:max_chunk]
                    self._decoded_sample_seen += len(decoded_chunk)
                    self.decoded_sample_complete = False
                else:
                    self.decoded_sample_complete = False
                self.emit("chunk", self, decoded_chunk)
            else:
                self.decoded_sample_complete = False

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
                    self.add_note('header-content-length', CL_CORRECT)
                else:
                    self.add_note('header-content-length',
                                  CL_INCORRECT,
                                  body_length=f_num(self.payload_len))
            if self.parsed_headers.has_key('content-md5'):
                c_md5_calc = base64.encodestring(self.payload_md5)[:-1]
                if self.parsed_headers['content-md5'] == c_md5_calc:
                    self.add_note('header-content-md5', CMD5_CORRECT)
                else:
                    self.add_note('header-content-md5',
                                  CMD5_INCORRECT, calc_md5=c_md5_calc)
        self.emit('content_available')

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
                        chunk = self._read_gzip_header(self._gzip_header_buffer)
                        self._in_gzip_body = True
                    except IndexError:
                        return '' # not a full header yet
                    except IOError, gzip_error:
                        self.add_note('header-content-encoding',
                                      BAD_GZIP,
                                      gzip_error=str(gzip_error))
                        self._decode_ok = False
                        return
                try:
                    chunk = self._gzip_processor.decompress(chunk)
                except zlib.error, zlib_error:
                    self.add_note(
                        'header-content-encoding',
                        BAD_ZLIB,
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
        method = ord(content[2:3])
        if method != 8:
            raise IOError, 'Unknown compression method'
        flag = ord(content[3:4])
        content_l = list(content[10:])
        if flag & gz_flags['FEXTRA']:
            # Read & discard the extra field, if present
            xlen = ord(content_l.pop(0))
            xlen = xlen + 256*ord(content_l.pop(0))
            content_l = content_l[xlen:]
        if flag & gz_flags['FNAME']:
            # Read and discard a null-terminated string
            # containing the filename
            while True:
                st1 = content_l.pop(0)
                if not content_l or st1 == '\000':
                    break
        if flag & gz_flags['FCOMMENT']:
            # Read and discard a null-terminated string containing a comment
            while True:
                st2 = content_l.pop(0)
                if not content_l or st2 == '\000':
                    break
        if flag & gz_flags['FHCRC']:
            content_l = content_l[2:]   # Read & discard the 16-bit header CRC
        return "".join(content_l)


class HttpRequest(HttpMessage):
    """
    A HTTP Request message.
    """
    def __init__(self, add_note, name=None):
        HttpMessage.__init__(self, add_note, name)
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
            self.http_error = thor.http.error.UrlError(why[0])
            return
        if not re.match(r"^\s*%s\s*$" % rfc3986.URI, self.uri, re.VERBOSE):
            self.add_note('uri', URI_BAD_SYNTAX)
        if '#' in self.uri:
            # chop off the fragment
            self.uri = self.uri[:self.uri.index('#')]
        if len(self.uri) > MAX_URI:
            self.add_note('uri', URI_TOO_LONG, uri_len=f_num(len(self.uri)))

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
        sub_delims = "!$&'()*+,;="
        pchar = "-.+~" + sub_delims + ":@"
        path = urllib.quote(path.encode('utf-8'), safe=pchar+"/")
        quer = urllib.quote(query.encode('utf-8'), safe=pchar+"/?")
        frag = urllib.quote(frag.encode('utf-8'), safe=pchar+"/?")
        return urlparse.urlunsplit((scheme, authority, path, quer, frag))


class HttpResponse(HttpMessage):
    """
    A HTTP Response message.
    """
    def __init__(self, add_note, name=None):
        HttpMessage.__init__(self, add_note, name)
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
    def __init__(self, add_note=None, name=None):
        HttpResponse.__init__(self, add_note, name)
        self.base_uri = "http://www.example.com/foo/bar/baz.html?bat=bam"
        self.start_time = time.time()
        self.status_phrase = ""
        self.notes = []
        self.note_classes = []

    def add_note(self, subject, note, subreq=None, **kw):
        "Record the classes of notes set."
        self.notes.append(note(subject, None, kw))
        self.note_classes.append(note.__name__)



class URI_TOO_LONG(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = u"The URI is very long (%(uri_len)s characters)."
    text = u"""\
Long URIs aren't supported by some implementations, including proxies. A reasonable upper size
limit is 8192 characters."""

class URI_BAD_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"The URI's syntax isn't valid."
    text = u"""\
This isn't a valid URI. Look for illegal characters and other problems; see
[RFC3986](http://www.ietf.org/rfc/rfc3986.txt) for more information."""

class CL_CORRECT(Note):
    category = categories.GENERAL
    level = levels.GOOD
    summary = u'The Content-Length header is correct.'
    text = u"""\
`Content-Length` is used by HTTP to delimit messages; that is, to mark the end of one message and
the beginning of the next. RED has checked the length of the body and found the `Content-Length` to
be correct."""

class CL_INCORRECT(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"%(response)s's Content-Length header is incorrect."
    text = u"""\
`Content-Length` is used by HTTP to delimit messages; that is, to mark the end of one message and
the beginning of the next. RED has checked the length of the body and found the `Content-Length` is
not correct. This can cause problems not only with connection handling, but also caching, since an
incomplete response is considered uncacheable.

The actual body size sent was %(body_length)s bytes."""

class CMD5_CORRECT(Note):
    category = categories.GENERAL
    level = levels.GOOD
    summary = u'The Content-MD5 header is correct.'
    text = u"""\
`Content-MD5` is a hash of the body, and can be used to ensure integrity of the response. RED has
checked its value and found it to be correct."""

class CMD5_INCORRECT(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u'The Content-MD5 header is incorrect.'
    text = u"""\
`Content-MD5` is a hash of the body, and can be used to ensure integrity of the response. RED has
checked its value and found it to be incorrect; i.e., the given `Content-MD5` does not match what
RED thinks it should be (%(calc_md5)s)."""

class BAD_GZIP(Note):
    category = categories.CONNEG
    level = levels.BAD
    summary = u"%(response)s was compressed using GZip, but the header wasn't \
valid."
    text = u"""\
GZip-compressed responses have a header that contains metadata. %(response)s's header wasn't valid;
the error encountered was "`%(gzip_error)s`"."""

class BAD_ZLIB(Note):
    category = categories.CONNEG
    level = levels.BAD
    summary = u"%(response)s was compressed using GZip, but the data was corrupt."
    text = u"""\
GZip-compressed responses use zlib compression to reduce the number of bytes transferred on the
wire. However, this response could not be decompressed; the error encountered was
"`%(zlib_error)s`".

%(ok_zlib_len)s bytes were decompressed successfully before this; the erroneous chunk starts with
"`%(chunk_sample)s`"."""