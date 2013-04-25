#!/usr/bin/env python

"""
Subrequest for partial content checks.
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

import random

from redbot.resource.active_check.base import SubRequest
from redbot.formatter import f_num
import redbot.speak as rs

class RangeRequest(SubRequest):
    "Check for partial content support (if advertised)"

    def __init__(self, red, name):
        SubRequest.__init__(self, red, name)
        self.range_start = None
        self.range_end = None
        self.range_target = None
        
    def modify_req_hdrs(self):
        req_hdrs = list(self.base.request.headers)
        if len(self.base.response.payload_sample) != 0:
            sample_num = random.randint(
                0, 
                len(self.base.response.payload_sample) - 1
            )
            sample_len = min(
                96, 
                len(self.base.response.payload_sample[sample_num][1])
            )
            self.range_start = \
              self.base.response.payload_sample[sample_num][0]
            self.range_end = self.range_start + sample_len
            self.range_target = \
              self.base.response.payload_sample[sample_num][1] \
                [:sample_len + 1]
            # TODO: uses the compressed version (if available). Revisit.
            req_hdrs += [
                (u'Range', u"bytes=%s-%s" % (
                    self.range_start, self.range_end
                ))
            ]
        return req_hdrs
        
    def preflight(self):
        if 'bytes' in \
          self.base.response.parsed_headers.get('accept-ranges', []):
            if len(self.base.response.payload_sample) == 0:
                return False
            if self.range_start == self.range_end: 
                # wow, that's a small body.
                return False
            return True
        else:
            self.base.partial_support = False
            return False

    def done(self):
        if not self.state.response.complete:
            self.set_message('', rs.RANGE_SUBREQ_PROBLEM,
                problem=self.state.response.http_error.desc
            )
            return
            
        if self.state.response.status_code == '206':
            c_e = 'content-encoding'
            if 'gzip' in self.base.response.parsed_headers.get(c_e, []) == \
               'gzip' not in self.state.response.parsed_headers.get(c_e, []):
                self.set_message(
                    'header-accept-ranges header-content-encoding',
                    rs.RANGE_NEG_MISMATCH
                )
                return
            if not [True for h in self.base.orig_req_hdrs 
                if h[0].lower() == 'if-range']:
                self.check_missing_hdrs([
                        'date', 'cache-control', 'content-location', 'etag', 
                        'expires', 'vary'
                    ], rs.MISSING_HDRS_206, 'Range'
                )
            if self.state.response.parsed_headers.get('etag', 1) == \
              self.base.response.parsed_headers.get('etag', 2):
                if self.state.response.payload == self.range_target:
                    self.base.partial_support = True
                    self.set_message('header-accept-ranges', rs.RANGE_CORRECT)
                else:
                    # the body samples are just bags of bits
                    self.base.partial_support = False
                    self.set_message('header-accept-ranges',
                        rs.RANGE_INCORRECT,
                        range="bytes=%s-%s" % (
                            self.range_start, self.range_end
                        ),
                        range_expected = \
                          self.range_target.encode('string_escape'),
                        range_expected_bytes = f_num(len(self.range_target)),
                        range_received = \
                          self.state.response.payload.encode('string_escape'),
                        range_received_bytes = \
                          f_num(self.state.response.payload_len)
                    )
            else:
                self.set_message('header-accept-ranges', rs.RANGE_CHANGED)

        # TODO: address 416 directly
        elif self.state.response.status_code == \
          self.base.response.status_code:
            self.base.partial_support = False
            self.set_message('header-accept-ranges', rs.RANGE_FULL)
        else:
            self.set_message('header-accept-ranges', 
                rs.RANGE_STATUS,
                range_status=self.state.response.status_code,
                enc_range_status=self.state.response.status_code or \
                  '(unknown)'
            )