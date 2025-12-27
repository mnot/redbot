"""
Run test handler for REDbot Web UI.

This module provides a handler for executing HTTP resource tests.
"""

from functools import partial, update_wrapper
from typing import TYPE_CHECKING, List, Optional, cast, Any, Tuple
from urllib.parse import urlsplit, urlencode

import thor
import thor.events
from markupsafe import escape

from redbot.resource import HttpResource
from redbot.type import RawHeaderListType, StrHeaderListType
from redbot.webui.captcha import CaptchaHandler
from redbot.webui.handlers.base import RequestHandler
from redbot.webui.ratelimit import ratelimiter
from redbot.webui.saved_tests import init_save_file, save_test
from redbot.formatter import find_formatter
from redbot.formatter.html_base import e_url
from redbot.resource.active_check import active_checks

if TYPE_CHECKING:
    from redbot.webui import RedWebUi
    from redbot.formatter import Formatter


class RunTestHandler(RequestHandler):
    """
    Handler for executing HTTP resource tests.

    This handler responds to POST requests with 'uri' in the query string.
    It performs validation (referer checks, rate limiting, captcha), then
    executes the HTTP test and streams the results.
    """

    def can_handle(self) -> bool:
        """
        Determine if this handler should process the request.

        Handles POST requests with 'uri' in query string.
        """
        return self.ui.method == "POST" and "uri" in self.ui.query_string

    def handle(self) -> None:
        """
        Handle the test execution request.

        Performs validation, creates the resource and formatter,
        then executes the test with proper rate limiting and captcha checks.
        """
        test_id = init_save_file(self.ui)
        test_uri = self.ui.query_string.get("uri", [""])[0]
        test_req_hdrs: StrHeaderListType = [
            cast(Tuple[str, str], tuple(h.split(":", 1)))
            for h in self.ui.query_string.get("req_hdr", [])
            if ":" in h
        ]
        descend = "descend" in self.ui.query_string

        top_resource = HttpResource(self.ui.config, descend=descend)
        top_resource.set_request(test_uri, headers=test_req_hdrs)
        format_ = self.ui.query_string.get("format", ["html"])[0]

        check_name = self.ui.query_string.get("check_name", [""])[0]

        check_title = check_name
        for check in active_checks:
            if getattr(check, "check_id", None) == check_name:
                check_title = getattr(check, "check_name", check_name)
                break

        formatter = find_formatter(format_, "html", descend)(
            self.ui.config,
            top_resource,
            self.ui.output,
            {
                "allow_save": test_id,
                "is_saved": False,
                "test_id": test_id,
                "descend": descend,
                "nonce": self.ui.nonce,
                "locale": self.ui.locale,
                "link_generator": self.ui.link_generator,
                "check_name": check_title or check_name,
            },
        )
        continue_test = partial(self._continue_test, top_resource, formatter)
        timeout_error = partial(self.ui.timeout_error, formatter)
        update_wrapper(timeout_error, self.ui.timeout_error)

        self.ui.timeout = thor.schedule(
            int(self.ui.config.get("max_runtime", "60")),
            timeout_error,
            top_resource.show_task_map,
        )

        # referer limiting
        referers = []
        for hdr, value in test_req_hdrs:
            if hdr.lower() == "referer":
                referers.append(value)
        referer_error = None

        if len(referers) > 1:
            referer_error = "Multiple referers not allowed."

        config_spam_domains = self.ui.config.get("referer_spam_domains") or ""
        referer_spam_domains = [i.strip() for i in config_spam_domains.split()]
        if (
            referer_spam_domains
            and referers
            and urlsplit(referers[0]).hostname in referer_spam_domains
        ):
            referer_error = "Referer not allowed."

        if referer_error:
            self.ui.error_response(b"403", b"Forbidden", referer_error)
            return

        # enforce client limits
        try:
            ratelimiter.process(self.ui, test_uri, self.ui.error_response)
        except ValueError:
            return  # over limit, don't continue.

        # Captcha
        captcha = CaptchaHandler(
            self.ui,
            continue_test,
            self.ui.error_response,
        )
        if captcha.configured():
            captcha.run()
        else:
            continue_test()

    def _continue_test(
        self,
        top_resource: HttpResource,
        formatter: "Formatter",
        extra_headers: Optional[RawHeaderListType] = None,
    ) -> None:
        """Preliminary checks are done; actually run the test."""

        if not extra_headers:
            extra_headers = []

        @thor.events.on(formatter)
        def formatter_done() -> None:
            if self.ui.timeout:
                self.ui.timeout.delete()
                self.ui.timeout = None
            self.ui.exchange.response_done([])
            save_test(self.ui, top_resource)

            # log excessive traffic
            log_traffic = self.ui.config.getint("log_traffic", None)
            if log_traffic:
                ti = sum(
                    [i.transfer_in for i, t in top_resource.linked],
                    top_resource.transfer_in,
                )
                to = sum(
                    [i.transfer_out for i, t in top_resource.linked],
                    top_resource.transfer_out,
                )
                if ti + to > log_traffic * 1024:

                    self.ui.error_log(
                        f"{ti / 1024:n}K in "
                        f"{to / 1024:n}K out "
                        f"for <{e_url(str(top_resource.request.uri))}> "
                    )

        # Stop the resource if the client disconnects
        @thor.events.on(cast(thor.events.EventEmitter, self.ui.exchange))
        def close() -> None:
            top_resource.stop()

        self.ui.exchange.response_start(
            b"200",
            b"OK",
            [
                (b"Content-Type", formatter.content_type()),
                (
                    b"Content-Security-Policy",
                    (f"script-src 'strict-dynamic' 'nonce-{self.ui.nonce}'").encode(
                        "ascii"
                    ),
                ),
                (b"Content-Language", self.ui.locale.encode("ascii")),
                (b"Vary", b"Accept-Language"),
            ]
            + extra_headers,
        )
        if "check_name" in self.ui.query_string:
            check_name = self.ui.query_string.get("check_name", [""])[0]
            display_resource = cast(
                HttpResource, top_resource.subreqs.get(check_name, top_resource)
            )
        else:
            display_resource = top_resource
        formatter.bind_resource(display_resource)
        top_resource.check()

    def render_link(self, absolute: bool = False, **kwargs: str) -> str:
        """
        Generate a URI for running a test.

        Args:
            absolute: If True, return absolute URI
            **kwargs: Supported keys:
                - uri (str): URI to test
                - req_hdr (str or list): Request headers as "Name:Value" strings
                - format (str): Output format (default: html)
                - descend (str): "True" to descend into linked resources
                - check_name (str): Specific check to display

        Returns:
            URI for the test endpoint
        """
        base_uri = self.get_base_uri(absolute)
        params = []
        if "uri" in kwargs:
            params.append(("uri", kwargs["uri"]))

        # Handle req_hdr which could be a single value or multiple
        # Note: In the current type signature, req_hdr is a string
        # but this could be extended to support lists in the future
        if "req_hdr" in kwargs:
            params.append(("req_hdr", kwargs["req_hdr"]))

        if kwargs.get("format"):
            params.append(("format", kwargs["format"]))
        if kwargs.get("descend") == "True":
            params.append(("descend", "True"))
        if kwargs.get("check_name"):
            params.append(("check_name", kwargs["check_name"]))

        return f"{base_uri}?{urlencode(params)}"

    def render_form(
        self,
        link_text: str = "Test",
        headers: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> str:
        """
        Generate an HTML form for running a test.

        Args:
            link_text: Text for the submit button
            headers: List of headers as "Name:Value" strings
            **kwargs: Supported keys:
                - uri (str): URI to test
                - format (str): Output format (default: html)
                - descend (str): "True" to descend into linked resources
                - check_name (str): Specific check to display
                - css_class (str): CSS class for the submit button
                - title (str): Title attribute for the submit button

        Returns:
            HTML form string
        """
        base_uri = self.get_base_uri()
        title = kwargs.get("title", "")
        uri = kwargs.get("uri", "")
        css_class = kwargs.get("css_class", "")

        # Build query string for the action URL
        query_params = []
        if kwargs.get("format"):
            query_params.append(("format", kwargs["format"]))
        if kwargs.get("descend") == "True":
            query_params.append(("descend", "True"))
        if kwargs.get("check_name"):
            query_params.append(("check_name", kwargs["check_name"]))

        action = e_url(base_uri)
        if query_params:
            action += "?" + urlencode(query_params)

        # Start building the form
        form_parts = [f'<form class="link" action="{action}" method="POST">']

        # Add URI field
        form_parts.append(f'<input type="hidden" name="uri" value="{escape(uri)}" />')

        # Add all request headers
        if headers:
            for hdr in headers:
                form_parts.append(
                    f'<input type="hidden" name="req_hdr" ' f'value="{escape(hdr)}" />'
                )

        if kwargs.get("format"):
            form_parts.append(
                f'<input type="hidden" name="format" value="{escape(kwargs["format"])}" />'
            )

        if kwargs.get("descend") == "True":
            form_parts.append('<input type="hidden" name="descend" value="True" />')

        if kwargs.get("check_name"):
            form_parts.append(
                f'<input type="hidden" name="check_name" value="{escape(kwargs["check_name"])}" />'
            )

        # Add submit button
        form_parts.append(
            f'<input type="submit" value="{escape(link_text)}" '
            f'class="post_link {css_class}" title="{title}" />'
        )
        form_parts.append("</form>")

        return "".join(form_parts)
