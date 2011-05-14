#!/usr/bin/env python

"""
Subrequests to do things like range requests, content negotiation checks,
and validation.
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
import random
import time

from redbot.fetch import RedFetcher
from redbot.response_analyse import f_num
import redbot.speak as rs


class SubRequest(RedFetcher):
    """
    A subrequest of a "main" ResourceExpertDroid, made to perform additional
    behavioural tests on the resource.
    
    it both adorns the given red's state, and saves its own state in the
    given red's subreqs dict.
    """
    def __init__(self, red, name):
        self.base = red.state
        req_hdrs = self.modify_req_hdrs()
        RedFetcher.__init__(self, self.base.uri, self.base.method, req_hdrs,
                            self.base.req_body, red.status_cb, [], name)
        self.base.subreqs[name] = self.state
    
    def modify_req_hdrs(self):
        """
        Usually overidden; modifies the request's headers.
        
        Make sure it returns a copy of the orignals, not them.
        """
        return list(self.base.orig_req_hdrs)

    def setMessage(self, subject, msg, subreq=None, **kw):
        self.base.setMessage(subject, msg, self.state.type, **kw)


class ConnegCheck(SubRequest):
    """
    See if content negotiation for compression is supported, and how.

    Note that this depends on the "main" request being sent with
    Accept-Encoding: gzip
    """
    def modify_req_hdrs(self):
        return [h for h in self.base.orig_req_hdrs 
            if h[0].lower() != 'accept-encoding']

    def preflight(self):
        if "gzip" in self.base.parsed_hdrs.get('content-encoding', []):
            return True
        else:
            self.base.gzip_support = False
            return False

    def done(self):
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
            self.setMessage('header-content-encoding',
                rs.CONNEG_GZIP_GOOD,
                savings=savings,
                orig_size=f_num(self.state.res_body_len),
                gzip_size=f_num(self.base.res_body_len)
            )
        else:
            self.setMessage('header-content-encoding',
                rs.CONNEG_GZIP_BAD,
                savings=abs(savings),
                orig_size=f_num(self.state.res_body_len),
                gzip_size=f_num(self.base.res_body_len)
            )
        vary_headers = self.base.parsed_hdrs.get('vary', [])
        if (not "accept-encoding" in vary_headers) \
        and (not "*" in vary_headers):
            self.setMessage('header-vary header-%s', rs.CONNEG_NO_VARY)
        # TODO: verify that the status/body/hdrs are the same; 
        # if it's different, alert
        no_conneg_vary_headers = self.state.parsed_hdrs.get('vary', [])
        if 'gzip' in self.state.parsed_hdrs.get('content-encoding', []) or \
           'x-gzip' in self.state.parsed_hdrs.get('content-encoding', []):
            self.setMessage('header-vary header-content-encoding',
                                 rs.CONNEG_GZIP_WITHOUT_ASKING)
        if no_conneg_vary_headers != vary_headers:
            self.setMessage('header-vary', 
                rs.VARY_INCONSISTENT,
                conneg_vary=e(", ".join(vary_headers)),
                no_conneg_vary=e(", ".join(no_conneg_vary_headers))
            )
        if self.state.parsed_hdrs.get('etag', 1) \
           == self.base.parsed_hdrs.get('etag', 2):
            self.setMessage('header-etag', rs.ETAG_DOESNT_CHANGE) 
            # TODO: weakness?


class RangeRequest(SubRequest):
    "Check for partial content support (if advertised)"

    def modify_req_hdrs(self):
        req_hdrs = list(self.base.req_hdrs)
        if len(self.base.res_body_sample) != 0:
            sample_num = random.randint(0, len(self.base.res_body_sample) - 1)
            sample_len = min(
                96, len(self.base.res_body_sample[sample_num][1])
            )
            self.range_start = self.base.res_body_sample[sample_num][0]
            self.range_end = self.range_start + sample_len
            self.range_target = \
                self.base.res_body_sample[sample_num][1][:sample_len + 1]
            # TODO: uses the compressed version (if available. Revisit.
            req_hdrs += [
                ('Range', "bytes=%s-%s" % (self.range_start, self.range_end))
            ]
        return req_hdrs
        
    def preflight(self):
        if 'bytes' in self.base.parsed_hdrs.get('accept-ranges', []):
            if len(self.base.res_body_sample) == 0:
                return False
            if self.range_start == self.range_end: 
                # wow, that's a small body.
                return False
            return True
        else:
            self.base.partial_support = False
            return False

    def done(self):
        if self.state.res_status == '206':
            # TODO: check entity headers
            # TODO: check content-range
            ce = 'content-encoding'
            if ('gzip' in self.base.parsed_hdrs.get(ce, [])) == \
               ('gzip' not in self.state.parsed_hdrs.get(ce, [])):
                self.setMessage(
                    'header-accept-ranges header-content-encoding',
                    rs.RANGE_NEG_MISMATCH
                )
                return
            if self.state.parsed_hdrs.get('etag', 1) == \
              self.base.parsed_hdrs.get('etag', 2):
                if self.state.res_body == self.range_target:
                    self.base.partial_support = True
                    self.setMessage('header-accept-ranges', rs.RANGE_CORRECT)
                else:
                    # the body samples are just bags of bits
                    self.base.partial_support = False
                    self.setMessage('header-accept-ranges',
                        rs.RANGE_INCORRECT,
                        range="bytes=%s-%s" % (
                            self.range_start, self.range_end
                        ),
                        range_expected=e(
                            self.range_target.encode('string_escape')
                        ),
                        range_expected_bytes = f_num(len(self.range_target)),
                        range_received = e(
                            self.state.res_body.encode('string_escape')
                        ),
                        range_received_bytes = f_num(self.state.res_body_len)
                    )
            else:
                self.setMessage('header-accept-ranges', rs.RANGE_CHANGED)

        # TODO: address 416 directly
        elif self.state.res_status == self.base.res_status:
            self.base.partial_support = False
            self.setMessage('header-accept-ranges', rs.RANGE_FULL)
        else:
            self.setMessage('header-accept-ranges', 
                rs.RANGE_STATUS,
                range_status=self.state.res_status,
                enc_range_status=e(self.state.res_status)
            )


class ETagValidate(SubRequest):
    "If an ETag is present, see if it will validate."

    def modify_req_hdrs(self):
        req_hdrs = list(self.base.req_hdrs)
        if self.base.parsed_hdrs.has_key('etag'):
            weak, etag = self.base.parsed_hdrs['etag']
            if weak:
                weak_str = "W/"
                # TODO: message on weak etag
            else:
                weak_str = ""
            etag_str = '%s"%s"' % (weak_str, etag)
            req_hdrs += [
                ('If-None-Match', etag_str),
            ]
        return req_hdrs
            
    def preflight(self):
        if self.base.parsed_hdrs.has_key('etag'):
            return True
        else:
            self.base.inm_support = False
            return False

    def done(self):
        if self.state.res_status == '304':
            self.base.inm_support = True
            self.setMessage('header-etag', rs.INM_304, self.state)
            # TODO : check Content- headers, esp. length.
        elif self.state.res_status == self.base.res_status:
            if self.state.res_body_md5 == self.base.res_body_md5:
                self.base.inm_support = False
                self.setMessage('header-etag', rs.INM_FULL)
            else:
                self.setMessage('header-etag', rs.INM_UNKNOWN)
        else:
            self.setMessage('header-etag', 
                rs.INM_STATUS, 
                inm_status = self.state.res_status,
                enc_inm_status = e(self.state.res_status)
            )
        # TODO: check entity headers


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
