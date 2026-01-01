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
from redbot.type import RedWebUiProtocol

if TYPE_CHECKING:
    from redbot.webui import RedWebUi


class SaveHandler(RequestHandler):
    """
    Handler for extending the expiry time of saved test results.

    This handler responds to POST requests with 'save' and 'id' parameters
    in the query string. It updates the modification time of the saved test
    file to extend its expiry, then redirects to the saved test page.
    """

    @classmethod
    def can_handle(cls, ui: RedWebUiProtocol) -> bool:
        """
        Determine if this handler should process the request.

        Handles POST requests with 'save' and 'id' in query string.
        """
        return (
            ui.method == "POST"
            and len(ui.path) == 2
            and ui.path[0] == "saved"
        )

    @classmethod
    def handle(cls, ui: RedWebUiProtocol) -> None:
        """
        Handle the save request by extending the test expiry time.

        This touches the save file to update its modification time,
        then redirects to the saved test page.
        """
        # Only proceed if save_dir is configured
        if not ui.config.get("save_dir"):
            ui.error_response(b"404", b"Not Found", "Saving not configured.")
            return

        test_id = ui.path[1]
        if not test_id:
            ui.error_response(b"400", b"Bad Request", "test_id not provided.")
            return

        try:
            # Touch the save file so it isn't deleted
            now = time.time()
            state_dir = ui.config.get("save_dir", "")
            if not os.path.exists(state_dir):
                raise OSError("Save directory does not exist")

            os.utime(
                os.path.join(state_dir, test_id),
                (
                    now,
                    now
                    + (ui.config.getint("save_days", fallback=30) * 24 * 60 * 60),
                ),
            )

            # Build redirect location
            location = LoadSavedTestHandler.render_link(
                ui,
                test_id,
                descend="descend" in ui.query_string
            )

            ui.exchange.response_start(
                b"303", b"See Other", [(b"Location", location.encode("ascii"))]
            )
            ui.output("Redirecting to the saved test page...")
        except OSError:
            ui.error_response(
                b"500", b"Internal Server Error", "Sorry, I couldn't save that."
            )
            return

        ui.exchange.response_done([])

    @classmethod
    def render_link(cls, ui: RedWebUiProtocol, **kwargs: Any) -> str:
        """
        Generate a URI for saving a test.
        """
        return ""

    @classmethod
    def render_form(cls, ui: RedWebUiProtocol, **kwargs: str) -> str:
        """
        Generate an HTML form for saving a test.

        Args:
            ui: The WebUI instance
            **kwargs: Required keys:
                - id (str): Test ID to save
                - descend (str, optional): "True" if descend mode

        Returns:
            HTML form for saving
        """
        base_uri = cls.get_base_uri(ui)
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

    @classmethod
    def can_handle(cls, ui: RedWebUiProtocol) -> bool:
        """
        Determine if this handler should process the request.

        Handles GET/HEAD requests with 'id' in query string.
        """
        return (
            ui.method in ["GET", "HEAD"]
            and len(ui.path) == 2
            and ui.path[0] == "saved"
        )

    @classmethod
    def handle(cls, ui: RedWebUiProtocol) -> None:
        """
        Handle the load request by loading and displaying the saved test.

        Loads the pickled test data from disk, creates the appropriate formatter,
        and displays the results.
        """
        test_id = ui.path[1]
        if not test_id:
            ui.error_response(b"400", b"Bad Request", "test_id not provided.")
            return

        state_dir = ui.config.get("save_dir", "")
        if not os.path.exists(state_dir):
            ui.error_response(b"404", b"Not Found", "Saving not configured.")
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
            ui.error_response(
                b"404", b"Not Found", "I'm sorry, I can't find that saved response."
            )
            return
        except (pickle.PickleError, zlib.error, EOFError):
            ui.error_response(
                b"500",
                b"Internal Server Error",
                "I'm sorry, I had a problem loading that.",
            )
            return

        if "check_name" in ui.query_string:
            check_name = ui.query_string.get("check_name", [None])[0]
            display_resource = top_resource.subreqs.get(check_name, top_resource)
        else:
            display_resource = top_resource

        format_ = ui.query_string.get("format", ["html"])[0]
        formatter = find_formatter(format_, "html", top_resource.descend)(
            ui.config,
            display_resource,
            ui.output,
            {
                "allow_save": (not is_saved),
                "is_saved": True,
                "save_mtime": mtime,
                "test_id": test_id,
                "nonce": ui.nonce,
                "link_generator": ui.link_generator,
            },
        )

        ui.exchange.response_start(
            b"200",
            b"OK",
            [
                (b"Content-Type", formatter.content_type()),
                (b"Cache-Control", b"max-age=3600, must-revalidate"),
            ],
        )

        @thor.events.on(formatter)
        def formatter_done() -> None:
            ui.exchange.response_done([])

        formatter.bind_resource(display_resource)

    @classmethod
    def render_link(
        cls,
        ui: RedWebUiProtocol,
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
            ui: The WebUI instance
            test_id: Test ID to load
            output_format: Output format (optional)
            check_name: Specific check to display (optional)
            descend: If True, include descend parameter
            absolute: If True, return absolute URI

        Returns:
            URI for loading the saved test
        """
        base_uri = cls.get_base_uri(ui, absolute)
        params = []
        if output_format:
            params.append(("format", output_format))
        if check_name:
            params.append(("check_name", check_name))
        if descend:
            params.append(("descend", "True"))

        return f"{base_uri}saved/{test_id}?{urlencode(params)}"

    @classmethod
    def render_form(cls, ui: RedWebUiProtocol, **kwargs: str) -> str:
        """
        Loading saved tests doesn't typically use forms.

        Returns:
            Empty string (no form needed)
        """
        return ""
