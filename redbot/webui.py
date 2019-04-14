#!/usr/bin/env python

"""
A Web UI for RED, the Resource Expert Droid.
"""

from collections import defaultdict
from configparser import SectionProxy
import gzip
import hmac
import os
import pickle
import secrets
import sys
import tempfile
import time
from typing import Any, Callable, Dict, List, Tuple, Union # pylint: disable=unused-import
from urllib.parse import parse_qs, urlsplit
import zlib

import thor
from redbot import __version__
from redbot.message import HttpRequest
from redbot.resource import HttpResource
from redbot.resource.robot_fetch import RobotFetcher, url_to_origin
from redbot.formatter import find_formatter, html, Formatter
from redbot.formatter.html import e_url
from redbot.type import RawHeaderListType, StrHeaderListType # pylint: disable=unused-import


class RedWebUi:
    """
    A Web UI for RED.

    Given a URI, run REDbot on it and present the results to output as HTML.
    If descend is true, spider the links and present a summary.
    """

    _origin_counts = defaultdict(int)       # type: Dict[str, int]
    _origin_period = None                   # type: float
    _robot_secret = secrets.token_bytes(16) # type: bytes
    # TODO: make it work for CGI; persist?


    def __init__(self, config: SectionProxy, method: str, query_string: bytes,
                 response_start: Callable[..., None],
                 response_body: Callable[..., None],
                 response_done: Callable[..., None],
                 error_log: Callable[[str], int] = sys.stderr.write) -> None:
        self.config = config  # type: SectionProxy
        self.charset_bytes = self.config['charset'].encode('ascii')
        self.method = method   # Request method to the UX; bytes
        self.response_start = response_start
        self.response_body = response_body
        self._response_done = response_done
        self.error_log = error_log  # function to log errors to
        self.test_uri = None   # type: str
        self.test_id = None    # type: str
        self.robot_time = None # type: str
        self.robot_hmac = None # type: str
        self.req_hdrs = None   # type: StrHeaderListType
        self.format = None     # type: str
        self.check_name = None # type: str
        self.descend = None    # type: bool
        self.save = None       # type: bool
        self.save_path = None  # type: str
        self.timeout = None    # type: Any
        self.referer_spam_domains = [] # type: List[str]
        if config.get("limit_origin_tests", ""):
            if self._origin_period is None:
                self._origin_period = config.getfloat("limit_origin_period", fallback=1) * 3600
                thor.schedule(self._origin_period, self.ratelimit_cleanup)

        if config.get("referer_spam_domains", ""):
            self.referer_spam_domains = [i.strip() for i in \
                config["referer_spam_domains"].split()]

        self.run(query_string)

    def run(self, query_string: bytes) -> None:
        """Given a bytes query_string from the wire, set attributes."""
        qs = parse_qs(query_string.decode(self.config['charset'], 'replace'))
        self.test_uri = qs.get('uri', [''])[0]
        self.req_hdrs = [tuple(h.split(":", 1)) # type: ignore
                         for h in qs.get("req_hdr", []) if h.find(":") > 0]
        self.format = qs.get('format', ['html'])[0]
        self.descend = 'descend' in qs
        if not self.descend:
            self.check_name = qs.get('check_name', [None])[0]
        self.test_id = qs.get('id', [None])[0]
        self.robot_time = qs.get('robot_time', [None])[0]
        self.robot_hmac = qs.get('robot_hmac', [None])[0]
        if self.method == "POST":
            self.save = 'save' in qs
        else:
            self.save = False
        self.start = time.time()
        if self.save and self.config.get('save_dir', "") and self.test_id:
            self.save_test()
        elif self.test_id:
            self.load_saved_test()
        elif self.test_uri:
            self.run_test()
        else:
            self.show_default()

    def save_test(self) -> None:
        """Save a previously run test_id."""
        try:
            # touch the save file so it isn't deleted.
            os.utime(os.path.join(self.config['save_dir'], self.test_id), (
                thor.time(), thor.time() + (int(self.config['save_days']) * 24 * 60 * 60)))
            location = "?id=%s" % self.test_id
            if self.descend:
                location = "%s&descend=True" % location
            self.response_start("303", "See Other", [("Location", location)])
            self.response_body(
                "Redirecting to the saved test page...".encode(self.config['charset']))
        except (OSError, IOError):
            self.response_start(b"500", b"Internal Server Error",
                                [(b"Content-Type", b"text/html; charset=%s" % self.charset_bytes),])
            self.response_body(self.show_error("Sorry, I couldn't save that."))
        self.response_done([])

    def load_saved_test(self) -> None:
        """Load a saved test by test_id."""
        try:
            fd = gzip.open(os.path.join(self.config['save_dir'], os.path.basename(self.test_id)))
            mtime = os.fstat(fd.fileno()).st_mtime
        except (OSError, IOError, TypeError, zlib.error):
            self.response_start(b"404", b"Not Found", [
                (b"Content-Type", b"text/html; charset=%s" % self.charset_bytes),
                (b"Cache-Control", b"max-age=600, must-revalidate")])
            self.response_body(self.show_error("I'm sorry, I can't find that saved response."))
            self.response_done([])
            return
        is_saved = mtime > thor.time()
        try:
            top_resource = pickle.load(fd)
        except (pickle.PickleError, IOError, EOFError):
            self.response_start(b"500", b"Internal Server Error", [
                (b"Content-Type", b"text/html; charset=%s" % self.charset_bytes),
                (b"Cache-Control", b"max-age=600, must-revalidate")])
            self.response_body(self.show_error("I'm sorry, I had a problem loading that."))
            self.response_done([])
            return
        finally:
            fd.close()

        if self.check_name:
            display_resource = top_resource.subreqs.get(self.check_name, top_resource)
        else:
            display_resource = top_resource

        formatter = find_formatter(self.format, 'html', top_resource.descend)(
            self.config, self.output,
            allow_save=(not is_saved), is_saved=True, test_id=self.test_id)

        self.response_start(b"200", b"OK", [
            (b"Content-Type", formatter.content_type()),
            (b"Cache-Control", b"max-age=3600, must-revalidate")])
        @thor.events.on(formatter)
        def formatter_done() -> None:
            self.response_done([])
        formatter.bind_resource(display_resource)

    def run_test(self) -> None:
        """Test a URI."""
        # try to initialise stored test results
        if self.config.get('save_dir', "") and os.path.exists(self.config['save_dir']):
            try:
                fd, self.save_path = tempfile.mkstemp(prefix='', dir=self.config['save_dir'])
                self.test_id = os.path.split(self.save_path)[1]
            except (OSError, IOError):
                # Don't try to store it.
                self.test_id = None # should already be None, but make sure

        top_resource = HttpResource(self.config, descend=self.descend)
        self.timeout = thor.schedule(int(self.config['max_runtime']), self.timeoutError,
                                     top_resource.show_task_map)
        top_resource.set_request(self.test_uri, req_hdrs=self.req_hdrs)
        formatter = find_formatter(self.format, 'html', self.descend)(
            self.config, self.output, allow_save=self.test_id, is_saved=False,
            test_id=self.test_id, descend=self.descend)

        # referer limiting
        referers = []
        for hdr, value in self.req_hdrs:
            if hdr.lower() == 'referer':
                referers.append(value)
        referer_error = None
        if len(referers) > 1:
            referer_error = "Multiple referers not allowed."
        if referers and urlsplit(referers[0]).hostname in self.referer_spam_domains:
            referer_error = "Referer not allowed."
        if referer_error:
            self.response_start(b"403", b"Forbidden", [
                (b"Content-Type", formatter.content_type()),
                (b"Cache-Control", b"max-age=360, must-revalidate")])
            formatter.start_output()
            formatter.error_output(referer_error)
            self.response_done([])
            return

        # robot human check
        if self.robot_time and self.robot_time.isdigit() and self.robot_hmac:
            valid_till = int(self.robot_time)
            computed_hmac = hmac.new(self._robot_secret, bytes(self.robot_time, 'ascii'))
            is_valid = self.robot_hmac == computed_hmac.hexdigest()
            if is_valid and valid_till >= thor.time():
                self.continue_test(top_resource, formatter)
                return
            else:
                self.response_start(b"403", b"Forbidden", [
                    (b"Content-Type", formatter.content_type()),
                    (b"Cache-Control", b"max-age=60, must-revalidate")])
                formatter.start_output()
                formatter.error_output("Naughty.")
                self.response_done([])
                self.error_log("Naughty robot key.")

        # enforce origin limits
        if self.config.getint('limit_origin_tests', fallback=0):
            origin = url_to_origin(self.test_uri)
            if origin:
                if self._origin_counts.get(origin, 0) > \
                  self.config.getint('limit_origin_tests'):
                    self.response_start(b"429", b"Too Many Requests", [
                        (b"Content-Type", formatter.content_type()),
                        (b"Cache-Control", b"max-age=60, must-revalidate")])
                    formatter.start_output()
                    formatter.error_output("Origin is over limit. Please try later.")
                    self.response_done([])
                    self.error_log("origin over limit: %s" % origin)
                    return
                self._origin_counts[origin] += 1

        # check robots.txt
        robot_fetcher = RobotFetcher(self.config)
        @thor.events.on(robot_fetcher)
        def robot(results: Tuple[str, bool]) -> None:
            url, robot_ok = results
            if robot_ok:
                self.continue_test(top_resource, formatter)
            else:
                valid_till = str(int(thor.time()) + 60)
                robot_hmac = hmac.new(self._robot_secret, bytes(valid_till, 'ascii'))
                self.response_start(b"403", b"Forbidden", [
                    (b"Content-Type", formatter.content_type()),
                    (b"Cache-Control", b"no-cache")])
                formatter.start_output()
                formatter.error_output("This site doesn't allow robots. If you are human, please <a href='?uri=%s&robot_time=%s&robot_hmac=%s'>click here</a>." % (self.test_uri, valid_till, robot_hmac.hexdigest()) )
                self.response_done([])

        robot_fetcher.check_robots(HttpRequest.iri_to_uri(self.test_uri))


    def continue_test(self, top_resource: HttpResource, formatter: Formatter) -> None:
        "Preliminary checks are done; actually run the test."
        @thor.events.on(formatter)
        def formatter_done() -> None:
            self.response_done([])
            if self.test_id:
                try:
                    tmp_file = gzip.open(self.save_path, 'w')
                    pickle.dump(top_resource, tmp_file)
                    tmp_file.close()
                except (IOError, zlib.error, pickle.PickleError):
                    pass # we don't cry if we can't store it.

            # log excessive traffic
            ti = sum([i.transfer_in for i, t in top_resource.linked],
                     top_resource.transfer_in)
            to = sum([i.transfer_out for i, t in top_resource.linked],
                     top_resource.transfer_out)
            if ti + to > int(self.config['log_traffic']) * 1024:
                self.error_log("%iK in %iK out for <%s> (descend %s)" % (
                    ti / 1024, to / 1024, e_url(self.test_uri), str(self.descend)))

        self.response_start(b"200", b"OK", [
            (b"Content-Type", formatter.content_type()),
            (b"Cache-Control", b"max-age=60, must-revalidate")])
        if self.check_name:
            display_resource = top_resource.subreqs.get(self.check_name, top_resource)
        else:
            display_resource = top_resource
        formatter.bind_resource(display_resource)
        top_resource.check()


    def show_default(self) -> None:
        """Show the default page."""
        formatter = html.BaseHtmlFormatter(self.config, self.output, is_blank=True)
        self.response_start(b"200", b"OK", [
            (b"Content-Type", formatter.content_type()),
            (b"Cache-Control", b"max-age=300")])
        formatter.start_output()
        formatter.finish_output()
        self.response_done([])

    def show_error(self, message: str, to_output: bool = False) -> Union[None, bytes]:
        """
        Display a message. If to_output is True, send it to self.output(); otherwise
        return it as binary
        """
        out = ("<p class='error'>%s</p>" % message)
        if to_output:
            self.output(out)
            return None
        return out.encode(self.config['charset'], 'replace')

    def output(self, chunk: str) -> None:
        self.response_body(chunk.encode(self.config['charset'], 'replace'))

    def response_done(self, trailers: RawHeaderListType) -> None:
        if self.timeout:
            self.timeout.delete()
            self.timeout = None
        self._response_done(trailers)

    def timeoutError(self, detail: Callable[[], str]) -> None:
        """ Max runtime reached."""
        self.error_log("timeout: <%s> descend=%s; %s" % (
            self.test_uri, self.descend, detail()))
        self.show_error("REDbot timeout.", to_output=True)
        self.response_done([])

    def ratelimit_cleanup(self) -> None:
        """
        Clean up ratelimit counters.
        """
        self._origin_counts.clear()
        thor.schedule(self._origin_period, self.ratelimit_cleanup)



