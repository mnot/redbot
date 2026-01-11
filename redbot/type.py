from configparser import SectionProxy
from typing import Callable, Dict, List, Tuple, Any, Optional, TYPE_CHECKING

from typing_extensions import Protocol

if TYPE_CHECKING:
    import thor.loop

StrHeaderListType = List[Tuple[str, str]]
RawHeaderListType = List[Tuple[bytes, bytes]]
ParamDictType = Dict[str, str]
AddNoteMethodType = Callable[..., None]


class HttpResponseExchange(Protocol):
    def response_start(
        self, status_code: bytes, status_phrase: bytes, res_hdrs: RawHeaderListType
    ) -> None: ...

    def response_done(self, trailers: RawHeaderListType) -> None: ...
    def response_body(self, chunk: bytes) -> None: ...


class RedWebUiProtocol(Protocol):
    config: "SectionProxy"
    exchange: HttpResponseExchange
    save_path: str
    charset: str
    req_headers: RawHeaderListType
    req_body: bytes
    method: str
    query_string: Dict[str, List[str]]
    path: List[str]
    nonce: str
    locale: str
    timeout: Optional["thor.loop.ScheduledEvent"]
    link_generator: "LinkGenerator"

    def output(self, chunk: str) -> None: ...
    def get_client_id(self) -> str: ...
    def get_client_ip(self) -> str: ...
    def error_response(
        self,
        status_code: bytes,
        status_phrase: bytes,
        message: str,
        log_message: Optional[str] = None,
    ) -> None: ...
    def error_log(self, message: str) -> None: ...
    def timeout_error(self, formatter: Any, detail: Optional[Callable[[], str]] = None) -> None: ...


class LinkGenerator(Protocol):
    def save_form(self, test_id: str, descend: bool = False) -> str: ...

    def load_link(
        self,
        test_id: str,
        output_format: str = "",
        check_name: str = "",
        descend: bool = False,
    ) -> str: ...

    def client_error_link(self) -> str: ...
    def home_link(self, absolute: bool = False) -> str: ...

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
    ) -> str: ...

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
    ) -> str: ...

    def har_link(
        self,
        resource: Any,
        label: Any,
        title: Any = "",
        test_id: Optional[str] = None,
    ) -> str: ...

    def check_link(
        self,
        resource: Any,
        label: Any,
        check_name: str,
        check_id: Optional[str] = None,
        test_id: Optional[str] = None,
    ) -> str: ...
