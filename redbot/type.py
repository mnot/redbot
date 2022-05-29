from typing import Any, Callable, Dict, List, Tuple

from typing_extensions import Protocol

StrHeaderListType = List[Tuple[str, str]]
RawHeaderListType = List[Tuple[bytes, bytes]]
HeaderDictType = Dict[str, Any]
ParamDictType = Dict[str, str]
AddNoteMethodType = Callable[..., None]


class HttpResponseExchange(Protocol):
    def response_start(
        self, status_code: bytes, status_phrase: bytes, res_hdrs: RawHeaderListType
    ) -> None:
        ...

    def response_body(self, chunk: bytes) -> None:
        ...

    def response_done(self, trailers: RawHeaderListType) -> None:
        ...
