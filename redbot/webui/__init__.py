"""
A Web UI for RED, the Resource Expert Droid.
"""

from base64 import standard_b64encode
from collections import defaultdict
from configparser import SectionProxy
from functools import partial, update_wrapper
import os
from random import getrandbits
import string
import sys
import time
from typing import Any, Callable, Dict, List, Tuple, Union, cast
from urllib.parse import parse_qs, urlsplit, urlencode

import thor
import thor.http.common
from thor.http import get_header
from redbot import __version__
from redbot.webui.captcha import CaptchaHandler
from redbot.webui.ratelimit import ratelimiter
from redbot.webui.saved_tests import (
    init_save_file,
    save_test,
    extend_saved_test,
    load_saved_test,
)
from redbot.webui.slack import slack_run, slack_auth
from redbot.resource import HttpResource
from redbot.formatter import find_formatter, html, Formatter
from redbot.formatter.html_base import e_url
from redbot.type import (
    RawHeaderListType,
    StrHeaderListType,
    HttpResponseExchange,
)

CSP = "script-src"


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
        client_ip: str,
        console: Callable[[str], int] = sys.stderr.write,
    ) -> None:
        self.config: SectionProxy = config
        self.charset = self.config["charset"]
        self.charset_bytes = self.charset.encode("ascii")
        self.query_string = parse_qs(query_string.decode(self.charset, "replace"))
        self.req_headers = req_headers
        self.req_body = req_body
        self.body_args = {}
        self.exchange = exchange
        self.client_ip = client_ip
        self.console = console  # function to log errors to

        # stash the remote IP header name
        self.remote_ip_header = (
            self.config.get("remote_ip_header", "").lower().encode("ascii")
        )

        # query processing
        self.test_uri = self.query_string.get("uri", [""])[0]
        self.test_id = self.query_string.get("id", [None])[0]
        self.req_hdrs: StrHeaderListType = [
            tuple(h.split(":", 1))  # type: ignore
            for h in self.query_string.get("req_hdr", [])
            if ":" in h
        ]
        self.format = self.query_string.get("format", ["html"])[0]
        self.descend = "descend" in self.query_string
        self.check_name: str = None
        if not self.descend:
            self.check_name = self.query_string.get("check_name", [None])[0]

        self.save_path: str = None
        self.timeout: Any = None

        self.nonce: str = standard_b64encode(
            getrandbits(128).to_bytes(16, "big")
        ).decode("ascii")
        self.start = time.time()

        if method == "POST":
            req_ct = get_header(self.req_headers, b"content-type")
            if req_ct and req_ct[-1].lower() == b"application/x-www-form-urlencoded":
                self.body_args = parse_qs(req_body.decode(self.charset, "replace"))

            if (
                "save" in self.query_string
                and self.config.get("save_dir", "")
                and self.test_id
            ):
                extend_saved_test(self)
            elif "slack" in self.query_string:
                slack_run(self)
            elif "client_error" in self.query_string:
                self.dump_client_error()
            elif self.test_uri:
                self.run_test()
            else:
                self.show_default()
        elif method in ["GET", "HEAD"]:
            if self.test_id:
                load_saved_test(self)
            elif "code" in self.query_string:
                slack_auth(self)
            else:
                self.show_default()
        else:
            self.error_response(
                find_formatter("html")(
                    self.config, None, self.output, nonce=self.nonce
                ),
                b"405",
                b"Method Not Allowed",
                "Method Not Allowed",
            )

    def run_test(self) -> None:
        """Test a URI."""
        self.test_id = init_save_file(self)
        top_resource = HttpResource(self.config, descend=self.descend)
        top_resource.set_request(self.test_uri, headers=self.req_hdrs)
        formatter = find_formatter(self.format, "html", self.descend)(
            self.config,
            top_resource,
            self.output,
            allow_save=self.test_id,
            is_saved=False,
            test_id=self.test_id,
            descend=self.descend,
            nonce=self.nonce,
        )
        continue_test = partial(self.continue_test, top_resource, formatter)
        error_response = partial(self.error_response, formatter)
        timeout_error = partial(self.timeout_error, formatter)
        update_wrapper(timeout_error, self.timeout_error)

        self.timeout = thor.schedule(
            int(self.config["max_runtime"]),
            timeout_error,
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

        # Captcha
        captcha = CaptchaHandler(
            self,
            continue_test,
            error_response,
        )
        if captcha.configured():
            captcha.run()
        else:
            continue_test()

    def continue_test(
        self,
        top_resource: HttpResource,
        formatter: Formatter,
        extra_headers: RawHeaderListType = None,
    ) -> None:
        "Preliminary checks are done; actually run the test."

        if not extra_headers:
            extra_headers = []

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
                    f"{ti / 1024:n}K in "
                    f"{to / 1024:n}K out "
                    f"for <{e_url(self.test_uri)}> "
                    f"(descend {self.descend})"
                )

        self.exchange.response_start(
            b"200",
            b"OK",
            [
                (b"Content-Type", formatter.content_type()),
                (
                    b"Content-Security-Policy",
                    f"{CSP} 'strict-dynamic' 'nonce-{self.nonce}'".encode("ascii"),
                ),
            ]
            + extra_headers,
        )
        if self.check_name:
            display_resource = cast(
                HttpResource, top_resource.subreqs.get(self.check_name, top_resource)
            )
        else:
            display_resource = top_resource
        formatter.bind_resource(display_resource)
        top_resource.check()

    def dump_client_error(self) -> None:
        """Dump a client error."""
        body = self.req_body.decode("ascii", "replace")[:255].replace("\n", "")
        body_safe = "".join([x for x in body if x in string.printable])
        self.error_log(f"Client JS -> {body_safe}")
        self.exchange.response_start(
            b"204",
            b"No Content",
            [],
        )
        self.exchange.response_done([])

    def show_default(self) -> None:
        """Show the default page."""
        formatter = html.BaseHtmlFormatter(
            self.config,
            None,
            self.output,
            is_blank=self.test_uri == "",
            nonce=self.nonce,
        )
        if self.test_uri:
            top_resource = HttpResource(self.config, descend=self.descend)
            top_resource.set_request(self.test_uri, headers=self.req_hdrs)
            if self.check_name:
                formatter.resource = cast(
                    HttpResource,
                    top_resource.subreqs.get(self.check_name, top_resource),
                )
            else:
                formatter.resource = top_resource
        self.exchange.response_start(
            b"200",
            b"OK",
            [
                (b"Content-Type", formatter.content_type()),
                (b"Cache-Control", b"max-age=5"),
                (
                    b"Content-Security-Policy",
                    f"{CSP} 'strict-dynamic' 'nonce-{self.nonce}'".encode("ascii"),
                ),
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
        if self.timeout:
            self.timeout.delete()
            self.timeout = None
        self.exchange.response_start(
            status_code,
            status_phrase,
            [
                (b"Content-Type", formatter.content_type()),
                (b"Cache-Control", b"max-age=60, must-revalidate"),
                (
                    b"Content-Security-Policy",
                    f"{CSP} 'strict-dynamic' 'nonce-{self.nonce}'".encode("ascii"),
                ),
            ],
        )
        formatter.start_output()
        formatter.error_output(message)
        self.exchange.response_done([])
        if log_message:
            self.error_log(log_message)

    def output(self, chunk: str) -> None:
        self.exchange.response_body(chunk.encode(self.charset, "replace"))

    def error_log(self, message: str) -> None:
        self.console(f"{self.get_client_ip()}: {message}")

    def timeout_error(
        self, formatter: Formatter, detail: Callable[[], str] = None
    ) -> None:
        """Max runtime reached."""
        details = ""
        if detail:
            details = f"detail={detail()}"
        self.error_log(f"timeout <{self.test_uri}> descend={self.descend} {details}")
        formatter.error_output("REDbot timeout.")
        self.exchange.response_done([])

    def get_client_id(self) -> str:
        """
        Return as unique an identifier for the client as possible.
        """
        return self.get_client_ip()

    def get_client_ip(self) -> str:
        """
        Return what we believe to be the client's IP address.
        """
        if self.remote_ip_header:
            remote_ip = thor.http.common.get_header(
                self.req_headers, self.remote_ip_header
            )
            if remote_ip:
                return remote_ip[-1].decode("ascii", errors="replace")
        return self.client_ip
