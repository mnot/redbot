#!/usr/bin/env python

"""
Regular expressions for common HTTP syntax
"""

# URI syntax
from redbot.message.uri_syntax import URI, URI_reference, absolute_URI

# generic syntax regexen (assume processing with re.VERBOSE)
TOKEN = r'(?:[!#\$%&\'\*\+\-\.\^_`|~A-Za-z0-9]+?)'
QUOTED_STRING = r'(?:"(?:[ \t\x21\x23-\x5B\x5D-\x7E]|\\[ \t\x21-\x7E])*")'
PARAMETER = r'(?:%(TOKEN)s(?:\s*=\s*(?:%(TOKEN)s|%(QUOTED_STRING)s))?)' % locals()
TOK_PARAM = r'(?:%(TOKEN)s(?:\s*;\s*%(PARAMETER)s)*)' % locals()
PRODUCT = r'(?:%(TOKEN)s(?:/%(TOKEN)s)?)' % locals()
COMMENT = r"""(?:
    \((?:
        [^\(\)] |
        \\\( |
        \\\) |
        (?:
            \((?:
                [^\(\)] |
                \\\( |
                \\\) |
                (?:
                    \((?:
                        [^\(\)] |
                        \\\( |
                        \\\)
                    )*\)
                )
            )*\)
        )
    )*\)
)""" # only handles two levels of nested comments; does not check chars
COMMA = r'(?:\s*(?:,\s*)+)'
DIGITS = r'(?:[0-9]+)'
DATE = r"""(?:\w{3},\ [0-9]{2}\ \w{3}\ [0-9]{4}\ [0-9]{2}:[0-9]{2}:[0-9]{2}\ GMT |
         \w{6,9},\ [0-9]{2}\-\w{3}\-[0-9]{2}\ [0-9]{2}:[0-9]{2}:[0-9]{2}\ GMT |
         \w{3}\ \w{3}\ [0-9 ][0-9]\ [0-9]{2}:[0-9]{2}:[0-9]{2}\ [0-9]{4})
        """