"""
Save handler for REDbot Web UI.

This module provides a handler for extending the expiry time of saved test results.
"""

import gzip
import os
import pickle
import time
import zlib
from typing import TYPE_CHECKING, cast, IO, Any
from urllib.parse import urlencode

from markupsafe import escape
import thor.events

from redbot.webui.handlers.base import RequestHandler
from redbot.formatter import find_formatter

if TYPE_CHECKING:
    from redbot.webui import RedWebUi


class SaveHandler(RequestHandler):
    """
    Handler for extending the expiry time of saved test results.

    This handler responds to POST requests with 'save' and 'id' parameters
    in the query string. It updates the modification time of the saved test
    file to extend its expiry, then redirects to the saved test page.
    """

    def can_handle(self) -> bool:
        """
        Determine if this handler should process the request.

        Handles POST requests with 'save' and 'id' in query string.
        """
        return (
            self.ui.method == "POST"
            and len(self.ui.path) == 2
            and self.ui.path[0] == "saved"
        )

    def handle(self) -> None:
        """
        Handle the save request by extending the test expiry time.

        This touches the save file to update its modification time,
        then redirects to the saved test page.
        """
        # Only proceed if save_dir is configured
        if not self.ui.config.get("save_dir"):
            self.ui.error_response(b"404", b"Not Found", "Saving not configured.")
            return

        test_id = self.ui.path[1]
        if not test_id:
            self.ui.error_response(b"400", b"Bad Request", "test_id not provided.")
            return

        try:
            # Touch the save file so it isn't deleted
            now = time.time()
            state_dir = self.ui.config.get("save_dir", "")
            if not os.path.exists(state_dir):
                raise OSError("Save directory does not exist")

            os.utime(
                os.path.join(state_dir, test_id),
                (
                    now,
                    now
                    + (self.ui.config.getint("save_days", fallback=30) * 24 * 60 * 60),
                ),
            )

            # Build redirect location
            location = LoadSavedTestHandler(self.ui).render_link(
                test_id, descend="descend" in self.ui.query_string
            )

            self.ui.exchange.response_start(
                b"303", b"See Other", [(b"Location", location.encode("ascii"))]
            )
            self.ui.output("Redirecting to the saved test page...")
        except OSError:
            self.ui.error_response(
                b"500", b"Internal Server Error", "Sorry, I couldn't save that."
            )
            return

        self.ui.exchange.response_done([])

    def render_link(self, **kwargs: Any) -> str:
        """
        Generate a URI for saving a test.
        """
        return ""

    def render_form(self, **kwargs: str) -> str:
        """
        Generate an HTML form for saving a test.

        Args:
            **kwargs: Required keys:
                - id (str): Test ID to save
                - descend (str, optional): "True" if descend mode

        Returns:
            HTML form for saving
        """
        base_uri = self.get_base_uri()
        test_id = kwargs.get("id", "")
        descend = kwargs.get("descend", "")

        params = {}
        if descend == "True":
            params["descend"] = "True"

        action = f"{base_uri}saved/{test_id}?{urlencode(params)}"
        form_parts = [f'<form method="POST" id="save_form" action="{escape(action)}">']
        form_parts.append("</form>")

        return "".join(form_parts)


class LoadSavedTestHandler(RequestHandler):
    """
    Handler for loading and displaying saved test results.

    This handler responds to GET/HEAD requests with 'id' in the query string.
    It loads the saved test from disk and displays it using the appropriate formatter.
    """

    def can_handle(self) -> bool:
        """
        Determine if this handler should process the request.

        Handles GET/HEAD requests with 'id' in query string.
        """
        return (
            self.ui.method in ["GET", "HEAD"]
            and len(self.ui.path) == 2
            and self.ui.path[0] == "saved"
        )

    def handle(self) -> None:
        """
        Handle the load request by loading and displaying the saved test.

        Loads the pickled test data from disk, creates the appropriate formatter,
        and displays the results.
        """
        test_id = self.ui.path[1]
        if not test_id:
            self.ui.error_response(b"400", b"Bad Request", "test_id not provided.")
            return

        state_dir = self.ui.config.get("save_dir", "")
        if not os.path.exists(state_dir):
            self.ui.error_response(b"404", b"Not Found", "Saving not configured.")
            return

        try:
            with cast(
                IO[bytes],
                gzip.open(os.path.join(state_dir, os.path.basename(test_id))),
            ) as fd:
                mtime = os.fstat(fd.fileno()).st_mtime
                is_saved = mtime > time.time()
                top_resource = pickle.load(fd)
        except (OSError, TypeError):
            self.ui.error_response(
                b"404", b"Not Found", "I'm sorry, I can't find that saved response."
            )
            return
        except (pickle.PickleError, zlib.error, EOFError):
            self.ui.error_response(
                b"500",
                b"Internal Server Error",
                "I'm sorry, I had a problem loading that.",
            )
            return

        if "check_name" in self.ui.query_string:
            check_name = self.ui.query_string.get("check_name", [None])[0]
            display_resource = top_resource.subreqs.get(check_name, top_resource)
        else:
            display_resource = top_resource

        format_ = self.ui.query_string.get("format", ["html"])[0]
        formatter = find_formatter(format_, "html", top_resource.descend)(
            self.ui.config,
            display_resource,
            self.ui.output,
            {
                "allow_save": (not is_saved),
                "is_saved": True,
                "save_mtime": mtime,
                "test_id": test_id,
                "nonce": self.ui.nonce,
                "link_generator": self.ui.link_generator,
            },
        )

        self.ui.exchange.response_start(
            b"200",
            b"OK",
            [
                (b"Content-Type", formatter.content_type()),
                (b"Cache-Control", b"max-age=3600, must-revalidate"),
            ],
        )

        @thor.events.on(formatter)
        def formatter_done() -> None:
            self.ui.exchange.response_done([])

        formatter.bind_resource(display_resource)

    def render_link(
        self,
        test_id: str = "",
        output_format: str = "",
        check_name: str = "",
        descend: bool = False,
        absolute: bool = False,
        **kwargs: Any,
    ) -> str:
        """
        Generate a URI for loading a saved test.

        Args:
            test_id: Test ID to load
            output_format: Output format (optional)
            check_name: Specific check to display (optional)
            descend: If True, include descend parameter
            absolute: If True, return absolute URI

        Returns:
            URI for loading the saved test
        """
        base_uri = self.get_base_uri(absolute)
        params = []
        if output_format:
            params.append(("format", output_format))
        if check_name:
            params.append(("check_name", check_name))
        if descend:
            params.append(("descend", "True"))

        return f"{base_uri}saved/{test_id}?{urlencode(params)}"

    def render_form(self, **kwargs: str) -> str:
        """
        Loading saved tests doesn't typically use forms.

        Returns:
            Empty string (no form needed)
        """
        return ""
