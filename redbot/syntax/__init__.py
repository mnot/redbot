
import re
import sys
import types

__all__ = ["rfc3986",
           "rfc5234",
           "rfc5322",
           "rfc5646",
           "rfc7230",
           "rfc7231",
           "rfc7232",
           "rfc7233",
           "rfc7234",
           "rfc7235"]

def check_regex() -> None:
    """Grab all the regex in this module."""
    for module_name in __all__:
        __import__(module_name)
        module = sys.modules[module_name]
        for attr_name in dir(module):
            attr_value = getattr(module, attr_name, None)
            if isinstance(attr_value, bytes):
                try:
                    re.compile(attr_value, re.VERBOSE)
                except re.error as why:
                    print("*", module_name, attr_name, why)


if __name__ == "__main__":
    check_regex()
