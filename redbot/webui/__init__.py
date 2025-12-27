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
from typing import Optional, Callable, Dict, List, Tuple, Union, cast
from urllib.parse import parse_qs, urlsplit, urlencode

from babel.core import negotiate_locale
import thor
import thor.http.common
from thor.http import get_header

from redbot import __version__
from redbot.i18n import set_locale, AVAILABLE_LOCALES, DEFAULT_LOCALE
from redbot.webui.handlers import (
    SaveHandler,
    LoadSavedTestHandler,
    ClientErrorHandler,
    RunTestHandler,
    ShowHandler,
    ErrorHandler,
)
from redbot.webui.saved_tests import init_save_file, save_test
from redbot.resource import HttpResource
from redbot.formatter import find_formatter, Formatter
from redbot.type import (
    RawHeaderListType,
    StrHeaderListType,
    HttpResponseExchange,
    LinkGenerator,
)
from redbot.webui.links import WebUiLinkGenerator

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
        path: bytes,
        query_string: bytes,
        req_headers: RawHeaderListType,
        req_body: bytes,
        exchange: HttpResponseExchange,
        client_ip: str,
        console: Callable[[str], Optional[int]] = sys.stderr.write,
    ) -> None:
        self.config: SectionProxy = config
        self.method = method
        self.charset = self.config.get("charset", "utf-8")
        self.charset_bytes = self.charset.encode("ascii")
        req_path = path.decode(self.charset, "replace")
        self.path = [p for p in req_path.split("/") if p]
        self.query_string = parse_qs(query_string.decode(self.charset, "replace"))
        self.req_headers = req_headers
        self.req_body = req_body
        self.exchange = exchange
        self.client_ip = client_ip
        self.console = console  # function to log errors to

        # stash the remote IP header name
        self.remote_ip_header = (
            self.config.get("remote_ip_header", "").lower().encode("ascii")
        )

        # locale negotiation
        accept_language = get_header(self.req_headers, b"accept-language")
        if accept_language:
            val_list_list = [fline.split(b",") for fline in accept_language]
            val_list = [item for sublist in val_list_list for item in sublist]
            # Ought to be sorted by q-value, but we don't do that.
            al_values = [
                item.strip().split(b";", 1)[0].decode("ascii", "replace")
                for item in val_list
            ]
            self.locale = (
                negotiate_locale(
                    al_values,
                    AVAILABLE_LOCALES,
                    sep="-",
                )
                or DEFAULT_LOCALE
            )
        else:
            self.locale = DEFAULT_LOCALE

        self.save_path: str
        self.timeout: Optional[thor.loop.ScheduledEvent] = None

        self.nonce: str = standard_b64encode(
            getrandbits(128).to_bytes(16, "big")
        ).decode("ascii")
        self.start = time.time()

        self.link_generator: LinkGenerator = WebUiLinkGenerator(self)

        # Dispatch through handler chain
        handlers = [
            SaveHandler(self),
            LoadSavedTestHandler(self),
            ClientErrorHandler(self),
            RunTestHandler(self),
            ShowHandler(self),
            ErrorHandler(self),  # Final fallback for 404/405
        ]

        for handler in handlers:
            if handler.can_handle():
                handler.handle()
                break

    def error_response(
        self,
        status_code: bytes,
        status_phrase: bytes,
        message: str,
        log_message: Optional[str] = None,
    ) -> None:
        """Send an error response."""
        # Create formatter for error display
        formatter = find_formatter("html")(
            self.config,
            HttpResource(self.config),
            self.output,
            {"nonce": self.nonce},
        )

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
                (b"Content-Language", self.locale.encode("ascii")),
                (b"Vary", b"Accept-Language"),
            ],
        )
        with set_locale(self.locale):
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
        self, formatter: Formatter, detail: Optional[Callable[[], str]] = None
    ) -> None:
        """Max runtime reached."""
        details = ""
        if detail:
            details = f"detail={detail()}"
        self.error_log(f"timeout <{formatter.resource.request.uri}> {details}")
        formatter.resource.stop()
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
