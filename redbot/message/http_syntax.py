#!/usr/bin/env python

"""
HTTP Syntax
"""

__author__ = "Mark Nottingham <mnot@mnot.net>"
__copyright__ = """\
Copyright (c) 2008-2013 Mark Nottingham

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
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