#!/usr/bin/env python

"""
A Web UI for RED, the Resource Expert Droid.
"""

from collections import defaultdict
from configparser import SectionProxy
from functools import partial
import os
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
from redbot.webui.captcha import CaptchaHandler
from redbot.webui.ratelimit import ratelimiter
from redbot.webui.saved_tests import (
    init_save_file,
    save_test,
    extend_saved_test,
    load_saved_test,
)
from redbot.webui.slack import run_slack
from redbot.resource import HttpResource
from redbot.formatter import find_formatter, html, Formatter
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
        self.query_string = parse_qs(
            query_string.decode(self.config["charset"], "replace")
        )
        self.req_headers = req_headers
        self.req_body = req_body
        self.body_args = {}
        self.exchange = exchange
        self.error_log = error_log  # function to log errors to

        # query processing
        self.test_uri = self.query_string.get("uri", [""])[0]
        self.test_id = self.query_string.get("id", [None])[0]
        self.req_hdrs = [
            tuple(h.split(":", 1))  # type: ignore
            for h in self.query_string.get("req_hdr", [])
            if h.find(":") > 0
        ]  # type: StrHeaderListType
        self.format = self.query_string.get("format", ["html"])[0]
        self.descend = "descend" in self.query_string
        self.check_name = None  # type: str
        if not self.descend:
            self.check_name = self.query_string.get("check_name", [None])[0]

        self.charset_bytes = self.config["charset"].encode("ascii")

        self.save_path = None  # type: str
        self.timeout = None  # type: Any

        self.start = time.time()

        if method == "POST":
            req_ct = get_header(self.req_headers, b"content-type")
            if req_ct and req_ct[-1].lower() == b"application/x-www-form-urlencoded":
                self.body_args = parse_qs(
                    req_body.decode(self.config["charset"], "replace")
                )

            if (
                "save" in self.query_string
                and self.config.get("save_dir", "")
                and self.test_id
            ):
                extend_saved_test(self)
            elif "slack" in self.query_string:
                run_slack(self)
            elif "client_error" in self.query_string:
                self.dump_client_error()
            elif self.test_uri:
                self.run_test()
            else:
                self.show_default()
        elif method in ["GET", "HEAD"]:
            if self.test_id:
                load_saved_test(self)
            else:
                self.show_default()
        else:
            self.error_response(
                find_formatter("html")(self.config, None, self.output),
                b"405",
                b"Method Not Allowed",
                "Method Not Allowed",
            )

    def run_test(self) -> None:
        """Test a URI."""
        self.test_id = init_save_file(self)
        top_resource = HttpResource(self.config, descend=self.descend)
        top_resource.set_request(self.test_uri, req_hdrs=self.req_hdrs)
        formatter = find_formatter(self.format, "html", self.descend)(
            self.config,
            top_resource,
            self.output,
            allow_save=self.test_id,
            is_saved=False,
            test_id=self.test_id,
            descend=self.descend,
        )
        continue_test = partial(self.continue_test, top_resource, formatter)
        error_response = partial(self.error_response, formatter)

        self.timeout = thor.schedule(
            int(self.config["max_runtime"]),
            self.timeoutError,
            top_resource.show_task_map,
        )

        # referer limiting
        referers = []
        for hdr, value in self.req_hdrs:
            if hdr.lower() == "referer":
                referers.append(value)
        referer_error = None

        if len(referers) > 1:
            referer_error = "Multiple referers not allowed."

        referer_spam_domains = [
            i.strip()
            for i in self.config.get("referer_spam_domains", fallback="").split()
        ]
        if (
            referer_spam_domains
            and referers
            and urlsplit(referers[0]).hostname in referer_spam_domains
        ):
            referer_error = "Referer not allowed."

        if referer_error:
            error_response(b"403", b"Forbidden", referer_error)
            return

        # enforce client limits
        try:
            ratelimiter.process(self, error_response)
        except ValueError:
            return  # over limit, don't continue.

        # hCaptcha
        if self.config.get("hcaptcha_sitekey", "") and self.config.get(
            "hcaptcha_secret", ""
        ):
            CaptchaHandler(
                self, self.get_client_id(), continue_test, error_response,
            ).run()
        else:
            continue_test()

    def continue_test(
        self,
        top_resource: HttpResource,
        formatter: Formatter,
        extra_headers: RawHeaderListType = [],
    ) -> None:
        "Preliminary checks are done; actually run the test."

        @thor.events.on(formatter)
        def formatter_done() -> None:
            if self.timeout:
                self.timeout.delete()
                self.timeout = None
            self.exchange.response_done([])
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
                    f"{ti / 1024:n}K in {to / 1024:n}K out for <{e_url(self.test_uri)}> (descend {self.descend})"
                )

        self.exchange.response_start(
            b"200",
            b"OK",
            [
                (b"Content-Type", formatter.content_type()),
                (b"Cache-Control", b"max-age=60, must-revalidate"),
            ]
            + extra_headers,
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

    def show_default(self) -> None:
        """Show the default page."""
        formatter = html.BaseHtmlFormatter(
            self.config, None, self.output, is_blank=self.test_uri == ""
        )
        if self.test_uri:
            top_resource = HttpResource(self.config, descend=self.descend)
            top_resource.set_request(self.test_uri, req_hdrs=self.req_hdrs)
            if self.check_name:
                formatter.resource = top_resource.subreqs.get(
                    self.check_name, top_resource
                )
            else:
                formatter.resource = top_resource
        self.exchange.response_start(
            b"200",
            b"OK",
            [
                (b"Content-Type", formatter.content_type()),
                (b"Cache-Control", b"max-age=300"),
            ],
        )
        formatter.start_output()
        formatter.finish_output()
        self.exchange.response_done([])

    def error_response(
        self,
        formatter: Formatter,
        status_code: bytes,
        status_phrase: bytes,
        message: str,
        log_message: str = None,
    ) -> None:
        """Send an error response."""
        self.exchange.response_start(
            status_code,
            status_phrase,
            [
                (b"Content-Type", formatter.content_type()),
                (b"Cache-Control", b"max-age=60, must-revalidate"),
            ],
        )
        formatter.start_output()
        formatter.error_output(message)
        self.exchange.response_done([])
        if log_message:
            self.error_log(log_message)

    def output(self, chunk: str) -> None:
        self.exchange.response_body(chunk.encode(self.config["charset"], "replace"))

    def timeoutError(self, detail: Callable[[], str] = None) -> None:
        """ Max runtime reached."""
        details = ""
        if detail:
            details = f"detail={detail()}"
        self.error_log(f"timeout: <{self.test_uri}> descend={self.descend} {details}")
        self.output(f"<p class='error'>REDbot timeout.</p>")
        self.exchange.response_done([])

    def get_client_id(self) -> str:
        """
        Figure out an identifer for the client.
        """
        xff = thor.http.common.get_header(self.req_headers, b"x-forwarded-for")
        if xff:
            return xff[-1].decode("idna")
        return thor.http.common.get_header(self.req_headers, b"client-ip")[-1].decode(
            "idna"
        )
