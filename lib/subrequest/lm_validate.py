#!/usr/bin/env python

"""
Subrequest for Last-Modified validation checks.
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

from cgi import escape as e
import time

from redbot.subrequest.base import SubRequest
import redbot.speak as rs

class LmValidate(SubRequest):
    "If Last-Modified is present, see if it will validate."

    def modify_req_hdrs(self):
        req_hdrs = list(self.base.req_hdrs)
        if self.base.parsed_hdrs.has_key('last-modified'):
            date_str = time.strftime(
                '%a, %d %b %Y %H:%M:%S GMT',
                time.gmtime(self.base.parsed_hdrs['last-modified'])
            )
            req_hdrs += [
                ('If-Modified-Since', date_str),
            ]
        return req_hdrs

    def preflight(self):
        if self.base.parsed_hdrs.has_key('last-modified'):
            return True
        else:
            self.base.ims_support = False
            return False

    def done(self):
        if self.state.res_status == '304':
            self.base.ims_support = True
            self.setMessage('header-last-modified', rs.IMS_304)
            # TODO : check Content- headers, esp. length.
        elif self.state.res_status == self.base.res_status:
            if self.state.res_body_md5 == self.base.res_body_md5:
                self.base.ims_support = False
                self.setMessage('header-last-modified', rs.IMS_FULL)
            else:
                self.setMessage('header-last-modified', rs.IMS_UNKNOWN)
        else:
            self.setMessage('header-last-modified', 
                rs.IMS_STATUS, 
                ims_status = self.state.res_status,
                enc_ims_status = e(self.state.res_status)
            )
        # TODO: check entity headers
