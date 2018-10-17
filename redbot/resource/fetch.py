"""
The Resource Expert Droid Fetcher.

RedFetcher fetches a single URI and analyses that response for common
problems and other interesting characteristics. It only makes one request,
based upon the provided headers.
"""

from configparser import SectionProxy
from typing import Any, Dict, List, Tuple, Type, Union

import thor
import thor.http.error as httperr

from redbot import __version__
from redbot.speak import Note, levels, categories
from redbot.message import HttpRequest, HttpResponse
from redbot.message.status import StatusChecker
from redbot.message.cache import checkCaching
from redbot.resource.robot_fetch import RobotFetcher
from redbot.type import StrHeaderListType, RawHeaderListType


UA_STRING = "RED/%s (https://redbot.org/)" % __version__

class RedHttpClient(thor.http.HttpClient):
    "Thor HttpClient for RedFetcher"

    def __init__(self, loop: thor.loop.LoopBase=None) -> None:
        thor.http.HttpClient.__init__(self, loop)
        self.connect_timeout = 10
        self.read_timeout = 15
        self.retry_delay = 1
        self.careful = False


class RedFetcher(thor.events.EventEmitter):
    """
    Abstract class for a fetcher.

    Fetches the given URI (with the provided method, headers and body) and:
      - emits 'status' as it progresses
      - emits 'fetch_done' when the fetch is finished.

    If provided, 'name' indicates the type of the request, and is used to
    help set notes and status events appropriately.
    """
    check_name = "undefined"
    response_phrase = "undefined"
    client = RedHttpClient()

    def __init__(self, config: SectionProxy) -> None:
        thor.events.EventEmitter.__init__(self)
        self.config = config
        self.robot_fetcher = RobotFetcher(self.config)
        self.notes = [] # type: List[Note]
        self.transfer_in = 0
        self.transfer_out = 0
        self.request = HttpRequest(self.ignore_note)  # type: HttpRequest
        self.nonfinal_responses = []                  # type: List[HttpResponse]
        self.response = HttpResponse(self.add_note)   # type: HttpResponse
        self.exchange = None                          # type: thor.http.ClientExchange
        self.follow_robots_txt = True # Should we pay attention to robots file?
        self.fetch_started = False
        self.fetch_done = False

    def __getstate__(self) -> Dict[str, Any]:
        state = thor.events.EventEmitter.__getstate__(self)
        del state['exchange']
        return state

    def __repr__(self) -> str:
        out = [self.__class__.__name__]
        if self.request.uri:
            out.append("%s" % self.request.uri)
        if self.fetch_started:
            out.append("fetch_started")
        if self.fetch_done:
            out.append("fetch_done")
        return "<%s at %#x>" % (", ".join(out), id(self))

    def add_note(self, subject: str, note: Type[Note], **kw: Union[str, int]) -> None:
        "Set a note."
        if 'response' not in kw:
            kw['response'] = self.response_phrase
        self.notes.append(note(subject, kw))

    def ignore_note(self, subject: str, note: Type[Note], **kw: str) -> None:
        "Ignore a note (for requests)."
        return

    def preflight(self) -> bool:
        """
        Check to see if we should bother running. Return True
        if so; False if not. Can be overridden.
        """
        return True

    def set_request(self, iri: str, method: str="GET",
                    req_hdrs: StrHeaderListType=None, req_body: bytes=None) -> None:
        """
        Set the resource's request. All values are strings.
        """
        self.request.method = method
        self.response.is_head_response = (method == "HEAD")   # type: ignore
        try:
            self.request.set_iri(iri)
        except httperr.UrlError as why:
            self.response.http_error = why
        self.response.base_uri = self.request.uri             # type: ignore
        if req_hdrs:
            self.request.set_headers(req_hdrs)
        self.request.payload = req_body # type: ignore    # FIXME: encoding
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

        if self.follow_robots_txt:
            self.robot_fetcher.once("robot-%s" % self.request.uri, self.run_continue)
            self.robot_fetcher.check_robots(self.request.uri)
        else:
            self.run_continue(True)

    def run_continue(self, allowed: bool) -> None:
        """
        Continue after getting the robots file.
        """
        if not allowed:
            self.response.http_error = RobotsTxtError()
            self._fetch_done()
            return

        self.fetch_started = True

        if 'user-agent' not in [i[0].lower() for i in self.request.headers]:
            self.request.headers.append(("User-Agent", UA_STRING))
        self.exchange = self.client.exchange()
        self.exchange.on('response_nonfinal', self._response_nonfinal)
        self.exchange.once('response_start', self._response_start)
        self.exchange.on('response_body', self._response_body)
        self.exchange.once('response_done', self._response_done)
        self.exchange.on('error', self._response_error)
        self.emit("status", "fetching %s (%s)" % (self.request.uri, self.check_name))
        req_hdrs = [(k.encode('ascii', 'replace'), v.encode('ascii', 'replace'))
                    for (k, v) in self.request.headers] # FIXME: should complain
        self.exchange.request_start(
            self.request.method.encode('ascii'), self.request.uri.encode('ascii'), req_hdrs)
        self.request.start_time = thor.time()
        if self.request.payload != None:
            self.exchange.request_body(self.request.payload)
            self.transfer_out += len(self.request.payload)
        self.exchange.request_done([])

    def _response_nonfinal(self, status: bytes, phrase: bytes,
                           res_headers: RawHeaderListType) -> None:
        "Got a non-final response."
        nfres = HttpResponse(self.add_note)
        nfres.process_top_line(self.exchange.res_version, status, phrase)
        nfres.process_raw_headers(res_headers)
        StatusChecker(nfres, self.request)
        self.nonfinal_responses.append(nfres)

    def _response_start(self, status: bytes, phrase: bytes,
                        res_headers: RawHeaderListType) -> None:
        "Process the response start-line and headers."
        self.response.start_time = thor.time()
        self.response.process_top_line(self.exchange.res_version, status, phrase)
        self.response.process_raw_headers(res_headers)
        StatusChecker(self.response, self.request)
        checkCaching(self.response, self.request)

    def _response_body(self, chunk: bytes) -> None:
        "Process a chunk of the response body."
        self.transfer_in += len(chunk)
        self.response.feed_body(chunk)

    def _response_done(self, trailers: List[Tuple[bytes, bytes]]) -> None:
        "Finish analysing the response, handling any parse errors."
        self.emit("status", "fetched %s (%s)" % (self.request.uri, self.check_name))
        self.response.transfer_length = self.exchange.input_transfer_length
        self.response.header_length = self.exchange.input_header_length
        self.response.body_done(True, trailers)
        self._fetch_done()

    def _response_error(self, error: httperr.HttpError) -> None:
        "Handle an error encountered while fetching the response."
        self.emit("status", "fetch error %s (%s) - %s" % (
            self.request.uri, self.check_name, error.desc))
        err_sample = error.detail[:40] or ""
        if isinstance(error, httperr.ExtraDataError):
            if self.response.status_code == "304":
                self.add_note('body', BODY_NOT_ALLOWED, sample=err_sample)
            else:
                self.add_note('body', EXTRA_DATA, sample=err_sample)
        elif isinstance(error, httperr.ChunkError):
            self.add_note('header-transfer-encoding', BAD_CHUNK, chunk_sample=err_sample)
        elif isinstance(error, httperr.HeaderSpaceError):
            subject = 'header-%s' % (error.detail.lower().strip())
            self.add_note(subject, HEADER_NAME_SPACE, header_name=error.detail)
        else:
            self.response.http_error = error
        self._fetch_done()

    def _fetch_done(self) -> None:
        if not self.fetch_done:
            self.fetch_done = True
            self.exchange = None
            self.emit("fetch_done")


class RobotsTxtError(httperr.HttpError):
    desc = "Forbidden by robots.txt"
    server_status = ("502", "Gateway Error")


class BODY_NOT_ALLOWED(Note):
    category = categories.CONNECTION
    level = levels.BAD
    summary = "%(response)s has a body."
    text = """\
HTTP defines a few special situations where a response does not allow a body. This includes 101,
204 and 304 responses, as well as responses to the `HEAD` method.

%(response)s had data after the headers ended, despite it being disallowed. Clients receiving it
may treat the body as the next response in the connection, leading to interoperability and security
issues.

The extra data started with:

    %(sample)s
"""

class EXTRA_DATA(Note):
    category = categories.CONNECTION
    level = levels.BAD
    summary = "%(response)s has extra data after it."
    text = """\
The server sent data after the message ended. This can be caused by an incorrect `Content-Length`
header, or by a programming error in the server itself.

The extra data started with:

    %(sample)s
"""

class BAD_CHUNK(Note):
    category = categories.CONNECTION
    level = levels.BAD
    summary = "%(response)s has chunked encoding errors."
    text = """\
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

class HEADER_NAME_SPACE(Note):
    category = categories.CONNECTION
    level = levels.BAD
    summary = "%(response)s has whitespace at the end of the '%(header_name)s' header field name."
    text = """\
HTTP specifically bans whitespace between header field names and the colon, because they can easily
be confused by recipients; some will strip it, and others won't, leading to a variety of attacks.

Most HTTP implementations will refuse to process this message.
"""
