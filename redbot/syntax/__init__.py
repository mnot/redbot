
import re, sys, types

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

def check_regex():
    """Grab all the regex in this module."""
    for module_name in __all__:
        __import__(module_name)
        module = sys.modules[module_name]
        for attr_name in dir(module):
            attr_value = getattr(module, attr_name, None)
            if isinstance(attr_value, types.StringType):
                try:
                    re.compile(attr_value, re.VERBOSE)
                except re.error, why:
                    print "*", module_name, attr_name, why.message


if __name__ == "__main__":
    check_regex()
