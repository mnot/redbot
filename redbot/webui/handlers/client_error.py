"""
Client error handler for REDbot Web UI.

This module provides a handler for logging client-side JavaScript errors.
"""

import string
from typing import TYPE_CHECKING

from redbot.webui.handlers.base import RequestHandler

if TYPE_CHECKING:
    from redbot.webui import RedWebUi


class ClientErrorHandler(RequestHandler):
    """
    Handler for logging client-side JavaScript errors.

    This handler responds to POST requests with 'client_error' in the query
    string. It logs the error from the request body and returns a 204 No Content
    response.
    """

    def can_handle(self) -> bool:
        """
        Determine if this handler should process the request.

        Handles POST requests with 'client_error' in query string.
        """
        return (
            self.ui.method == "POST"
            and len(self.ui.path) > 0
            and self.ui.path[0] == "client_error"
        )

    def handle(self) -> None:
        """
        Handle the client error by logging it.

        Extracts the error message from the request body, sanitizes it,
        and logs it to the console. Returns a 204 No Content response.
        """
        # Extract and sanitize the error message
        body = self.ui.req_body.decode("ascii", "replace")[:255].replace("\n", "")
        body_safe = "".join([x for x in body if x in string.printable])

        # Log the error
        self.ui.error_log(f"Client JS -> {body_safe}")

        # Return 204 No Content
        self.ui.exchange.response_start(
            b"204",
            b"No Content",
            [],
        )
        self.ui.exchange.response_done([])

    def render_link(self, absolute: bool = False, **kwargs: str) -> str:
        """
        Generate a URI for reporting client errors.

        Args:
            absolute: If True, return absolute URI
            **kwargs: Not used for this handler

        Returns:
            URI for the client error endpoint
        """
        return f"{self.get_base_uri(absolute)}client_error"

    def render_form(self, **kwargs: str) -> str:
        """
        Client error reporting doesn't use forms.

        Returns:
            Empty string (no form needed)
        """
        return ""
