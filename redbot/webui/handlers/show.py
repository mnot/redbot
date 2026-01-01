"""
Show handler for REDbot Web UI.

This module provides a handler for the main REDbot interface page.
"""

from typing import TYPE_CHECKING, cast, Any, Tuple
from urllib.parse import urlencode

from redbot.i18n import set_locale
from redbot.resource import HttpResource
from redbot.type import StrHeaderListType, RedWebUiProtocol
from redbot.webui.handlers.base import RequestHandler
from redbot.formatter import html

if TYPE_CHECKING:
    from redbot.webui import RedWebUi


class ShowHandler(RequestHandler):
    """
    Handler for the main REDbot interface page.

    This handler displays the main REDbot UI with the URI input form.
    It can pre-fill the form with URI and headers from the query string.
    """

    @classmethod
    def can_handle(cls, ui: RedWebUiProtocol) -> bool:
        """
        Determine if this handler should process the request.
        """
        return (
            ui.method in ["GET", "HEAD"]
            and (
                ui.path == []
                or ui.path[0] == "check"
            )
        )

    @classmethod
    def handle(cls, ui: RedWebUiProtocol) -> None:
        """
        Handle the default page request.

        Displays the main REDbot interface with optional pre-filled URI.
        """
        descend = "descend" in ui.query_string
        test_uri = ui.query_string.get("uri", [""])[0]
        test_req_hdrs: StrHeaderListType = [
            cast(Tuple[str, str], tuple(h.split(":", 1)))
            for h in ui.query_string.get("req_hdr", [])
            if ":" in h
        ]

        resource = HttpResource(ui.config, descend=descend)
        if test_uri:
            resource.set_request(test_uri, headers=test_req_hdrs)

        check_name = None
        if "check_name" in ui.query_string:
            check_name = ui.query_string.get("check_name", [""])[0]

        formatter = html.BaseHtmlFormatter(
            ui.config,
            resource,
            ui.output,
            {
                "is_blank": test_uri == "",
                "nonce": ui.nonce,
                "locale": ui.locale,
                "link_generator": ui.link_generator,
                "check_name": check_name,
            },
        )

        if check_name:
            formatter.resource = cast(
                HttpResource,
                resource.subreqs.get(check_name, resource),
            )

        ui.exchange.response_start(
            b"200",
            b"OK",
            [
                (b"Content-Type", formatter.content_type()),
                (b"Cache-Control", b"max-age=5"),
                (
                    b"Content-Security-Policy",
                    f"script-src 'strict-dynamic' 'nonce-{ui.nonce}'".encode(
                        "ascii"
                    ),
                ),
                (b"Content-Language", ui.locale.encode("ascii")),
                (b"Vary", b"Accept-Language"),
            ],
        )

        with set_locale(ui.locale):
            formatter.start_output()
            formatter.finish_output()

        ui.exchange.response_done([])

    @classmethod
    def render_link(
        cls,
        ui: RedWebUiProtocol,
        uri: str = "",
        req_hdr: str = "",
        descend: bool = False,
        check_name: str = "",
        absolute: bool = False,
        **kwargs: Any,
    ) -> str:
        """
        Generate a URI for the main UI page.

        Args:
            ui: The WebUI instance
            uri: URI to pre-fill (optional)
            req_hdr: Request header as "Name:Value" (optional)
            descend: If True, enable descend mode
            check_name: Specific check to display (optional)
            absolute: If True, return absolute URI

        Returns:
            URI for the main UI page
        """
        base_uri = cls.get_base_uri(ui, absolute)
        params = []
        if uri:
            params.append(("uri", uri))
        if req_hdr:
            params.append(("req_hdr", req_hdr))
        if descend:
            params.append(("descend", "True"))
        if check_name:
            params.append(("check_name", check_name))

        if params:
            return f"{base_uri}?{urlencode(params)}"
        return base_uri

    @classmethod
    def render_form(cls, ui: RedWebUiProtocol, **kwargs: str) -> str:
        """
        The default page itself is the form interface.

        Returns:
            Empty string (the page itself contains the form)
        """
        return ""

class RedirectHandler(RequestHandler):
    """
    Handler for redirecting legacy bookmarklets.
    
    This handler responds to GET/HEAD requests with 'uri' in the query string
    at the root path, redirecting them to the check handler.
    """

    @classmethod
    def can_handle(cls, ui: RedWebUiProtocol) -> bool:
        """
        Determine if this handler should process the request.
        """
        return (
            ui.method in ["GET", "HEAD"]
            and ui.path == []
            and "uri" in ui.query_string
        )

    @classmethod
    def handle(cls, ui: RedWebUiProtocol) -> None:
        """
        Handle the redirect request.
        """
        base_uri = cls.get_base_uri(ui)
        uri = ui.query_string.get("uri", [""])[0]
        params = [("uri", uri)]
        location = f"{base_uri}check?{urlencode(params)}"

        ui.exchange.response_start(
            b"303", b"See Other", [(b"Location", location.encode("ascii"))]
        )
        ui.output("Redirecting to the validation page...")
        ui.exchange.response_done([])

    @classmethod
    def render_link(cls, ui: RedWebUiProtocol, **kwargs: Any) -> str:
        """
        No link generation needed.
        """
        return ""
