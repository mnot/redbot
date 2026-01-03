from typing import List, Any, Optional


class NullLinkGenerator:
    """
    A null object implementation of LinkGenerator.
    Used when no web UI link generator is available (e.g. CLI).
    """

    def save_form(self, test_id: str, descend: bool = False) -> str:
        return ""

    def load_link(
        self,
        test_id: str,
        output_format: str = "",
        check_name: str = "",
        descend: bool = False,
    ) -> str:
        return ""

    def client_error_link(self) -> str:
        return ""

    def home_link(self, absolute: bool = False) -> str:
        return ""

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
        return ""

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
        return ""

    def har_link(
        self,
        resource: Any,
        label: Any,
        title: Any = "",
        test_id: Optional[str] = None,
    ) -> str:
        return ""

    def check_link(
        self,
        resource: Any,
        label: Any,
        check_name: str,
        check_id: Optional[str] = None,
        test_id: Optional[str] = None,
    ) -> str:
        return ""
