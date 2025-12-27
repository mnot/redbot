# from configparser import SectionProxy # Unused
from typing import List, Any, Optional
from urllib.parse import urljoin

from redbot.type import RedWebUiProtocol
from redbot.webui.handlers import (
    SaveHandler,
    LoadSavedTestHandler,
    ClientErrorHandler,
    ShowHandler,
    RunTestHandler,
)


class WebUiLinkGenerator:
    """
    Generates links for the Web UI using registered handlers.
    Implements the LinkGenerator protocol.
    """

    def __init__(self, ui: RedWebUiProtocol) -> None:
        self.ui = ui
        self.config = ui.config

    def save_form(self, test_id: str, descend: bool = False) -> str:
        """Generate a form to save a test."""
        return SaveHandler(self.ui).render_form(
            id=test_id, descend="True" if descend else ""
        )

    def load_link(
        self,
        test_id: str,
        output_format: str = "",
        check_name: str = "",
        descend: bool = False,
    ) -> str:
        """Generate a link to load a saved test."""
        return LoadSavedTestHandler(self.ui).render_link(
            test_id=test_id,
            output_format=output_format,
            check_name=check_name,
            descend=descend,
        )

    def client_error_link(self) -> str:
        """Generate a link for client error reporting."""
        return ClientErrorHandler(self.ui).render_link()

    def home_link(self, absolute: bool = False) -> str:
        """Generate a link to the home page."""
        return ShowHandler(self.ui).render_link(absolute=absolute)

    def test_form(
        self,
        link_value: str,
        headers: List[str],
        uri: str,
        check_name: str = "",
        output_format: str = "",
        descend: bool = False,
        css_class: str = "",
        title: str = "",
    ) -> str:
        """Generate a form for running a test."""
        return RunTestHandler(self.ui).render_form(
            link_text=link_value,
            headers=headers,
            uri=uri,
            check_name=check_name,
            format=output_format,
            descend="True" if descend else "",
            css_class=css_class,
            title=title,
        )

    def resource_link(
        self,
        resource: Any,
        link: str,
        label: Any,
        title: Any = "",
        css_class: str = "",
        descend: bool = False,
        use_stored: bool = False,
        test_id: Optional[str] = None,
    ) -> str:
        """Link to a resource."""
        return self._generate_link(
            resource=resource,
            link_value=label,
            link=link,
            title=title,
            css_class=css_class,
            descend=descend,
            use_stored=use_stored,
            test_id=test_id,
            referer=True,
        )

    def har_link(
        self,
        resource: Any,
        label: Any,
        title: Any = "",
        test_id: Optional[str] = None,
    ) -> str:
        """Link to the HAR view."""
        return self._generate_link(
            resource=resource,
            link_value=label,
            title=title,
            res_format="har",
            test_id=test_id,
        )

    def check_link(
        self,
        resource: Any,
        label: Any,
        check_name: str,
        check_id: Optional[str] = None,
        test_id: Optional[str] = None,
    ) -> str:
        """Link to a subrequest check."""
        return self._generate_link(
            resource=resource,
            link_value=label,
            check_name=check_id,
            test_id=test_id,
        )

    def _generate_link(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        resource: Any,
        link_value: Any,
        link: Optional[str] = None,
        check_name: Optional[str] = None,
        test_id: Optional[str] = None,
        res_format: Optional[str] = None,
        use_stored: bool = True,
        descend: bool = False,
        referer: bool = False,
        css_class: str = "",
        title: Any = "",
    ) -> str:
        uri = resource.request.uri
        if not uri:
            return "-"

        # For saved tests, delegate to LoadSavedTestHandler
        if use_stored and test_id:
            # Determine check_name
            # If check_name passed as arg, use it (for subreq link).
            # But the logic was: check = check_name or (resource.check_id...)
            # We should preserve that logic if check_name is None.
            check = check_name or (
                resource.check_id if resource.check_id is not None else ""
            )

            link_uri = self.load_link(
                test_id=test_id,
                check_name=check,
                output_format=res_format or "",
                descend=descend,
            )
            return (
                f"<a href='{link_uri}'"
                f"class='{css_class}' title='{title}'>{link_value}</a>"
            )

        # For new tests, gather context and delegate to RunTestHandler
        test_uri = urljoin(uri, link or "")

        # Collect request headers from current context
        headers = []
        for name, val in resource.request.headers.text:
            if referer and name.lower() == "referer":
                continue
            headers.append(f"{name}:{val}")
        if referer:
            headers.append(f"Referer:{uri}")

        # Delegate to generator
        return self.test_form(
            link_value=str(link_value),
            headers=headers,
            uri=test_uri,
            check_name=check_name
            or (resource.check_id if resource.check_id is not None else ""),
            output_format=res_format or "",
            descend=descend,
            css_class=css_class,
            title=str(title),
        )
