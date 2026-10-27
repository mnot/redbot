"""
Utility functions for REDbot.
"""

import configparser
import os
import sys
from functools import partial
from typing import NoReturn, Optional
from urllib.parse import quote as urlquote

from markupsafe import Markup


def config_error(program: str, message: str) -> NoReturn:
    "Report a problem with the configuration file in one line, and exit with a failure status."
    sys.exit(f"{program}: {message}")


def read_config(program: str, path: str) -> configparser.SectionProxy:
    """
    Read the [redbot] section of a configuration file. A file that is missing, unreadable or
    malformed, or that has no [redbot] section, ends the program with a one-line message rather
    than a traceback.
    """
    conf = configparser.ConfigParser()
    try:
        read = conf.read(path)
    except (configparser.Error, UnicodeError) as why:
        config_error(
            program, f"can't parse configuration file '{path}': {' '.join(str(why).split())}"
        )
    if not read:
        reason = "is not readable" if os.path.exists(path) else "was not found"
        config_error(program, f"configuration file '{path}' {reason}")
    if "redbot" not in conf:
        config_error(program, f"configuration file '{path}' has no [redbot] section")
    return conf["redbot"]


def unicode_url_escape(url: str, safe: str) -> str:
    """
    URL escape a unicode string. Assume that anything already encoded
    is to be left alone.
    """
    # also include "~" because it doesn't need to be encoded,
    # but Python does anyway :/
    return urlquote(url, safe + r"%~")


uri_gen_delims = r":/?#[]@"  # pylint: disable=invalid-name
uri_sub_delims = r"!$&'()*+,;="  # pylint: disable=invalid-name
e_url = partial(unicode_url_escape, safe=uri_gen_delims + uri_sub_delims)
e_authority = partial(unicode_url_escape, safe=uri_sub_delims + r"[]:@")
e_path = partial(unicode_url_escape, safe=uri_sub_delims + r":@/")
e_path_seg = partial(unicode_url_escape, safe=uri_sub_delims + r":@")
e_query = partial(unicode_url_escape, safe=uri_sub_delims + r":@/?")
e_query_arg = partial(unicode_url_escape, safe=r"!$'()*+,:@/?")
e_fragment = partial(unicode_url_escape, safe=r"!$&'()*+,;:@=/?")


def e_js(instr: str) -> Markup:
    """
    Make sure instr is safe for writing into a double-quoted
    JavaScript string.
    """
    if not instr:
        return Markup("")
    instr = instr.replace("\\", "\\\\")
    instr = instr.replace('"', r"\"")
    instr = instr.replace("\n", r"\n")
    instr = instr.replace("\r", r"")
    instr = instr.replace("<", r"\x3c")
    return Markup(instr)


def decode_text(data: bytes, encoding: Optional[str], errors: str = "replace") -> str:
    """
    Decode data using a charset name supplied by a remote party. If the name
    can't be used (unknown, not a text encoding, or 'undefined'), fall back to UTF-8.
    """
    try:
        return data.decode(encoding or "utf-8", errors)
    except (LookupError, UnicodeError):
        return data.decode("utf-8", "replace")
