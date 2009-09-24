"""
Header- and Status-specific detail/definition messages

Each should be in the form:

  HDR_HEADER_NAME = {'lang': u'message'}
or
  STATUS_NNN = {'lang': u'message'}

where HEADER_NAME is the header's field name in all capitals and with hyphens
replace with underscores, NNN is the three-digit status code, lang' is a
language tag, and 'message' is a description of the header that may
contain HTML.

The following %(var)s style variable interpolations are available:
  field_name - the name of the header

PLEASE NOTE: the description IS NOT ESCAPED, and therefore all variables to be
interpolated into it need to be escaped.
"""

__author__ = "Mark Nottingham <mnot@mnot.net>"
__copyright__ = """\
Copyright (c) 2009 Mark Nottingham

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

HDR_KEEP_ALIVE = {
    'en': u"""The <code>Keep-Alive</code> header is completely optional; it
    is defined primarily because the <code>keep-alive</code> connection token
    implies that such a header exists, not because anyone actually uses it.<p>
    Some implementations (e.g., <a href="http://httpd.apache.org/">Apache</a>)
    do generate a <code>Keep-Alive</code> header to convey how many requests
    they're willing to serve on a single connection, what the connection timeout
    is and other information. However, this isn't usually used by clients.<p>
    It's safe to remove this header if you wish to save a few bytes in the
    response."""
}

HDR_NNCOECTION = \
HDR_CNEONCTION = \
HDR_YYYYYYYYYY = \
HDR_XXXXXXXXXX = \
HDR_X_CNECTION = \
HDR__ONNECTION = {
     'en': u"""The <code>Connection</code> header is used to indicate what
     headers are hop-by-hop, and to signal that the connection should not be
     reused by the client, with the <code>close</code> directive.<p>
     The <code>%(field_name)s</code> field usually means that a HTTP load
     balancer, proxy or other intermediary in front of the server has replaced
     the <code>Connection</code> header, to allow the connection to be reused.<p>
     It takes this form because the most efficient way to strip the server's
     <code>Connection</code> header is to rewrite its name into something
     that isn't recognisable.
     """
}

HDR_X_PAD_FOR_NETSCRAPE_BUG = \
HDR_X_PAD = \
HDR_XX_PAD = \
HDR_X_BROWSERALIGNMENT = {
     'en': u"""The <code>%(field_name)s</code> header is used to "pad" the
     response header size; very old versions of the Netscape browser had a
     bug whereby a response whose headers were exactly 256 or 257 bytes long,
     the browser would consider the response (e.g., an image) invalid.<p>
     Since the affected browsers (specifically, Netscape 2.x, 3.x and 4.0 up to
     beta 2) are no longer widely used, it's probably safe to omit this header.
     """
}
