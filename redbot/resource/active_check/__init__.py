"""
Subrequests to do things like range requests, content negotiation checks,
and validation.
"""

from typing import List, Type, Union

from .conneg import ConnegCheck
from .range import RangeRequest
from .etag_validate import ETagValidate
from .lm_validate import LmValidate

active_checks: List[
    Union[Type[ConnegCheck], Type[RangeRequest], Type[ETagValidate], Type[LmValidate]]
] = [
    ConnegCheck,
    RangeRequest,
    ETagValidate,
    LmValidate,
]
