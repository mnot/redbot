"""
All checks that can be performed on a message in isolation.
"""

import base64
import binascii
import hashlib
import re
import time
from typing import Any, Callable, List, Dict, Tuple, Type, Union
from urllib.parse import urlsplit, urlunsplit, quote as urlquote
import zlib

import thor

from redbot.formatter import f_num
from redbot.message.headers import HeaderProcessor
from redbot.speak import Note, levels, categories, display_bytes
from redbot.syntax import rfc3986
from redbot.type import (
    StrHeaderListType,
    RawHeaderListType,
    HeaderDictType,
    AddNoteMethodType,
)


### configuration
MAX_URI = 8000


class HttpMessage(thor.events.EventEmitter):
    """
    Base class for HTTP message state.

    Emits "chunk" for each chunk of the response body (after decoding Content-Encoding).
    """

    def __init__(self, add_note: AddNoteMethodType) -> None:
        thor.events.EventEmitter.__init__(self)
        self.is_request: bool = None
        self.version: str = ""
        self.base_uri: str = ""
        self.method = None  # type: str
        self.uri = None  # type: str
        self.iri = None  # type: str
        self.status_code = None  # type: str
        self.status_phrase = ""
        self.is_head_response = False
        self.start_time: float = None
        self.complete: bool = False
        self.complete_time: float = None
        self.headers: StrHeaderListType = []
        self.parsed_headers: HeaderDictType = {}
        self.header_length: int = 0
        self.payload: bytes = b""  # Only used for 206 responses
        self.payload_len: int = 0
        self.payload_md5: bytes = None
        self.payload_sample: List[Tuple[int, bytes]] = []
        self.character_encoding: str = None
        self.decoded_len: int = 0
        self.decoded_md5: bytes = None
        self.decoded_sample: bytes = b""  # first decoded_sample_size bytes
        self.decoded_sample_size: int = 24 * 1024
        self._decoded_sample_seen: int = 0
        self.decoded_sample_complete: bool = True
        self._decode_ok: bool = True  # turn False if we have a problem
        self.transfer_length: int = 0
        self.trailers: RawHeaderListType = []
        self.http_error: thor.http.error.HttpError = None
        self._md5_processor = hashlib.new("md5")
        self._md5_post_processor = hashlib.new("md5")
        self._gzip_processor = zlib.decompressobj(-zlib.MAX_WBITS)
        self._in_gzip_body = False
        self._gzip_header_buffer = b""
        if not hasattr(self, "add_note"):
            self.add_note: AddNoteMethodType = add_note

    def __repr__(self) -> str:
        status = [self.__class__.__module__ + "." + self.__class__.__name__]
        return f"<{', '.join(status)} at {id(self):#x}>"

    def __getstate__(self) -> Dict[str, Any]:
        state: Dict[str, Any] = thor.events.EventEmitter.__getstate__(self)
        for key in [
            "_md5_processor",
            "_md5_post_processor",
            "_gzip_processor",
            "add_note",
        ]:
            if key in state:
                del state[key]
        return state

    def process_raw_headers(self, headers: RawHeaderListType) -> None:
        """
        Feed a list of (bytes name, bytes value) header tuples in and process them.
        """
        hp = HeaderProcessor(self)
        self.headers, self.parsed_headers = hp.process(headers)
        if "content-type" in self.parsed_headers:
            self.character_encoding = self.parsed_headers["content-type"][1].get(
                "charset", "utf-8"
            )
            # default isn't UTF-8, but oh well
        self.emit("headers_available")

    def set_headers(self, headers: StrHeaderListType) -> None:
        """
        Feed a list of (str name, str value) header tuples in. Do not process.
        """
        self.headers = headers
        self.emit("headers_available")

    def feed_body(self, chunk: bytes) -> None:
        """
        Feed a chunk of the body in.

        If body_procs is a non-empty list, each processor will be
        run over the chunk.

        decoded_sample is also populated.
        """
        self.payload_sample.append((self.payload_len, chunk))
        if len(self.payload_sample) > 4:
            self.payload_sample.pop(0)
        self._md5_processor.update(chunk)
        if (isinstance(self, HttpResponse)) and self.status_code == "206":
            # only store 206; don't try to understand it
            self.payload += chunk
        else:
            decoded_chunk = self._process_content_codings(chunk)
            if self._decode_ok:
                if (
                    self._decoded_sample_seen + len(decoded_chunk)
                    < self.decoded_sample_size
                ):
                    self.decoded_sample += decoded_chunk
                    self._decoded_sample_seen += len(decoded_chunk)
                elif self._decoded_sample_seen < self.decoded_sample_size:
                    max_chunk = self.decoded_sample_size - self._decoded_sample_seen
                    self.decoded_sample += decoded_chunk[:max_chunk]
                    self._decoded_sample_seen += len(decoded_chunk)
                    self.decoded_sample_complete = False
                else:
                    self.decoded_sample_complete = False
                self.emit("chunk", decoded_chunk)
            else:
                self.decoded_sample_complete = False
        self.payload_len += len(chunk)

    def body_done(self, complete: bool, trailers: RawHeaderListType = None) -> None:
        """
        Signal that the body is done. Complete should be True if we
        know it's complete (e.g., final chunk, Content-Length).
        """
        self.complete = complete
        self.complete_time = thor.time()
        self.trailers = trailers or []
        self.payload_md5 = self._md5_processor.digest()
        self.decoded_md5 = self._md5_post_processor.digest()

        if isinstance(self, HttpRequest) or (
            isinstance(self, HttpResponse)
            and not self.is_head_response
            and self.status_code not in ["304"]
        ):
            # check payload basics
            if "content-length" in self.parsed_headers:
                if self.payload_len == self.parsed_headers["content-length"]:
                    self.add_note("header-content-length", CL_CORRECT)
                else:
                    self.add_note(
                        "header-content-length",
                        CL_INCORRECT,
                        body_length=f_num(self.payload_len),
                    )
            if "content-md5" in self.parsed_headers:
                c_md5_calc = base64.encodebytes(self.payload_md5)[:-1]
                if self.parsed_headers["content-md5"] == c_md5_calc:
                    self.add_note("header-content-md5", CMD5_CORRECT)
                else:
                    self.add_note(
                        "header-content-md5", CMD5_INCORRECT, calc_md5=c_md5_calc
                    )
        self.emit("content_available")

    def _process_content_codings(self, chunk: bytes) -> bytes:
        """
        Decode a chunk according to the message's content-encoding header.

        Currently supports gzip.
        """
        content_codings = self.parsed_headers.get("content-encoding", [])
        content_codings.reverse()
        for coding in content_codings:
            if coding in ["gzip", "x-gzip"] and self._decode_ok:
                if not self._in_gzip_body:
                    self._gzip_header_buffer += chunk
                    try:
                        chunk = self._read_gzip_header(self._gzip_header_buffer)
                        self._in_gzip_body = True
                    except IndexError:
                        return b""  # not a full header yet
                    except IOError as gzip_error:
                        self.add_note(
                            "header-content-encoding",
                            BAD_GZIP,
                            gzip_error=str(gzip_error),
                        )
                        self._decode_ok = False
                        return b""
                try:
                    chunk = self._gzip_processor.decompress(chunk)
                except zlib.error as zlib_error:
                    self.add_note(
                        "header-content-encoding",
                        BAD_ZLIB,
                        zlib_error=str(zlib_error),
                        ok_zlib_len=f_num(self.payload_len),
                        chunk_sample=display_bytes(chunk),
                    )
                    self._decode_ok = False
                    return b""
            else:
                # we can't handle other codecs, so punt on body processing.
                self._decode_ok = False
                return b""
        self._md5_post_processor.update(chunk)
        self.decoded_len += len(chunk)
        return chunk

    @staticmethod
    def _read_gzip_header(content: bytes) -> bytes:
        """
        Parse a string for a GZIP header; if present, return remainder of
        gzipped content.
        """
        # adapted from gzip.py
        gz_flags = {"FTEXT": 1, "FHCRC": 2, "FEXTRA": 4, "FNAME": 8, "FCOMMENT": 16}
        if len(content) < 10:
            raise IndexError("Header not complete yet")
        magic = content[:2]
        if magic != b"\037\213":
            raise IOError(
                f"Not a gzip header (magic is hex {binascii.b2a_hex(magic).decode('ascii')}, "
                "should be 1f8b)"
            )
        method = ord(content[2:3])
        if method != 8:
            raise IOError("Unknown compression method")
        flag = ord(content[3:4])
        content_l = list(content[10:])
        if flag & gz_flags["FEXTRA"]:
            # Read & discard the extra field, if present
            xlen = content_l.pop(0)
            xlen = xlen + 256 * content_l.pop(0)
            content_l = content_l[xlen:]
        if flag & gz_flags["FNAME"]:
            # Read and discard a null-terminated string
            # containing the filename
            while True:
                st1 = content_l.pop(0)
                if not content_l or st1 == 0:
                    break
        if flag & gz_flags["FCOMMENT"]:
            # Read and discard a null-terminated string containing a comment
            while True:
                st2 = content_l.pop(0)
                if not content_l or st2 == 0:
                    break
        if flag & gz_flags["FHCRC"]:
            content_l = content_l[2:]  # Read & discard the 16-bit header CRC
        return bytes(content_l)


class HttpRequest(HttpMessage):
    """
    A HTTP Request message.
    """

    def __init__(self, add_note: AddNoteMethodType) -> None:
        HttpMessage.__init__(self, add_note)
        self.is_request = True  # type: bool

    def set_iri(self, iri: str) -> None:
        """
        Given a unicode string (possibly an IRI), convert to a URI and make sure it's sensible.
        """
        self.iri = iri
        try:
            self.uri = self.iri_to_uri(iri)
        except (ValueError, UnicodeError) as why:
            raise thor.http.error.UrlError(why.args[0])
        if not re.match(rf"^\s*{rfc3986.URI}\s*$", self.uri, re.VERBOSE):
            self.add_note("uri", URI_BAD_SYNTAX)
        if "#" in self.uri:
            # chop off the fragment
            self.uri = self.uri[: self.uri.index("#")]
        if len(self.uri) > MAX_URI:
            self.add_note("uri", URI_TOO_LONG, uri_len=f_num(len(self.uri)))

    @staticmethod
    def iri_to_uri(iri: str) -> str:
        "Takes a unicode string that can contain an IRI and emits a unicode URI."
        scheme, authority, path, query, frag = urlsplit(iri)
        if ":" in authority:
            host, port = authority.split(":", 1)
            authority = host.encode("idna").decode("ascii") + f":{port}"
        else:
            authority = authority.encode("idna").decode("ascii")
        sub_delims = "!$&'()*+,;="
        pchar = "-.+~" + sub_delims + ":@" + "%"
        path = urlquote(path, safe=pchar + "/")
        quer = urlquote(query, safe=pchar + "/?")
        frag = urlquote(frag, safe=pchar + "/?")
        return urlunsplit((scheme, authority, path, quer, frag))


class HttpResponse(HttpMessage):
    """
    A HTTP Response message.
    """

    def __init__(self, add_note: AddNoteMethodType) -> None:
        HttpMessage.__init__(self, add_note)
        self.is_request = False
        self.freshness_lifetime = None  # type: int
        self.age = None  # type: int
        self.store_shared = None  # type: bool
        self.store_private = None  # type: bool

    def process_top_line(
        self, version: bytes, status_code: bytes, status_phrase: bytes
    ) -> None:
        self.version = version.decode("ascii", "replace")
        self.status_code = status_code.decode("ascii", "replace")
        try:
            self.status_phrase = status_phrase.decode("ascii", "strict")
        except UnicodeDecodeError:
            self.status_phrase = status_phrase.decode("ascii", "replace")
            self.add_note("status", STATUS_PHRASE_ENCODING)


class DummyMsg(HttpResponse):
    """
    A dummy HTTP message, for testing.
    """

    def __init__(self, add_note: AddNoteMethodType = None) -> None:
        HttpResponse.__init__(self, self.dummy_add_note)
        self.base_uri = "http://www.example.com/foo/bar/baz.html?bat=bam"
        self.start_time = time.time()
        self.status_phrase = ""
        self.notes = []  # type: List[Note]
        self.note_classes = []  # type: List[str]

    def dummy_add_note(
        self, subject: str, note: Type[Note], **kw: Union[str, int]
    ) -> None:
        "Record the classes of notes set."
        self.notes.append(note(subject, kw))
        self.note_classes.append(note.__name__)


class URI_TOO_LONG(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = "The URI is very long (%(uri_len)s characters)."
    text = """\
Long URIs aren't supported by some implementations, including proxies. A reasonable upper size
limit is 8192 characters."""


class URI_BAD_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = "The URI's syntax isn't valid."
    text = """\
This isn't a valid URI. Look for illegal characters and other problems; see
[RFC3986](http://www.ietf.org/rfc/rfc3986.txt) for more information."""


class STATUS_PHRASE_ENCODING(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = "The status phrase contains non-ASCII characters."
    text = """\
The status phrase can only contain ASCII characters. REDbot has detected (and possibly removed)
non-ASCII characters in it."""


class CL_CORRECT(Note):
    category = categories.GENERAL
    level = levels.GOOD
    summary = "The Content-Length header is correct."
    text = """\
`Content-Length` is used by HTTP to delimit messages; that is, to mark the end of one message and
the beginning of the next. REDbot has checked the length of the body and found the `Content-Length`
to be correct."""


class CL_INCORRECT(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = "%(response)s's Content-Length header is incorrect."
    text = """\
`Content-Length` is used by HTTP to delimit messages; that is, to mark the end of one message and
the beginning of the next. REDbot has checked the length of the body and found the `Content-Length`
is not correct. This can cause problems not only with connection handling, but also caching, since
an incomplete response is considered uncacheable.

The actual body size sent was %(body_length)s bytes."""


class CMD5_CORRECT(Note):
    category = categories.GENERAL
    level = levels.GOOD
    summary = "The Content-MD5 header is correct."
    text = """\
`Content-MD5` is a hash of the body, and can be used to ensure integrity of the response. REDbot
has checked its value and found it to be correct."""


class CMD5_INCORRECT(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = "The Content-MD5 header is incorrect."
    text = """\
`Content-MD5` is a hash of the body, and can be used to ensure integrity of the response. REDbot has
checked its value and found it to be incorrect; i.e., the given `Content-MD5` does not match what
REDbot thinks it should be (%(calc_md5)s)."""


class BAD_GZIP(Note):
    category = categories.CONNEG
    level = levels.BAD
    summary = "%(response)s was compressed using GZip, but the header wasn't \
valid."
    text = """\
GZip-compressed responses have a header that contains metadata. %(response)s's header wasn't valid;
the error encountered was "`%(gzip_error)s`"."""


class BAD_ZLIB(Note):
    category = categories.CONNEG
    level = levels.BAD
    summary = "%(response)s was compressed using GZip, but the data was corrupt."
    text = """\
GZip-compressed responses use zlib compression to reduce the number of bytes transferred on the
wire. However, this response could not be decompressed; the error encountered was
"`%(zlib_error)s`".

%(ok_zlib_len)s bytes were decompressed successfully before this; the erroneous chunk starts with (in hex):

    %(chunk_sample)s
"""
