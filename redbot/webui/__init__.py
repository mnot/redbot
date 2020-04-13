#!/usr/bin/env python

"""
A Web UI for RED, the Resource Expert Droid.
"""

from collections import defaultdict
from configparser import SectionProxy
import hmac
import json
import os
import secrets
import string
import sys
import time
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Tuple,
    Union,
)  # pylint: disable=unused-import
from urllib.parse import parse_qs, urlsplit, urlencode

import thor
import thor.http.common
from thor.http import get_header
from redbot import __version__
from redbot.message import HttpRequest
from redbot.webui.captcha import handle_captcha
from redbot.webui.ratelimit import ratelimiter, RateLimitViolation
from redbot.webui.saved_tests import (
    init_save_file,
    save_test,
    extend_saved_test,
    load_saved_test,
)
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
        self.query_string = parse_qs(
            query_string.decode(self.config["charset"], "replace")
        )
        self.test_uri = self.query_string.get("uri", [""])[0]
        self.req_hdrs = [
            tuple(h.split(":", 1))  # type: ignore
            for h in self.query_string.get("req_hdr", [])
            if h.find(":") > 0
        ]
        self.format = self.query_string.get("format", ["html"])[0]
        self.descend = "descend" in self.query_string
        if not self.descend:
            self.check_name = self.query_string.get("check_name", [None])[0]
        self.test_id = self.query_string.get("id", [None])[0]
        self.robot_time = self.query_string.get("robot_time", [None])[0]
        self.robot_hmac = self.query_string.get("robot_hmac", [None])[0]
        self.start = time.time()
        if self.method == "POST":
            if (
                "save" in self.query_string
                and self.config.get("save_dir", "")
                and self.test_id
            ):
                extend_saved_test(self)
            elif "slack" in self.query_string:
                self.run_slack()
            elif "client_error" in self.query_string:
                self.dump_client_error()
        elif self.method in ["GET", "HEAD"]:
            if self.test_id:
                load_saved_test(self)
            elif self.test_uri:
                self.run_test()
            else:
                self.show_default()

    def run_test(self) -> None:
        """Test a URI."""
        self.test_id = init_save_file(self)
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

        # hCaptcha
        if self.config.get("hcaptcha_sitekey", "") and self.config.get(
            "hcaptcha_secret", ""
        ):
            presented_token = self.query_string.get("hCaptcha_token", [None])[0]
            handle_captcha(self, top_resource, formatter, presented_token, client_id)
        else:

            # check robots.txt
            robot_fetcher = RobotFetcher(self.config)
            if self.config.getboolean("robots_check"):

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
            else:
                self.continue_test(top_resource, formatter)

    def continue_test(self, top_resource: HttpResource, formatter: Formatter) -> None:
        "Preliminary checks are done; actually run the test."

        @thor.events.on(formatter)
        def formatter_done() -> None:
            self.response_done([])
            save_test(self, top_resource)

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
                    f"{ti / 1024}K in {to / 1024}K out for <{e_url(self.test_uri)}> (descend {self.descend})"
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

    def dump_client_error(self) -> None:
        """Dump a client error."""
        body = self.req_body.decode("ascii", "replace")[:255].replace("\n", "")
        body_safe = "".join([x for x in body if x in string.printable])
        self.error_log(f"Client JS -> {body_safe}")

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
            save_test(self, top_resource)

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
            f"v0={hmac.new(slack_signing_secret, sig_basestring, 'sha256').hexdigest()}"
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

    def show_error(self, message: str, to_output: bool = False) -> Union[None, bytes]:
        """
        Display a message. If to_output is True, send it to self.output(); otherwise
        return it as binary
        """
        out = f"<p class='error'>{message}</p>"
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
        self.error_log(f"timeout: <{self.test_uri}> descend={self.descend}; {detail()}")
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
