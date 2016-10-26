
from typing import Any, Callable, Dict, List, Tuple

StrHeaderListType = List[Tuple[str, str]]
RawHeaderListType = List[Tuple[bytes, bytes]]
HeaderDictType = Dict[str, Any]
ParamDictType = Dict[str, str]
AddNoteMethodType = Callable[..., None]
