#!/usr/bin/env python

"""
Subrequest for ETag validation checks.
"""

__author__ = "Mark Nottingham <mnot@mnot.net>"
__copyright__ = """\
Copyright (c) 2008-2012 Mark Nottingham

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
import redbot.speak as rs

class ETagValidate(SubRequest):
    "If an ETag is present, see if it will validate."

    def modify_req_hdrs(self):
        req_hdrs = list(self.base.req_hdrs)
        if self.base.parsed_hdrs.has_key('etag'):
            weak, etag = self.base.parsed_hdrs['etag']
            if weak:
                weak_str = u"W/"
                # #65: message on weak etag
            else:
                weak_str = u""
            etag_str = u'%s"%s"' % (weak_str, etag)
            req_hdrs += [
                (u'If-None-Match', etag_str),
            ]
        return req_hdrs
            
    def preflight(self):
        if self.base.parsed_hdrs.has_key('etag'):
            return True
        else:
            self.base.inm_support = False
            return False

    def done(self):
        if not self.state.res_complete:
            self.set_message('', rs.ETAG_SUBREQ_PROBLEM,
                problem=self.state.res_error.desc
            )
            return
            
        if self.state.res_status == '304':
            self.base.inm_support = True
            self.set_message('header-etag', rs.INM_304)
            self.check_missing_hdrs([
                    'cache-control', 'content-location', 'etag', 
                    'expires', 'last-modified', 'vary'
                ], rs.MISSING_HDRS_304, 'If-None-Match'
            )
        elif self.state.res_status == self.base.res_status:
            if self.state.res_body_md5 == self.base.res_body_md5:
                self.base.inm_support = False
                self.set_message('header-etag', rs.INM_FULL)
            else: # bodies are different
                if self.base.parsed_hdrs['etag'] == \
                  self.state.parsed_hdrs.get('etag', 1):
                    if self.base.parsed_hdrs['etag'][0]: # weak
                        self.set_message('header-etag', rs.INM_DUP_ETAG_WEAK)
                    else: # strong
                        self.set_message('header-etag',
                                        rs.INM_DUP_ETAG_STRONG,
                                        etag=self.base.parsed_hdrs['etag'])
                else:
                    self.set_message('header-etag', rs.INM_UNKNOWN)
        else:
            self.set_message('header-etag', 
                rs.INM_STATUS, 
                inm_status = self.state.res_status,
                enc_inm_status = self.state.res_status or '(unknown)'
            )
        # TODO: check entity headers