#!/usr/bin/env python

"""
parse_rfc_headers

Utility for finding the header definitions in the HTTPbis drafts and outputting
data structures that RED can read. 
"""

__author__ = "Mark Nottingham <mnot@mnot.net>"
__copyright__ = """\
Copyright (c) 2008-2009 Mark Nottingham

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


import re
import textwrap
from xml.sax import parse, handler

class HeaderSnatcher(handler.ContentHandler):
    def __init__(self, *args, **kw):
        handler.ContentHandler.__init__(self, *args, **kw)
        self.in_header_section = False
        self.first_t_in_section = False
        self.copying = False
        self.tr = textwrap.TextWrapper(width=60, subsequent_indent=" "*8)
        self.buffer = []
        self.field_name = None

    def startElement(self, name, attrs):
        start_call = getattr(self, "start_%s" % name, None)
        if start_call:
            start_call(attrs)
        elif self.copying:
            self.buffer.append("???")

    def endElement(self, name):
        end_call = getattr(self, "end_%s" % name, None)
        if end_call:
            end_call()

    def start_section(self, attrs):
        self.first_t_in_section = True

    def start_bcp14(self, attrs):
        pass

    def start_iref(self, attrs):
        if attrs.get("primary", None) == "true" and \
           attrs.get("item", None) == "Headers":
            self.in_header_section = True
            self.field_name = attrs.get("subitem", "-")

    def start_t(self, attrs):
        if self.first_t_in_section and self.in_header_section:
            self.copying = True

    def end_t(self):
        self.first_t_in_section = False
        if self.copying:
            clean_content = re.sub("[\r\n\t ]{2,}", " ", "".join(self.buffer))
            clean_content = re.sub(" \((?:as (?:defined|described) in )?\?\?\?\)", "", clean_content)
            clean_content = re.sub("The \w+\-header (?:field )?\"([\w\-]+)\"(?: header)?(?: field)?", "The <code>\\1</code> header", clean_content)
            field_desc = self.tr.fill(clean_content).strip()
            print """\
HDR_%s = {
    'en': u\"""%s\"""
}
""" % (self.field_name.upper().replace("-", "_"), field_desc)
            self.buffer = []
            self.copying = False
            self.in_header_section = False
            self.field_name = None

    def characters(self, content):
        if self.copying:
            self.buffer.append(content)


if __name__ == "__main__":
    import sys
    for in_file in sys.argv[1:]:
        parse(in_file, HeaderSnatcher())