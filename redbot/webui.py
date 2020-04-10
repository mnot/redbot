#!/usr/bin/env python

"""
A Web UI for RED, the Resource Expert Droid.
"""

from collections import defaultdict
from configparser import SectionProxy
import gzip
import hmac
import json
import os
import pickle
import secrets
import string
import sys
import tempfile
import time
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Tuple,
    Union,
)  # pylint: disable=unused-import
from urllib.parse import parse_qs, urlsplit
import zlib

import thor
import thor.http.common
from thor.http import get_header
from redbot import __version__
from redbot.message import HttpRequest
from redbot.ratelimit import ratelimiter, RateLimitViolation
from redbot.resource import HttpResource
from redbot.resource.robot_fetch import RobotFetcher, url_to_origin
from redbot.formatter import find_formatter, html, slack, Formatter
from redbot.formatter.html_base import e_url
from redbot.type import (
    RawHeaderListType,
    StrHeaderListType,
    HttpResponseExchange,
)  # pylint: disable=unused-import


class RedWebUi:
    """
    A Web UI for RED.

    Given a URI, run REDbot on it and present the results to output as HTML.
    If descend is true, spider the links and present a summary.
    """

    _robot_secret = secrets.token_bytes(16)  # type: bytes

    def __init__(
        self,
        config: SectionProxy,
        method: str,
        query_string: bytes,
        req_headers: RawHeaderListType,
        req_body: bytes,
        exchange: HttpResponseExchange,
        error_log: Callable[[str], int] = sys.stderr.write,
    ) -> None:
        self.config = config  # type: SectionProxy
        self.charset_bytes = self.config["charset"].encode("ascii")
        self.method = method
        self.req_headers = req_headers
        self.req_body = req_body
        self.response_start = exchange.response_start
        self.response_body = exchange.response_body
        self._response_done = exchange.response_done
        self.error_log = error_log  # function to log errors to
        self.test_uri = None  # type: str
        self.test_id = None  # type: str
        self.robot_time = None  # type: str
        self.robot_hmac = None  # type: str
        self.req_hdrs = None  # type: StrHeaderListType
        self.format = None  # type: str
        self.check_name = None  # type: str
        self.descend = None  # type: bool
        self.save = None  # type: bool
        self.save_path = None  # type: str
        self.timeout = None  # type: Any
        self.referer_spam_domains = []  # type: List[str]

        if config.get("limit_client_tests", fallback=""):
            limit = self.config.getint("limit_client_tests")
            period = config.getfloat("limit_client_period", fallback=1) * 3600
            ratelimiter.setup("client_id", limit, period)

        if config.get("limit_origin_tests", fallback=""):
            limit = self.config.getint("limit_origin_tests")
            period = config.getfloat("limit_origin_period", fallback=1) * 3600
            ratelimiter.setup("origin", limit, period)

        if config.get("referer_spam_domains", fallback=""):
            self.referer_spam_domains = [
                i.strip() for i in config["referer_spam_domains"].split()
            ]

        self.run(query_string)

    def run(self, query_string: bytes) -> None:
        """Given a bytes query_string from the wire, set attributes."""
        qs = parse_qs(query_string.decode(self.config["charset"], "replace"))
        self.test_uri = qs.get("uri", [""])[0]
        self.req_hdrs = [
            tuple(h.split(":", 1))  # type: ignore
            for h in qs.get("req_hdr", [])
            if h.find(":") > 0
        ]
        self.format = qs.get("format", ["html"])[0]
        self.descend = "descend" in qs
        if not self.descend:
            self.check_name = qs.get("check_name", [None])[0]
        self.test_id = qs.get("id", [None])[0]
        self.robot_time = qs.get("robot_time", [None])[0]
        self.robot_hmac = qs.get("robot_hmac", [None])[0]
        self.start = time.time()
        if self.method == "POST":
            if "save" in qs and self.config.get("save_dir", "") and self.test_id:
                self.save_test()
            elif "slack" in qs:
                self.run_slack()
            elif "client_error" in qs:
                self.dump_client_error()
        elif self.method in ["GET", "HEAD"]:
            if self.test_id:
                self.load_saved_test()
            elif self.test_uri:
                self.run_test()
            else:
                self.show_default()

    def save_test(self) -> None:
        """Save a previously run test_id."""
        try:
            # touch the save file so it isn't deleted.
            os.utime(
                os.path.join(self.config["save_dir"], self.test_id),
                (
                    thor.time(),
                    thor.time() + (int(self.config["save_days"]) * 24 * 60 * 60),
                ),
            )
            location = b"?id=%s" % self.test_id.encode("ascii")
            if self.descend:
                location = b"%s&descend=True" % location
            self.response_start(b"303", b"See Other", [(b"Location", location)])
            self.response_body(
                "Redirecting to the saved test page...".encode(self.config["charset"])
            )
        except (OSError, IOError):
            self.response_start(
                b"500",
                b"Internal Server Error",
                [(b"Content-Type", b"text/html; charset=%s" % self.charset_bytes)],
            )
            self.response_body(self.show_error("Sorry, I couldn't save that."))
        self.response_done([])

    def load_saved_test(self) -> None:
        """Load a saved test by test_id."""
        try:
            fd = gzip.open(
                os.path.join(self.config["save_dir"], os.path.basename(self.test_id))
            )
            mtime = os.fstat(fd.fileno()).st_mtime
        except (OSError, IOError, TypeError, zlib.error):
            self.response_start(
                b"404",
                b"Not Found",
                [
                    (b"Content-Type", b"text/html; charset=%s" % self.charset_bytes),
                    (b"Cache-Control", b"max-age=600, must-revalidate"),
                ],
            )
            self.response_body(
                self.show_error("I'm sorry, I can't find that saved response.")
            )
            self.response_done([])
            return
        is_saved = mtime > thor.time()
        try:
            top_resource = pickle.load(fd)
        except (pickle.PickleError, IOError, EOFError):
            self.response_start(
                b"500",
                b"Internal Server Error",
                [
                    (b"Content-Type", b"text/html; charset=%s" % self.charset_bytes),
                    (b"Cache-Control", b"max-age=600, must-revalidate"),
                ],
            )
            self.response_body(
                self.show_error("I'm sorry, I had a problem loading that.")
            )
            self.response_done([])
            return
        finally:
            fd.close()

        if self.check_name:
            display_resource = top_resource.subreqs.get(self.check_name, top_resource)
        else:
            display_resource = top_resource

        formatter = find_formatter(self.format, "html", top_resource.descend)(
            self.config,
            self.output,
            allow_save=(not is_saved),
            is_saved=True,
            test_id=self.test_id,
        )

        self.response_start(
            b"200",
            b"OK",
            [
                (b"Content-Type", formatter.content_type()),
                (b"Cache-Control", b"max-age=3600, must-revalidate"),
            ],
        )

        @thor.events.on(formatter)
        def formatter_done() -> None:
            self.response_done([])

        formatter.bind_resource(display_resource)

    def dump_client_error(self) -> None:
        """Dump a client error."""
        body = self.req_body.decode("ascii", "replace")[:255].replace("\n", "")
        body_safe = "".join([x for x in body if x in string.printable])
        self.error_log(f"Client JS -> {body_safe}")

    def run_test(self) -> None:
        """Test a URI."""
        # try to initialise stored test results
        if self.config.get("save_dir", "") and os.path.exists(self.config["save_dir"]):
            try:
                fd, self.save_path = tempfile.mkstemp(
                    prefix="", dir=self.config["save_dir"]
                )
                self.test_id = os.path.split(self.save_path)[1]
            except (OSError, IOError):
                # Don't try to store it.
                self.test_id = None  # should already be None, but make sure

        top_resource = HttpResource(self.config, descend=self.descend)
        self.timeout = thor.schedule(
            int(self.config["max_runtime"]),
            self.timeoutError,
            top_resource.show_task_map,
        )
        top_resource.set_request(self.test_uri, req_hdrs=self.req_hdrs)
        formatter = find_formatter(self.format, "html", self.descend)(
            self.config,
            self.output,
            allow_save=self.test_id,
            is_saved=False,
            test_id=self.test_id,
            descend=self.descend,
        )

        # referer limiting
        referers = []
        for hdr, value in self.req_hdrs:
            if hdr.lower() == "referer":
                referers.append(value)
        referer_error = None
        if len(referers) > 1:
            referer_error = "Multiple referers not allowed."
        if referers and urlsplit(referers[0]).hostname in self.referer_spam_domains:
            referer_error = "Referer not allowed."
        if referer_error:
            return self.error_response(formatter, b"403", b"Forbidden", referer_error)

        # robot human check
        if self.robot_time and self.robot_time.isdigit() and self.robot_hmac:
            valid_till = int(self.robot_time)
            computed_hmac = hmac.new(
                self._robot_secret, bytes(self.robot_time, "ascii"), "sha512"
            )
            is_valid = self.robot_hmac == computed_hmac.hexdigest()
            if is_valid and valid_till >= thor.time():
                self.continue_test(top_resource, formatter)
                return
            else:
                return self.error_response(
                    formatter, b"403", b"Forbidden", "Naughty.", "Naughty robot key."
                )

        # enforce client limits
        client_id = self.get_client_id()
        if client_id:
            try:
                ratelimiter.increment("client_id", client_id)
            except RateLimitViolation:
                return self.error_response(
                    formatter,
                    b"429",
                    b"Too Many Requests",
                    "Your client is over limit. Please try later.",
                    "client over limit: %s" % client_id,
                )

        # enforce origin limits
        origin = url_to_origin(self.test_uri)
        if origin:
            try:
                ratelimiter.increment("origin", origin)
            except RateLimitViolation:
                return self.error_response(
                    formatter,
                    b"429",
                    b"Too Many Requests",
                    "Origin is over limit. Please try later.",
                    "origin over limit: %s" % origin,
                )

        # check robots.txt
        robot_fetcher = RobotFetcher(self.config)

        @thor.events.on(robot_fetcher)
        def robot(results: Tuple[str, bool]) -> None:
            url, robot_ok = results
            if robot_ok:
                self.continue_test(top_resource, formatter)
            else:
                valid_till = str(int(thor.time()) + 60)
                robot_hmac = hmac.new(
                    self._robot_secret, bytes(valid_till, "ascii"), "sha512"
                )
                self.error_response(
                    formatter,
                    b"403",
                    b"Forbidden",
                    f"This site doesn't allow robots. If you are human, please <a href='?uri={self.test_uri}&robot_time={valid_till}&robot_hmac={robot_hmac.hexdigest()}'>click here</a>.",
                )

        robot_fetcher.check_robots(HttpRequest.iri_to_uri(self.test_uri))

    def error_response(
        self,
        formatter: Formatter,
        status_code: bytes,
        status_phrase: bytes,
        message: str,
        log_message: str = None,
    ) -> None:
        """Send an error response."""
        self.response_start(
            status_code,
            status_phrase,
            [
                (b"Content-Type", formatter.content_type()),
                (b"Cache-Control", b"max-age=60, must-revalidate"),
            ],
        )
        formatter.start_output()
        formatter.error_output(message)
        self.response_done([])
        if log_message:
            self.error_log(log_message)

    def continue_test(self, top_resource: HttpResource, formatter: Formatter) -> None:
        "Preliminary checks are done; actually run the test."

        @thor.events.on(formatter)
        def formatter_done() -> None:
            self.response_done([])
            if self.test_id:
                try:
                    tmp_file = gzip.open(self.save_path, "w")
                    pickle.dump(top_resource, tmp_file)
                    tmp_file.close()
                except (IOError, zlib.error, pickle.PickleError):
                    pass  # we don't cry if we can't store it.

            # log excessive traffic
            ti = sum(
                [i.transfer_in for i, t in top_resource.linked],
                top_resource.transfer_in,
            )
            to = sum(
                [i.transfer_out for i, t in top_resource.linked],
                top_resource.transfer_out,
            )
            if ti + to > int(self.config["log_traffic"]) * 1024:
                self.error_log(
                    "%iK in %iK out for <%s> (descend %s)"
                    % (ti / 1024, to / 1024, e_url(self.test_uri), str(self.descend))
                )

        self.response_start(
            b"200",
            b"OK",
            [
                (b"Content-Type", formatter.content_type()),
                (b"Cache-Control", b"max-age=60, must-revalidate"),
            ],
        )
        if self.check_name:
            display_resource = top_resource.subreqs.get(self.check_name, top_resource)
        else:
            display_resource = top_resource
        formatter.bind_resource(display_resource)
        top_resource.check()

    def run_slack(self) -> None:
        """Handle a slack request."""
        body = parse_qs(self.req_body.decode("utf-8"))
        slack_response_uri = body.get("response_url", [""])[0].strip()
        formatter = slack.SlackFormatter(
            self.config, self.output, slack_uri=slack_response_uri
        )
        self.test_uri = body.get("text", [""])[0].strip()

        self.response_start(
            b"200",
            b"OK",
            [
                (b"Content-Type", formatter.content_type()),
                (b"Cache-Control", b"max-age=300"),
            ],
        )
        self.output(
            json.dumps(
                {
                    "response_type": "ephemeral",
                    "text": f"_Checking_ {self.test_uri} _..._",
                }
            )
        )
        self.response_done([])

        top_resource = HttpResource(self.config)
        top_resource.set_request(self.test_uri, req_hdrs=self.req_hdrs)
        formatter.bind_resource(top_resource)
        if not self.verify_slack_secret():
            return self.error_response(
                formatter,
                b"403",
                b"Forbidden",
                "Incorrect Slack Authentication.",
                "Bad slack token.",
            )
        self.timeout = thor.schedule(int(self.config["max_runtime"]), self.timeoutError)

        @thor.events.on(formatter)
        def formatter_done() -> None:
            if self.test_id:
                try:
                    tmp_file = gzip.open(self.save_path, "w")
                    pickle.dump(top_resource, tmp_file)
                    tmp_file.close()
                except (IOError, zlib.error, pickle.PickleError):
                    pass  # we don't cry if we can't store it.

        top_resource.check()

    def verify_slack_secret(self) -> bool:
        """Verify the slack secret."""
        slack_signing_secret = self.config.get(
            "slack_signing_secret", fallback=""
        ).encode("utf-8")
        timestamp = get_header(self.req_headers, b"x-slack-request-timestamp")
        if not timestamp or not timestamp[0].isdigit():
            return False
        timestamp = timestamp[0]
        if abs(thor.time() - int(timestamp)) > 60 * 5:
            return False
        sig_basestring = b"v0:" + timestamp + b":" + self.req_body
        signature = (
            "v0=" + hmac.new(slack_signing_secret, sig_basestring, "sha256").hexdigest()
        )
        presented_signature = get_header(self.req_headers, b"x-slack-signature")
        if not presented_signature:
            return False
        presented_sig = presented_signature[0].decode("utf-8")
        return hmac.compare_digest(signature, presented_sig)

    def show_default(self) -> None:
        """Show the default page."""
        formatter = html.BaseHtmlFormatter(self.config, self.output, is_blank=True)
        self.response_start(
            b"200",
            b"OK",
            [
                (b"Content-Type", formatter.content_type()),
                (b"Cache-Control", b"max-age=300"),
            ],
        )
        formatter.start_output()
        formatter.finish_output()
        self.response_done([])

    def show_error(self, message: str, to_output: bool = False) -> Union[None, bytes]:
        """
        Display a message. If to_output is True, send it to self.output(); otherwise
        return it as binary
        """
        out = "<p class='error'>%s</p>" % message
        if to_output:
            self.output(out)
            return None
        return out.encode(self.config["charset"], "replace")

    def output(self, chunk: str) -> None:
        self.response_body(chunk.encode(self.config["charset"], "replace"))

    def response_done(self, trailers: RawHeaderListType) -> None:
        if self.timeout:
            self.timeout.delete()
            self.timeout = None
        self._response_done(trailers)

    def timeoutError(self, detail: Callable[[], str]) -> None:
        """ Max runtime reached."""
        self.error_log(
            "timeout: <%s> descend=%s; %s" % (self.test_uri, self.descend, detail())
        )
        self.show_error("REDbot timeout.", to_output=True)
        self.response_done([])

    def get_client_id(self) -> str:
        """
        Figure out an identifer for the client.
        """
        xff = thor.http.common.get_header(self.req_headers, b"x-forwarded-for")
        if xff:
            return xff[-1].decode("idna")
        else:
            return thor.http.common.get_header(self.req_headers, b"client-ip")[
                -1
            ].decode("idna")
        return None
