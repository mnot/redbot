"""
The Resource Expert Droid Fetcher.

RedFetcher fetches a single URI and analyses that response for common
problems and other interesting characteristics. It only makes one request,
based upon the provided headers.
"""

from configparser import SectionProxy
import time
from typing import Optional, Any, Dict, List, Tuple, Callable

from netaddr import IPAddress  # type: ignore
import thor
from thor.http.client import HttpClientExchange
import thor.http.error as httperr

from httplint import HttpRequestLinter, HttpResponseLinter
from httplint.note import categories, levels
from redbot.note import RedbotNote

from redbot import __version__
from redbot.type import StrHeaderListType, RawHeaderListType
from redbot.i18n import _

UA_STRING = f"RED/{__version__} (https://redbot.org/)".encode("ascii")


class RedHttpClient(thor.http.HttpClient):
    "Thor HttpClient for RedFetcher"

    def __init__(self, loop: Optional[thor.loop.LoopBase] = None) -> None:
        thor.http.HttpClient.__init__(self, loop)
        self.connect_timeout = 10
        self.read_timeout = 15
        self.idle_timeout = 5
        self.retry_delay = 1
        self.careful = False


class RedFetcher(thor.events.EventEmitter):
    """
    Abstract class for a fetcher.

    Fetches the given URI (with the provided method, headers and content) and:
        - emits 'status' and 'debug' as it progresses
        - emits 'fetch_done' when the fetch is finished.

    If provided, 'name' indicates the type of the request, and is used to
    help set notes and status events appropriately.
    """

    check_name = "undefined"
    client = RedHttpClient()

    def __init__(self, config: SectionProxy) -> None:
        thor.events.EventEmitter.__init__(self)
        self.config = config
        self.transfer_in = 0
        self.transfer_out = 0
        self.request_content: bytes
        self.response_header_length: int = 0
        self.response_content_processors: List[Callable[[bytes], None]] = []
        self.response_content_sample: List[Tuple[int, bytes]] = []
        self.response_decoded_sample: List[bytes] = []
        self.response_decoded_complete: bool = True
        self.max_sample_size = config.getint("max_sample_size", fallback=8192)

        self.request = HttpRequestLinter()
        self.nonfinal_responses: List[HttpResponseLinter] = []
        self.response = HttpResponseLinter()
        self.response.decoded.processors.append(self.sample_decoded)
        self.exchange: HttpClientExchange
        self.fetch_started = False
        self.fetch_error: Optional[httperr.HttpError] = None
        self.fetch_done = False
        self.setup_check_ip()

    def __getstate__(self) -> Dict[str, Any]:
        state: Dict[str, Any] = thor.events.EventEmitter.__getstate__(self)
        try:
            del state["exchange"]
        except KeyError:
            pass
        del state["response_content_processors"]
        return state

    def __repr__(self) -> str:
        out = [self.__class__.__name__]
        if hasattr(self.request, "uri") and self.request.uri:
            out.append(self.request.uri)
        if self.fetch_started:
            out.append("fetch_started")
        if self.fetch_done:
            out.append("fetch_done")
        return f"<{', '.join(out)} at {id(self):#x}>"

    def preflight(self) -> bool:
        """
        Check to see if we should bother running. Return True
        if so; False if not. Can be overridden.
        """
        return True

    def setup_check_ip(self) -> None:
        """
        Check to see if access to this IP is allowed.
        """
        if (
            not self.config.getboolean("enable_local_access", fallback=False)
        ) and self.client.check_ip is None:

            def check_ip(dns_result: str) -> bool:
                addr = IPAddress(dns_result)
                if not addr.is_global():
                    return False
                return True

            self.client.check_ip = check_ip

    def set_request(
        self,
        iri: str,
        method: str = "GET",
        headers: Optional[StrHeaderListType] = None,
        content: bytes = b"",
    ) -> None:
        """
        Set the resource's request. All values are strings.
        """
        self.request.method = method
        self.response.is_head_response = method == "HEAD"
        try:
            self.request.set_uri(iri)
        except httperr.UrlError as why:
            self.fetch_error = why
        if self.request.uri:
            self.response.base_uri = self.request.uri
        if headers:
            bheaders = [(n.encode("utf-8"), v.encode("utf-8")) for (n, v) in headers]
            self.request.process_headers(bheaders)
        self.request_content = content
        self.request.feed_content(content)
        self.request.complete = True  # cheating a bit

    def check(self) -> None:
        """
        Make an asynchronous HTTP request to uri, emitting 'status' as it's
        updated and 'fetch_done' when it's done. Reason is used to explain what the
        request is in the status callback.
        """
        if not self.preflight() or self.request.uri is None:
            # generally a good sign that we're not going much further.
            self._fetch_done()
            return

        self.fetch_started = True
        assert self.request.method, "method not set in check"
        assert self.request.uri, "uri not set in check"

        if "user-agent" not in [i[0].lower() for i in self.request.headers.text]:
            self.request.headers.process([(b"User-Agent", UA_STRING)])
        self.exchange = self.client.exchange()
        self.exchange.on("response_nonfinal", self._response_nonfinal)
        self.exchange.once("response_start", self._response_start)
        self.exchange.on("response_body", self._response_body)
        self.exchange.once("response_done", self._response_done)
        self.exchange.on("error", self._response_error)
        self.emit(
            "status",
            _("fetching %(uri)s (%(check_name)s)")
            % {"uri": self.request.uri, "check_name": self.check_name},
        )
        self.emit("debug", f"fetching {self.request.uri} ({self.check_name})")
        req_hdrs = [
            (k.encode("ascii", "replace"), v.encode("ascii", "replace"))
            for (k, v) in self.request.headers.text
        ]
        self.request.start_time = time.time()
        self.exchange.request_start(
            self.request.method.encode("ascii"),
            self.request.uri.encode("ascii"),
            req_hdrs,
        )
        if not self.fetch_done:  # the request could have immediately failed.
            if self.request_content:
                self.exchange.request_body(self.request_content)
                self.transfer_out += len(self.request_content)
        if not self.fetch_done:  # the request could have immediately failed.
            self.exchange.request_done([])

    def _response_nonfinal(
        self, status: bytes, phrase: bytes, res_headers: RawHeaderListType
    ) -> None:
        "Got a non-final response."
        nfres = HttpResponseLinter(start_time=time.time())
        assert (
            self.exchange.res_version
        ), "exchange.res_version not set in _response_nonfinal"
        nfres.process_response_topline(self.exchange.res_version, status, phrase)
        nfres.process_headers(res_headers)
        nfres.finish_content(True)
        self.nonfinal_responses.append(nfres)

        for wire_name, _ in res_headers:
            name = wire_name.lower()
            if name in [
                b"content-length",
                b"transfer-encoding",
                b"content-range",
                b"trailer",
            ]:
                self.response.notes.add(
                    f"header-{name.decode('ascii')}",
                    ONE_XX_BAD_HEADER,
                    response=status.decode("ascii", "replace").split()[0],
                    header_name=wire_name.decode("ascii"),
                )

    def _response_start(
        self, status: bytes, phrase: bytes, res_headers: RawHeaderListType
    ) -> None:
        "Process the response start-line and headers."
        if self.fetch_done:
            return
        self.response.start_time = time.time()
        assert (
            self.exchange.res_version
        ), "exchange.res_version not set in _response_start"
        self.response.process_response_topline(
            self.exchange.res_version, status, phrase
        )
        self.response.process_headers(res_headers)
        self.emit("response_headers_available")

    def _response_body(self, chunk: bytes) -> None:
        "Process a chunk of the response body."
        self.transfer_in += len(chunk)
        self.response.feed_content(chunk)
        for processor in self.response_content_processors:
            processor(chunk)

    def _response_done(self, trailers: List[Tuple[bytes, bytes]]) -> None:
        "Finish analysing the response, handling any parse errors."
        self.emit("debug", f"fetched {self.request.uri} ({self.check_name})")
        self.response.transfer_length = self.exchange.input_transfer_length
        self.response_header_length = self.exchange.input_header_length
        self.response.finish_content(True, trailers)
        self._fetch_done()

    def sample_response(self, chunk: bytes) -> None:
        "Sample the response content."
        if (
            self.max_sample_size == 0
            or self.response.content_length < self.max_sample_size
        ):
            self.response_content_sample.append((self.response.content_length, chunk))

    def sample_decoded(self, decoded_chunk: bytes) -> None:
        "Sample the decoded response content."
        if (
            self.max_sample_size == 0
            or self.response.decoded.length < self.max_sample_size
        ):
            self.response_decoded_sample.append(decoded_chunk)
        else:
            self.response_decoded_complete = False

    def _response_error(self, error: httperr.HttpError) -> None:
        "Handle an error encountered while fetching the response."
        self.emit(
            "debug",
            f"fetch error {self.request.uri} ({self.check_name}) - {error.desc}",
        )
        assert error.detail is not None, "detail not set in _response_error"
        err_sample = error.detail[:40] or ""
        if isinstance(error, httperr.ExtraDataError):
            if self.response.status_code == 304:
                self.response.notes.add("body", BODY_NOT_ALLOWED, sample=err_sample)
            else:
                self.response.notes.add("body", EXTRA_DATA, sample=err_sample)
        elif isinstance(error, httperr.ChunkError):
            self.response.notes.add(
                "field-transfer-encoding", BAD_CHUNK, chunk_sample=err_sample
            )
        elif isinstance(error, httperr.HeaderSpaceError):
            assert error.detail, "error.detail not set in _response_error"
            subject = f"field-{error.detail.lower().strip()}"
            self.response.notes.add(
                subject, HEADER_NAME_SPACE, header_name=error.detail
            )
            return
        else:
            self.fetch_error = error
        self._fetch_done()

    def _fetch_done(self) -> None:
        self.response.finish_time = time.time()
        if not self.fetch_done:
            self.fetch_done = True
            try:
                delattr(self, "exchange")
            except AttributeError:
                pass
            self.emit("fetch_done")

    def stop(self) -> None:
        "Stop the fetcher."
        if hasattr(self, "exchange"):
            if self.exchange.tcp_conn:
                self.exchange.tcp_conn.close()
        self._fetch_done()


class BODY_NOT_ALLOWED(RedbotNote):
    category = categories.CONNECTION
    level = levels.BAD
    _summary = "This response has content."
    _text = """\
HTTP defines a few special situations where a response does not allow content. This includes 101,
204 and 304 responses, as well as responses to the `HEAD` method.

This response had data after the headers ended, despite it being disallowed. Clients receiving it
may treat the content as the next response in the connection, leading to interoperability and
security issues.

The extra data started with:

    %(sample)s
"""


class EXTRA_DATA(RedbotNote):
    category = categories.CONNECTION
    level = levels.BAD
    _summary = "This response has extra data after it."
    _text = """\
The server sent data after the message ended. This can be caused by an incorrect `Content-Length`
header, or by a programming error in the server itself.

The extra data started with:

    %(sample)s
"""


class BAD_CHUNK(RedbotNote):
    category = categories.CONNECTION
    level = levels.BAD
    _summary = "This response has chunked encoding errors."
    _text = """\
The response indicates it uses HTTP chunked encoding, but there was a problem decoding the
chunking.

A valid chunk looks something like this:

    [chunk-size in hex]\\r\\n[chunk-data]\\r\\n

However, the chunk sent started like this:

    %(chunk_sample)s

This is a serious problem, because HTTP uses chunking to delimit one response from the next one;
incorrect chunking can lead to interoperability and security problems.

This issue is often caused by sending an integer chunk size instead of one in hex, or by sending
`Transfer-Encoding: chunked` without actually chunking the response body."""


class HEADER_NAME_SPACE(RedbotNote):
    category = categories.CONNECTION
    level = levels.BAD
    _summary = "This response has whitespace at the end of the '%(header_name)s' header field name."
    _text = """\
HTTP specifically bans whitespace between header field names and the colon, because they can easily
be confused by recipients; some will strip it, and others won't, leading to a variety of attacks.

Most HTTP implementations will refuse to process this message.
"""


class ONE_XX_BAD_HEADER(RedbotNote):
    category = categories.CONNECTION
    level = levels.BAD
    _summary = "The %(response)s response contains a %(header_name)s header."
    _text = """\
RFC 9110 requires that 1xx responses not contain a `%(header_name)s` header.

Clients receiving this response will either fail to process it or behave unexpectedly.
"""
