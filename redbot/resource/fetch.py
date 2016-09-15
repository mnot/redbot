#!/usr/bin/env python

"""
The Resource Expert Droid Fetcher.

RedFetcher fetches a single URI and analyses that response for common
problems and other interesting characteristics. It only makes one request,
based upon the provided headers.
"""

import hashlib
from os import path
from robotparser import RobotFileParser
from urlparse import urlsplit

import thor
import thor.http.error as httperr

from redbot import __version__
from redbot.cache_file import CacheFile
from redbot.speak import Note, levels, categories, response as response_phrase
from redbot.message import HttpRequest, HttpResponse
from redbot.message.status import StatusChecker
from redbot.message.cache import checkCaching


UA_STRING = u"RED/%s (https://redbot.org/)" % __version__

class RedHttpClient(thor.http.HttpClient):
    "Thor HttpClient for RedFetcher"
    connect_timeout = 10
    read_timeout = 15


class RedFetcher(thor.events.EventEmitter):
    """
    Abstract class for a fetcher.

    Fetches the given URI (with the provided method, headers and body) and:
      - emits 'status' as it progresses
      - emits 'fetch_done' when the fetch is finished.

    If provided, 'name' indicates the type of the request, and is used to
    help set notes and status events appropriately.
    """
    client = RedHttpClient()
    robot_files = {} # cache of robots.txt
    robot_cache_dir = None
    robot_lookups = {}

    def __init__(self, iri, method="GET", req_hdrs=None, req_body=None, name=None):
        thor.events.EventEmitter.__init__(self)
        self.name = name
        self.notes = []
        self.transfer_in = 0
        self.transfer_out = 0
        self.request = HttpRequest(self.add_note, self.name)
        self.request.method = method
        self.request.set_iri(iri)
        self.request.headers = req_hdrs or []
        self.request.payload = req_body
        self.response = HttpResponse(self.add_note, self.name)
        self.response.is_head_response = (method == "HEAD")
        self.response.base_uri = self.request.uri
        self.exchange = None
        self.follow_robots_txt = True # Should we pay attention to robots file?
        self._st = [] # FIXME: this is temporary, for debugging thor

    def __getstate__(self):
        state = self.__dict__.copy()
        del state['exchange']
        return state

    def __repr__(self):
        status = [self.__class__.__module__ + "." + self.__class__.__name__]
        status.append("'%s'" % self.name)
        return "<%s at %#x>" % (", ".join(status), id(self))

    def add_note(self, subject, note, subreq=None, **kw):
        "Set a note."
        kw['response'] = response_phrase.get(
            self.name, response_phrase['this']
        )
        self.notes.append(note(subject, subreq, kw))

    def preflight(self):
        """
        Check to see if we should bother running. Return True
        if so; False if not. Can be overridden.
        """
        return True

    def check(self):
        """
        Make an asynchronous HTTP request to uri, emitting 'status' as it's
        updated and 'done' when it's done. Reason is used to explain what the
        request is in the status callback.
        """
        self._st.append('check')
        if not self.preflight() or self.request.uri == None:
            # generally a good sign that we're not going much further.
            self.emit("fetch_done")
            return

        if self.follow_robots_txt:
            self.fetch_robots_txt(self.request.uri, self.run_continue)
        else:
            self.run_continue("")

    def fetch_robots_txt(self, url, cb, network=True):
        """
        Fetch the robots.txt URL and then feed the response to cb.
        If the status code is not 200, send a blank doc back.

        If network is False, we won't use the network, will return the result
        immediately if cached, and will assume it's OK if we don't have a
        cached file.
        """

        origin = url_to_origin(self.request.uri)
        if origin == None:
            cb("")
            return ""
        origin_hash = hashlib.sha1(origin).hexdigest()

        if self.robot_files.has_key(origin):
            # FIXME: freshness lifetime
            cb(self.robot_files[origin])
            return self.robot_files[origin]

        if self.robot_cache_dir:
            robot_fd = CacheFile(path.join(self.robot_cache_dir, origin_hash))
            cached_robots_txt = robot_fd.read()
            if cached_robots_txt != None:
                cb(cached_robots_txt)
                return cached_robots_txt

        if not network:
            cb("")
            return ""

        if self.robot_lookups.has_key(origin):
            self.robot_lookups[origin].append(cb)
        else:
            self.robot_lookups[origin] = [cb]
            exchange = self.client.exchange()
            @thor.on(exchange)
            def response_start(status, phrase, headers):
                exchange.status = status

            exchange.res_body = ""
            @thor.on(exchange)
            def response_body(chunk):
                exchange.res_body += chunk

            @thor.on(exchange)
            def response_done(trailers):
                if not exchange.status.startswith("2"):
                    robots_txt = ""
                else:
                    robots_txt = exchange.res_body

                self.robot_files[origin] = robots_txt
                if self.robot_cache_dir:
                    robot_fd = CacheFile(path.join(self.robot_cache_dir, origin_hash))
                    robot_fd.write(robots_txt, 60*30)

                for _cb in self.robot_lookups[origin]:
                    _cb(robots_txt)
                del self.robot_lookups[origin]

            p_url = urlsplit(url)
            robots_url = "%s://%s/robots.txt" % (p_url.scheme, p_url.netloc)
            exchange.request_start("GET", robots_url, [('User-Agent', UA_STRING)])
            exchange.request_done([])

    def run_continue(self, robots_txt):
        """
        Continue after getting the robots file.
        TODO: refactor callback style into events.
        """
        if robots_txt == "": # empty or non-200
            pass
        else:
            checker = RobotFileParser()
            checker.parse(
                robots_txt.decode('ascii', 'replace').encode('ascii', 'replace').splitlines())
            if not checker.can_fetch(UA_STRING, self.request.uri):
                self.response.http_error = RobotsTxtError()
                self.emit("fetch_done")
                return # TODO: show error?

        if 'user-agent' not in [i[0].lower() for i in self.request.headers]:
            self.request.headers.append(
                (u"User-Agent", UA_STRING))
        self.exchange = self.client.exchange()
        self.exchange.on('response_start', self._response_start)
        self.exchange.on('response_body', self._response_body)
        self.exchange.on('response_done', self._response_done)
        self.exchange.on('error', self._response_error)
        self.emit("status", "fetching %s (%s)" % (self.request.uri, self.name))
        req_hdrs = [
            (k.encode('ascii', 'replace'), v.encode('latin-1', 'replace')) \
            for (k, v) in self.request.headers
        ]
        self.exchange.request_start(
            self.request.method, self.request.uri, req_hdrs
        )
        self.request.start_time = thor.time()
        if self.request.payload != None:
            self.exchange.request_body(self.request.payload)
            self.transfer_out += len(self.request.payload)
        self.exchange.request_done([])

    def _response_start(self, status, phrase, res_headers):
        "Process the response start-line and headers."
        self._st.append('_response_start(%s, %s)' % (status, phrase))
        self.response.start_time = thor.time()
        self.response.version = self.exchange.res_version
        self.response.status_code = status.decode('iso-8859-1', 'replace')
        self.response.status_phrase = phrase.decode('iso-8859-1', 'replace')
        self.response.set_headers(res_headers)
        StatusChecker(self.response, self.request)
        checkCaching(self.response, self.request)

    def _response_body(self, chunk):
        "Process a chunk of the response body."
        self.transfer_in += len(chunk)
        self.response.feed_body(chunk)

    def _response_done(self, trailers):
        "Finish analysing the response, handling any parse errors."
        self._st.append('_response_done()')
        self.response.complete_time = thor.time()
        self.response.transfer_length = self.exchange.input_transfer_length
        self.response.header_length = self.exchange.input_header_length
        self.response.body_done(True, trailers)
        self.emit("status", "fetched %s (%s)" % (self.request.uri, self.name))
        self.emit("fetch_done")

    def _response_error(self, error):
        "Handle an error encountered while fetching the response."
        self._st.append('_response_error(%s)' % (str(error)))
        self.emit("status", "fetch error %s (%s)" % (self.request.uri, self.name))
        self.response.complete_time = thor.time()
        self.response.http_error = error
        if isinstance(error, httperr.BodyForbiddenError):
            self.add_note('header-none', BODY_NOT_ALLOWED)
#        elif isinstance(error, httperr.ExtraDataErr):
#            res.payload_len += len(err.get('detail', ''))
        elif isinstance(error, httperr.ChunkError):
            err_msg = error.detail[:20] or ""
            self.add_note('header-transfer-encoding', BAD_CHUNK,
                          chunk_sample=err_msg.encode('string_escape'))
        self.emit("fetch_done")


def url_to_origin(url):
    "Convert an URL to an RFC6454 Origin."
    default_port = {
        'http': 80,
        'https': 443}
    try:
        p_url = urlsplit(url)
        origin = "%s://%s:%s" % (p_url.scheme.lower(),
                                 p_url.hostname.lower(),
                                 p_url.port or default_port.get(p_url.scheme, 0))
    except (AttributeError, ValueError):
        origin = None
    return origin


class RobotsTxtError(httperr.HttpError):
    desc = "Forbidden by robots.txt"
    server_status = ("502", "Gateway Error")


class BODY_NOT_ALLOWED(Note):
    category = categories.CONNECTION
    level = levels.BAD
    summary = u"%(response)s is not allowed to have a body."
    text = u"""\
HTTP defines a few special situations where a response does not allow a body. This includes 101,
204 and 304 responses, as well as responses to the `HEAD` method.

%(response)s had a body, despite it being disallowed. Clients receiving it may treat the body as
the next response in the connection, leading to interoperability and security issues."""

class BAD_CHUNK(Note):
    category = categories.CONNECTION
    level = levels.BAD
    summary = u"%(response)s had chunked encoding errors."
    text = u"""\
The response indicates it uses HTTP chunked encoding, but there was a problem decoding the
chunking.

A valid chunk looks something like this:

`[chunk-size in hex]\\r\\n[chunk-data]\\r\\n`

However, the chunk sent started like this:

`%(chunk_sample)s`

This is a serious problem, because HTTP uses chunking to delimit one response from the next one;
incorrect chunking can lead to interoperability and security problems.

This issue is often caused by sending an integer chunk size instead of one in hex, or by sending
`Transfer-Encoding: chunked` without actually chunking the response body."""




if __name__ == "__main__":
    import sys
    T = RedFetcher(
        sys.argv[1],
        req_hdrs=[(u'Accept-Encoding', u'gzip')],
        name='test'
    )
    @thor.events.on(T)
    def fetch_done():
        print 'done'
        thor.stop()
    @thor.events.on(T)
    def status(msg):
        print msg    
    T.check()
    thor.run()
