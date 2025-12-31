"""
Request handler abstraction for REDbot Web UI.

This module provides a base class for creating request handlers that encapsulate
three key responsibilities:

1. **Request Dispatch**: Determining if the handler should process a request
2. **Request Handling**: Processing the request and generating a response
3. **Link/Form Generation**: Creating URIs and HTML forms for accessing the handler
"""

from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlparse

from redbot.type import RedWebUiProtocol


class RequestHandler(ABC):
    """
    Abstract base class for REDbot Web UI request handlers.

    A RequestHandler encapsulates three responsibilities:
    1. Determining if it should handle a request (dispatch)
    2. Handling the request and generating a response
    3. Generating URIs and HTML forms for accessing the handler
    """

    def __init__(self, ui: RedWebUiProtocol) -> None:
        self.ui = ui

    def get_base_uri(self, absolute: bool = False) -> str:
        """
        Get the base URI for links.

        If absolute is True, returns the full URI from config.
        Otherwise, returns just the path component.

        The returned string is always terminated by '/'.
        """
        ui_uri = self.ui.config.get("ui_uri", "")
        if not ui_uri.endswith("/"):
            ui_uri += "/"

        if absolute:
            return ui_uri
        return urlparse(ui_uri).path

    @abstractmethod
    def can_handle(self) -> bool:
        """
        Determine if this handler should process the request.

        Called at request dispatch time to determine routing.

        Returns:
            True if this handler should process the request, False otherwise
        """

    @abstractmethod
    def handle(self) -> None:
        """
        Handle the request and generate a response.

        This method is responsible for:
        - Processing the request
        - Generating appropriate response headers and body
        - Calling self.ui.exchange.response_start(), self.ui.output(), and
          self.ui.exchange.response_done()
        """

    @abstractmethod
    def render_link(self, **kwargs: Any) -> str:
        """
        Generate a URI for this handler.

        This method generates a relative URI for the handler, including any
        parameters required. It uses the `ui_uri` from the configuration.

        Args:
            **kwargs: Arguments for the link (handler-specific)

        Returns:
            The generated URI string
        """
        raise NotImplementedError

    def render_form(self, **kwargs: Any) -> str:
        """
        Generate an HTML form for accessing this handler.

        This method is optional and may return an empty string if the handler
        doesn't require or support form-based access. When implemented, it should
        return a complete HTML <form> element.

        Args:
            **kwargs: Handler-specific parameters for the form

        Returns:
            An HTML form string, or empty string if not applicable
        """
        return ""
