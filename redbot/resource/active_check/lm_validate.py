#!/usr/bin/env python

"""
Subrequest for Last-Modified validation checks.
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

from datetime import datetime

from redbot.resource.active_check.base import SubRequest
import redbot.speak as rs

class LmValidate(SubRequest):
    "If Last-Modified is present, see if it will validate."

    _weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    _months = [None, 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 
                     'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    def modify_req_hdrs(self):
        req_hdrs = list(self.base.request.headers)
        if self.base.response.parsed_headers.has_key('last-modified'):
            try:
                l_m = datetime.utcfromtimestamp(
                    self.base.response.parsed_headers['last-modified']
                )
            except ValueError:
                return req_hdrs # TODO: sensible error message.
            date_str = u"%s, %.2d %s %.4d %.2d:%.2d:%.2d GMT" % (
                self._weekdays[l_m.weekday()],
                l_m.day,
                self._months[l_m.month],
                l_m.year,
                l_m.hour,
                l_m.minute,
                l_m.second
            )
            req_hdrs += [
                (u'If-Modified-Since', date_str),
            ]
        return req_hdrs

    def preflight(self):
        if self.base.response.parsed_headers.has_key('last-modified'):
            return True
        else:
            self.base.ims_support = False
            return False

    def done(self):
        if not self.state.response.complete:
            self.add_note('', rs.LM_SUBREQ_PROBLEM,
                problem=self.state.response.http_error.desc
            )
            return
            
        if self.state.response.status_code == '304':
            self.base.ims_support = True
            self.add_note('header-last-modified', rs.IMS_304)
            self.check_missing_hdrs([
                    'cache-control', 'content-location', 'etag', 
                    'expires', 'vary'
                ], rs.MISSING_HDRS_304, 'If-Modified-Since'
            )
        elif self.state.response.status_code \
          == self.base.response.status_code:
            if self.state.response.payload_md5 \
              == self.base.response.payload_md5:
                self.base.ims_support = False
                self.add_note('header-last-modified', rs.IMS_FULL)
            else:
                self.add_note('header-last-modified', rs.IMS_UNKNOWN)
        else:
            self.add_note('header-last-modified', 
                rs.IMS_STATUS, 
                ims_status = self.state.response.status_code,
                enc_ims_status = self.state.response.status_code \
                  or '(unknown)'
            )
        # TODO: check entity headers
