"""
Client error handler for REDbot Web UI.

This module provides a handler for logging client-side JavaScript errors.
"""

import string
from typing import TYPE_CHECKING

from redbot.webui.handlers.base import RequestHandler
from redbot.type import RedWebUiProtocol

if TYPE_CHECKING:
    from redbot.webui import RedWebUi


class ClientErrorHandler(RequestHandler):
    """
    Handler for logging client-side JavaScript errors.

    This handler responds to POST requests with 'client_error' in the query
    string. It logs the error from the request body and returns a 204 No Content
    response.
    """

    @classmethod
    def can_handle(cls, ui: RedWebUiProtocol) -> bool:
        """
        Determine if this handler should process the request.

        Handles POST requests with 'client_error' in query string.
        """
        return ui.method == "POST" and len(ui.path) > 0 and ui.path[0] == "client_error"

    @classmethod
    def handle(cls, ui: RedWebUiProtocol) -> None:
        """
        Handle the client error by logging it.

        Extracts the error message from the request body, sanitizes it,
        and logs it to the console. Returns a 204 No Content response.
        """
        # Extract and sanitize the error message
        body = ui.req_body.decode("ascii", "replace")[:255].replace("\n", "")
        body_safe = "".join([x for x in body if x in string.printable])

        # Log the error
        ui.error_log(f"Client JS -> {body_safe}")

        # Return 204 No Content
        ui.exchange.response_start(
            b"204",
            b"No Content",
            [],
        )
        ui.exchange.response_done([])

    @classmethod
    def render_link(
        cls, ui: RedWebUiProtocol, absolute: bool = False, **kwargs: str
    ) -> str:
        """
        Generate a URI for reporting client errors.

        Args:
            ui: The WebUI instance
            absolute: If True, return absolute URI
            **kwargs: Not used for this handler

        Returns:
            URI for the client error endpoint
        """
        return f"{cls.get_base_uri(ui, absolute)}client_error"

    @classmethod
    def render_form(cls, ui: RedWebUiProtocol, **kwargs: str) -> str:
        """
        Client error reporting doesn't use forms.

        Returns:
            Empty string (no form needed)
        """
        return ""
