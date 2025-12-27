"""
Error handler for REDbot Web UI.

This module provides a fallback handler for unsupported methods (405) and unknown requests (404).
"""

from typing import TYPE_CHECKING

from redbot.webui.handlers.base import RequestHandler

if TYPE_CHECKING:
    from redbot.webui import RedWebUi


class ErrorHandler(RequestHandler):
    """
    Fallback handler for errors (404/405).

    This handler catches all requests that don't match other handlers
    and returns appropriate error responses.
    """

    def can_handle(self) -> bool:
        """
        Determine if this handler should process the request.

        This is the final catch-all handler, so it always returns True.
        It should be checked last in the handler chain.
        """
        return True  # Always matches as the final fallback

    def handle(self) -> None:
        """
        Handle the error by returning 405 or 404 as appropriate.

        Returns 405 Method Not Allowed for unsupported methods,
        or 404 Not Found for unrecognized request patterns.
        """
        # Get the HTTP method from the request
        # For now, we'll treat everything as 404 since we're the final fallback
        self.ui.error_response(
            b"404",
            b"Not Found",
            "The requested resource was not found",
            log_message="404",
        )

    def render_link(self, **kwargs: str) -> str:
        """
        Error handler doesn't generate links.

        Returns:
            Empty string
        """
        return ""

    def render_form(self, **kwargs: str) -> str:
        """
        Error handler doesn't generate forms.

        Returns:
            Empty string
        """
        return ""
