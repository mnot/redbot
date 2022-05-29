#!/usr/bin/env python

import re
import sys
import types

__all__ = [
    "rfc3986",
    "rfc5234",
    "rfc5322",
    "rfc5646",
    "rfc5987",
    "rfc5988",
    "rfc7230",
    "rfc7231",
    "rfc7232",
    "rfc7233",
    "rfc7234",
    "rfc7235",
]


def check_regex() -> None:
    """Grab all the regex in this module."""
    for module_name in __all__:
        full_name = f"redbot.syntax.{module_name}"
        __import__(full_name)
        module = sys.modules[full_name]
        for attr_name in dir(module):
            attr_value = getattr(module, attr_name, None)
            if isinstance(attr_value, bytes):
                try:
                    re.compile(attr_value, re.VERBOSE)
                except re.error as why:
                    print("*", module_name, attr_name, why)


if __name__ == "__main__":
    check_regex()
