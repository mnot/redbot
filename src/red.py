#!/usr/bin/env python

"""
The Resource Expert Droid. 

RED will examine a HTTP resource for problems and other interesting 
characteristics, making a list of these observation messages available
for presentation to the user. It does so by potentially making a number
of requests to probe the resource's behaviour.

See webui.py for the Web front-end.
"""

__version__ = "1"
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
import time
import random
from cgi import escape as e

import red_speak as rs
from red_fetcher import RedFetcher
from response_analyse import relative_time
from uri_validate import absolute_URI

### configuration
cacheable_methods = ['GET']
heuristic_cacheable_status = ['200', '203', '206', '300', '301', '410']
max_uri = 8 * 1024
max_clock_skew = 5  # seconds


class ResourceExpertDroid(RedFetcher):
    """
    Given a URI (optionally with method, request headers and body), as well
    as an optional status callback and list of body processors, examine the
    URI for issues and notable conditions, making any necessary additional
    requests.
    
    Note that this primary request negotiates for gzip content-encoding; 
    see ConnegCheck.
    
    After processing the response-specific attributes of RedFetcher will be
    populated, as well as its messages; see that class for details.
    """
    def __init__(self, uri, method="GET", req_hdrs=None, req_body=None,
                 status_cb=None, body_procs=None):
        req_hdrs = req_hdrs or []
        req_hdrs.append(('Accept-Encoding', 'gzip'))
        req_hdrs.append(("User-Agent", "RED/%s (http://redbot.org/about)" % __version__))
        RedFetcher.__init__(self, uri, method, req_hdrs, req_body, 
                            status_cb, body_procs, req_type=method)

        # check the URI
        if not re.match("^\s*%s\s*$" % absolute_URI, uri, re.VERBOSE):
            self.setMessage('uri', rs.URI_BAD_SYNTAX)
        if len(uri) > max_uri:
            self.setMessage('uri', rs.URI_TOO_LONG, uri_len=len(uri))            
            
    def done(self):
        """
        Response is available; perform further processing that's specific to
        the "main" response.
        """
        self.checkClock()
        self.checkCaching()
        ConnegCheck(self)
        RangeRequest(self)
        ETagValidate(self)
        LmValidate(self)

    def checkClock(self):
        "Check for clock skew and dateless origin server."
        if not self.parsed_hdrs.has_key('date'):
            self.setMessage('', rs.DATE_CLOCKLESS)
            if self.parsed_hdrs.has_key('expires') or \
              self.parsed_hdrs.has_key('last-modified'):
                self.setMessage('header-expires header-last-modified', rs.DATE_CLOCKLESS_BAD_HDR)
            return
        skew = self.parsed_hdrs['date'] - \
          self.timestamp + self.parsed_hdrs.get('age', 0)
        if abs(skew) > max_clock_skew:
            self.setMessage('header-date', rs.DATE_INCORRECT, 
                             clock_skew_string=relative_time(skew, 0, 2)
                             )
        else:
            self.setMessage('header-date', rs.DATE_CORRECT)

    def checkCaching(self):
        "Examine HTTP caching characteristics."
        # TODO: check URI for query string, message about HTTP/1.0 if so
        # TODO: assure that there aren't any dup standard directives
        # TODO: check for spurious 'public' directive (e.g., sun.com)
        # TODO: check for capitalisation on standard directives
        cc_dict = dict(self.parsed_hdrs.get('cache-control', []))

        # Who can store this?
        if self.method not in cacheable_methods:
            self.store_shared = self.store_private = False
            self.setMessage('method', rs.METHOD_UNCACHEABLE, method=self.method)
            return # bail; nothing else to see here
        elif cc_dict.has_key('no-store'):
            self.store_shared = self.store_private = False
            self.setMessage('header-cache-control', rs.NO_STORE)
            return # bail; nothing else to see here
        elif cc_dict.has_key('private'):
            self.store_shared = False
            self.store_private = True
            self.setMessage('header-cache-control', rs.PRIVATE_CC)
        elif 'authorization' in [k.lower() for k, v in self.req_hdrs] and \
          not cc_dict.has_key('public'):
            self.store_shared = False
            self.store_private = True
            self.setMessage('header-cache-control', rs.PRIVATE_AUTH)
        else:
            self.store_shared = self.store_private = True
            self.setMessage('header-cache-control', rs.STOREABLE)

        # no-cache?
        if cc_dict.has_key('no-cache'):
            self.setMessage('header-cache-control', rs.NO_CACHE)
            return # TODO: differentiate when there aren't LM or ETag present.

        # vary?
        vary = self.parsed_hdrs.get('vary', set())
        if "*" in vary:
            self.setMessage('header-vary', rs.VARY_ASTERISK)
            return # bail; nothing else to see here
        elif len(vary) > 3:
            self.setMessage('header-vary', rs.VARY_COMPLEX, vary_count=len(vary))
        else:
            if "user-agent" in vary:
                self.setMessage('header-vary', rs.VARY_USER_AGENT)
            if "host" in vary:
                self.setMessage('header-vary', rs.VARY_HOST)
            # TODO: enumerate the axes in a message

        # calculate age
        if self.parsed_hdrs.has_key('date'):
            apparent_age = max(0, 
              int(self.timestamp - self.parsed_hdrs['date']))
        else:
            apparent_age = 0
        age = self.parsed_hdrs.get('age', 0)
        current_age = max(apparent_age, self.parsed_hdrs.get('age', 0))
        current_age_str = relative_time(current_age, 0, 0)
        self.age = age
        if age >= 1:
            self.setMessage('header-age header-date', rs.CURRENT_AGE, 
                                     current_age=current_age_str)
        
        # calculate freshness
        freshness_lifetime = 0
        has_explicit_freshness = False
        freshness_hdrs = ['header-date', 'header-expires']
        if cc_dict.has_key('s-maxage'): # TODO: differentiate message for s-maxage
            freshness_lifetime = cc_dict['s-maxage']
            freshness_hdrs.append('header-cache-control')
            has_explicit_freshness = True
        elif cc_dict.has_key('max-age'):
            freshness_lifetime = cc_dict['max-age']
            freshness_hdrs.append('header-cache-control')
            has_explicit_freshness = True
        elif self.parsed_hdrs.has_key('expires'):
            has_explicit_freshness = True
            if self.parsed_hdrs.has_key('date'):
                freshness_lifetime = self.parsed_hdrs['expires'] - \
                    self.parsed_hdrs['date']
            else:
                freshness_lifetime = self.parsed_hdrs['expires'] - \
                    self.timestamp # ?

        freshness_left = freshness_lifetime - current_age
        freshness_left_str = relative_time(abs(int(freshness_left)), 0, 0)
        freshness_lifetime_str = relative_time(int(freshness_lifetime), 0, 0)

        self.freshness_lifetime = freshness_lifetime
        if freshness_left > 0:
            self.setMessage(" ".join(freshness_hdrs), rs.FRESHNESS_FRESH, 
                             freshness_lifetime=freshness_lifetime_str,
                             freshness_left=freshness_left_str,
                             current_age = current_age_str
                             )
        else:
            self.setMessage(" ".join(freshness_hdrs), rs.FRESHNESS_STALE, 
                             freshness_lifetime=freshness_lifetime_str,
                             freshness_left=freshness_left_str,
                             current_age = current_age_str
                             )

        # can heuristic freshness be used?
        if self.res_status in heuristic_cacheable_status and \
          not has_explicit_freshness:
            self.setMessage('header-last-modified', rs.HEURISTIC_FRESHNESS)

        # can stale responses be served?
        if cc_dict.has_key('must-revalidate'):
            self.stale_serveable = False
            self.setMessage('header-cache-control', rs.STALE_MUST_REVALIDATE) 
        elif cc_dict.has_key('proxy-revalidate') or cc_dict.has_key('s-maxage'):
            self.stale_serveable = False
            self.setMessage('header-cache-control', rs.STALE_PROXY_REVALIDATE) 
        else:
            self.stale_serveable = True
            self.setMessage('header-cache-control', rs.STALE_SERVABLE)

        # public?
        if cc_dict.has_key('public'):
            self.setMessage('header-cache-control', rs.PUBLIC)


class ConnegCheck(RedFetcher):
    """
    See if content negotiation for compression is supported, and how.
    
    Note that this depends on the "main" request being sent with 
    Accept-Encoding: gzip
    """
    def __init__(self, red):
        self.red = red
        if "gzip" in red.parsed_hdrs.get('content-encoding', []):
            req_hdrs = [h for h in red.req_hdrs if
                        h[0].lower() != 'accept-encoding']
            RedFetcher.__init__(self, red.uri, red.method, req_hdrs, red.req_body, 
                                red.status_cb, [], "conneg")
        else:
            self.red.gzip_support = False

    def done(self):
        if self.res_body_len > 0:
            savings = int(100 * ((float(self.res_body_len) - \
                                  self.red.res_body_len) / self.res_body_len))
        else: 
            savings = 0
        self.red.gzip_support = True
        self.red.gzip_savings = savings
        self.red.setMessage('header-content-encoding', rs.CONNEG_GZIP, self,
                             savings=savings,
                             orig_size=self.res_body_len
                             )
        vary_headers = self.red.parsed_hdrs.get('vary', [])
        if (not "accept-encoding" in vary_headers) and (not "*" in vary_headers):
            self.red.setMessage('header-vary header-%s', rs.CONNEG_NO_VARY)
        # FIXME: verify that the status/body/hdrs are the same; if it's different, alert
        no_conneg_vary_headers = self.parsed_hdrs.get('vary', [])
        if 'gzip' in self.parsed_hdrs.get('content-encoding', []):
            self.red.setMessage('header-vary header-content-encoding', 
                                 rs.CONNEG_GZIP_WITHOUT_ASKING)
        if no_conneg_vary_headers != vary_headers:
            self.red.setMessage('header-vary', rs.VARY_INCONSISTENT,
                                 conneg_vary=e(", ".join(vary_headers)),
                                 no_conneg_vary=e(", ".join(no_conneg_vary_headers))
                                 )
        if self.parsed_hdrs.get('etag', 1) == self.red.parsed_hdrs.get('etag', 2):
            self.red.setMessage('header-etag', rs.ETAG_DOESNT_CHANGE) # TODO: weakness?


class RangeRequest(RedFetcher):
    "Check for partial content support (if advertised)"
    def __init__(self, red):
        self.red = red
        if 'bytes' in red.parsed_hdrs.get('accept-ranges', []):
            if len(red.res_body_sample) == 0: return
            sample_num = random.randint(0, len(red.res_body_sample) - 1)
            sample_len = min(96, len(red.res_body_sample[sample_num][1]))
            self.range_start = red.res_body_sample[sample_num][0]
            self.range_end = self.range_start + sample_len
            self.range_target = red.res_body_sample[sample_num][1][:sample_len + 1]
            if self.range_start == self.range_end: return # wow, that's a small body.    
            req_hdrs = red.req_hdrs + [
                    ('Range', "bytes=%s-%s" % (self.range_start, self.range_end))
            ]
            RedFetcher.__init__(self, red.uri, red.method, req_hdrs, red.req_body, 
                                red.status_cb, [], "range")
        else:
            self.red.partial_support = False

    def done(self):
        if self.res_status == '206':
            # TODO: check entity headers
            # TODO: check content-range
            if ('gzip' in self.red.parsed_hdrs.get('content-encoding', [])) == \
               ('gzip' not in self.parsed_hdrs.get('content-encoding', [])):
                self.red.setMessage('header-accept-ranges header-content-encoding', 
                                rs.RANGE_NEG_MISMATCH, self)
                return
            if self.res_body == self.range_target:
                self.red.partial_support = True
                self.red.setMessage('header-accept-ranges', rs.RANGE_CORRECT, self)
            else:
                # the body samples are just bags of bits
                self.red.partial_support = False
                self.red.setMessage('header-accept-ranges', rs.RANGE_INCORRECT, self,
                    range="bytes=%s-%s" % (self.range_start, self.range_end),
                    range_expected=e(self.range_target.encode('string_escape')),
                    range_expected_bytes = len(self.range_target),
                    range_received=e(self.res_body.encode('string_escape')),
                    range_received_bytes = self.res_body_len
                ) 
        # TODO: address 416 directly
        elif self.res_status == self.red.res_status:
            self.red.partial_support = False
            self.red.setMessage('header-accept-ranges', rs.RANGE_FULL)
        else:
            self.red.setMessage('header-accept-ranges', rs.RANGE_STATUS, 
                                range_status=self.res_status,
                                enc_range_status=e(self.res_status))
        
            
class ETagValidate(RedFetcher):
    "If an ETag is present, see if it will validate."
    def __init__(self, red):
        self.red = red
        if red.parsed_hdrs.has_key('etag'):
            weak, etag = red.parsed_hdrs['etag']
            if weak:
                weak_str = "W/"
                # TODO: message on weak etag
            else:
                weak_str = ""
            etag_str = '%s"%s"' % (weak_str, etag)
            req_hdrs = red.req_hdrs + [
                ('If-None-Match', etag_str),
            ]
            RedFetcher.__init__(self, red.uri, red.method, req_hdrs, red.req_body, 
                                red.status_cb, [], "ETag validation")
        else:
            self.red.inm_support = False
            
    def done(self):
        if self.res_status == '304':
            self.red.inm_support = True
            self.red.setMessage('header-etag', rs.INM_304, self)
        elif self.res_status == self.red.res_status:
            if self.res_body_md5 == self.red.res_body_md5:
                self.red.inm_support = False
                self.red.setMessage('header-etag', rs.INM_FULL, self)
            else:
                self.red.setMessage('header-etag', rs.INM_UNKNOWN, self)
        else:
            self.red.setMessage('header-etag', rs.INM_STATUS, self, 
                                inm_status=self.res_status,
                                enc_inm_status=e(self.res_status)
                                )
        # TODO: check entity headers
            
class LmValidate(RedFetcher):
    "If Last-Modified is present, see if it will validate."
    def __init__(self, red):
        self.red = red
        if red.parsed_hdrs.has_key('last-modified'):
            date_str = time.strftime('%a, %d %b %Y %H:%M:%S GMT', 
                                     time.gmtime(red.parsed_hdrs['last-modified']))
            req_hdrs = red.req_hdrs + [
                ('If-Modified-Since', date_str),
            ]
            RedFetcher.__init__(self, red.uri, red.method, req_hdrs, red.req_body, 
                                red.status_cb, [], "LM validation")
        else:
            self.red.ims_support = False

    def done(self):
        if self.res_status == '304':
            self.red.ims_support = True
            self.red.setMessage('header-last-modified', rs.IMS_304, self)
        elif self.res_status == self.red.res_status:
            if self.res_body_md5 == self.red.res_body_md5:
                self.red.ims_support = False
                self.red.setMessage('header-last-modified', rs.IMS_FULL, self)
            else:
                self.red.setMessage('header-last-modified', rs.IMS_UNKNOWN, self)
        else:
            self.red.setMessage('header-last-modified', rs.IMS_STATUS, self, 
                                 ims_status=self.res_status,
                                 enc_ims_status=e(self.res_status)
                                 )
        # TODO: check entity headers
            


if "__main__" == __name__:
    import sys
    uri = sys.argv[1]
    def status_p(msg):
        print msg
    red = ResourceExpertDroid(uri, status_cb=status_p)        
    print red.messages