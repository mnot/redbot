#!/usr/bin/env python

"""
Subrequest for content negotiation checks.
"""

__author__ = "Mark Nottingham <mnot@mnot.net>"
__copyright__ = """\
Copyright (c) 2008-2011 Mark Nottingham

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


from redbot.subrequest.base import SubRequest
from redbot.headers import f_num
import redbot.speak as rs

class ConnegCheck(SubRequest):
    """
    See if content negotiation for compression is supported, and how.

    Note that this depends on the "main" request being sent with
    Accept-Encoding: gzip
    """
    def modify_req_hdrs(self):
        return [h for h in self.base.orig_req_hdrs 
                  if h[0].lower() != 'accept-encoding'] + \
               [('accept-encoding', 'identity')]

    def preflight(self):
        if "gzip" in self.base.parsed_hdrs.get('content-encoding', []):
            return True
        else:
            self.base.gzip_support = False
            return False

    def done(self):
        # see if it was compressed when not negotiated
        no_conneg_vary_headers = self.state.parsed_hdrs.get('vary', [])
        if 'gzip' in self.state.parsed_hdrs.get('content-encoding', []) or \
           'x-gzip' in self.state.parsed_hdrs.get('content-encoding', []):
            self.set_message('header-vary header-content-encoding',
                            rs.CONNEG_GZIP_WITHOUT_ASKING)
        else: # Apparently, content negotiation is happening.

            # check status
            if self.base.res_status != self.state.res_status:
                self.set_message('status', rs.VARY_STATUS_MISMATCH, 
                  neg_status=self.base.res_status,
                  noneg_status=self.state.res_status)
                return  # Can't be sure what's going on...

            # check headers that should be invariant
            for hdr in ['content-type']:
                if self.base.parsed_hdrs.get(hdr) != \
                  self.state.parsed_hdrs.get(hdr, None):
                    self.set_message('header-%s' % hdr,
                      rs.VARY_HEADER_MISMATCH, 
                      header=hdr)
                    # TODO: expose on-the-wire values.

            # check Vary headers
            vary_headers = self.base.parsed_hdrs.get('vary', [])
            if (not "accept-encoding" in vary_headers) and \
               (not "*" in vary_headers):
                self.set_message('header-vary', rs.CONNEG_NO_VARY)
            if no_conneg_vary_headers != vary_headers:
                self.set_message('header-vary', 
                    rs.VARY_INCONSISTENT,
                    conneg_vary=", ".join(vary_headers),
                    no_conneg_vary=", ".join(no_conneg_vary_headers)
                )

            # check body
            if self.base.res_body_post_md5 != self.state.res_body_md5:
                self.set_message('body', rs.VARY_BODY_MISMATCH)
                return  # Can't be sure what's going on...

            # check ETag
            if self.state.parsed_hdrs.get('etag', 1) \
               == self.base.parsed_hdrs.get('etag', 2):
                self.set_message('header-etag', rs.VARY_ETAG_DOESNT_CHANGE) 
                # TODO: weakness?

            # check compression efficiency
            if self.state.res_body_len > 0:
                savings = int(100 * 
                    (
                        (float(self.state.res_body_len) - \
                        self.base.res_body_len
                        ) / self.state.res_body_len
                    )
                )
            else:
                savings = 0
            self.base.gzip_support = True
            self.base.gzip_savings = savings
            if savings >= 0:
                self.set_message('header-content-encoding',
                    rs.CONNEG_GZIP_GOOD,
                    savings=savings,
                    orig_size=f_num(self.state.res_body_len),
                    gzip_size=f_num(self.base.res_body_len)
                )
            else:
                self.set_message('header-content-encoding',
                    rs.CONNEG_GZIP_BAD,
                    savings=abs(savings),
                    orig_size=f_num(self.state.res_body_len),
                    gzip_size=f_num(self.base.res_body_len)
                )