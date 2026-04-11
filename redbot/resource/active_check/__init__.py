"""
Subrequests to do things like range requests, content negotiation checks,
and validation.
"""

from typing import List, Type, Union

from .conneg import ConnegCheck
from .etag_validate import ETagValidate
from .lm_validate import LmValidate
from .range import RangeRequest

__all__ = [
    "ConnegCheck",
    "ETagValidate",
    "LmValidate",
    "RangeRequest",
    "active_checks",
]

active_checks: List[
    Union[Type[ConnegCheck], Type[RangeRequest], Type[ETagValidate], Type[LmValidate]]
] = [
    ConnegCheck,
    RangeRequest,
    ETagValidate,
    LmValidate,
]
