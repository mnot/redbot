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

import re
from cgi import escape as e
from urlparse import urljoin

import redbot.speak as rs
from redbot import link_parse
from redbot.fetch import RedFetcher
from redbot.response_analyse import relative_time, f_num
from redbot.subreq import ConnegCheck, RangeRequest, ETagValidate, LmValidate
from redbot.uri_validate import absolute_URI

### configuration
cacheable_methods = ['GET']
heuristic_cacheable_status = ['200', '203', '206', '300', '301', '410']
max_uri = 8000
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
        orig_req_hdrs = req_hdrs or []
        rh = orig_req_hdrs + [('Accept-Encoding', 'gzip')]
        RedFetcher.__init__(self, uri, method, rh, req_body,
                            status_cb, body_procs, req_type=method)

        # Extra metadata that the "main" RED will be adorned with 
        self.state.orig_req_hdrs = orig_req_hdrs
        self.state.age = None
        self.state.store_shared = None
        self.state.store_private = None
        self.state.freshness_lifetime = None
        self.state.stale_serveable = None
        self.state.partial_support = None
        self.state.inm_support = None
        self.state.ims_support = None
        self.state.gzip_support = None
        self.state.gzip_savings = 0

        # check the URI
        if not re.match("^\s*%s\s*$" % absolute_URI, uri, re.VERBOSE):
            self.state.setMessage('uri', rs.URI_BAD_SYNTAX)
        if len(uri) > max_uri:
            self.state.setMessage('uri', 
                rs.URI_TOO_LONG, 
                uri_len=f_num(len(uri))
            )

    def done(self):
        """
        Response is available; perform further processing that's specific to
        the "main" response.
        """
        if self.state.res_complete:
            self.checkCaching()
            self.add_task(ConnegCheck(self, 'Accept-Encoding').run)
            self.add_task(RangeRequest(self, 'Range').run)
            self.add_task(ETagValidate(self, 'ETag').run)
            self.add_task(LmValidate(self, 'Last-Modified').run)
                
    def checkCaching(self):
        "Examine HTTP caching characteristics."
        
        state = self.state
        # TODO: check URI for query string, message about HTTP/1.0 if so
        # known Cache-Control directives that don't allow duplicates
        known_cc = ["max-age", "no-store", "s-maxage", "public",
                    "private", "pre-check", "post-check",
                    "stale-while-revalidate", "stale-if-error",
        ]

        cc_set = state.parsed_hdrs.get('cache-control', [])
        cc_list = [k for (k,v) in cc_set]
        cc_dict = dict(cc_set)
        cc_keys = cc_dict.keys()

        # check for mis-capitalised directives /
        # assure there aren't any dup directives with different values
        for cc in cc_keys:
            if cc.lower() in known_cc and cc != cc.lower():
                state.setMessage('header-cache-control', rs.CC_MISCAP,
                    cc_lower = cc.lower(), cc=cc
                )
            if cc in known_cc and cc_list.count(cc) > 1:
                state.setMessage('header-cache-control', rs.CC_DUP,
                    cc=cc
                )

        # Who can store this?
        if state.method not in cacheable_methods:
            state.store_shared = state.store_private = False
            state.setMessage('method', 
                rs.METHOD_UNCACHEABLE, 
                method=self.method
            )
            return # bail; nothing else to see here
        elif 'no-store' in cc_keys:
            state.store_shared = state.store_private = False
            state.setMessage('header-cache-control', rs.NO_STORE)
            return # bail; nothing else to see here
        elif 'private' in cc_keys:
            state.store_shared = False
            state.store_private = True
            state.setMessage('header-cache-control', rs.PRIVATE_CC)
        elif 'authorization' in [k.lower() for k, v in state.req_hdrs] and \
          not 'public' in cc_keys:
            state.store_shared = False
            state.store_private = True
            state.setMessage('header-cache-control', rs.PRIVATE_AUTH)
        else:
            state.store_shared = state.store_private = True
            state.setMessage('header-cache-control', rs.STOREABLE)

        # no-cache?
        if 'no-cache' in cc_keys:
            if "last-modified" not in state.parsed_hdrs.keys() and \
               "etag" not in state.parsed_hdrs.keys():
                state.setMessage('header-cache-control',
                    rs.NO_CACHE_NO_VALIDATOR
                )
            else:
                state.setMessage('header-cache-control', rs.NO_CACHE)
            return

        # pre-check / post-check
        if 'pre-check' in cc_keys or 'post-check' in cc_keys:
            if 'pre-check' not in cc_keys or 'post_check' not in cc_keys:
                state.setMessage('header-cache-control', rs.CHECK_SINGLE)
            else:
                pre_check = post_check = None
                try:
                    pre_check = int(cc_dict['pre-check'])
                    post_check = int(cc_dict['post-check'])
                except ValueError:
                    state.setMessage('header-cache-control',
                        rs.CHECK_NOT_INTEGER
                    )
                if pre_check is not None and post_check is not None:
                    if pre_check == 0 and post_check == 0:
                        state.setMessage('header-cache-control',
                            rs.CHECK_ALL_ZERO
                        )
                    elif post_check > pre_check:
                        state.setMessage('header-cache-control',
                            rs.CHECK_POST_BIGGER
                        )
                        post_check = pre_check
                    elif post_check == 0:
                        state.setMessage('header-cache-control',
                            rs.CHECK_POST_ZERO
                        )
                    else:
                        state.setMessage('header-cache-control',
                            rs.CHECK_POST_PRE,
                            pre_check=pre_check,
                            post_check=post_check
                        )

        # vary?
        vary = state.parsed_hdrs.get('vary', set())
        if "*" in vary:
            state.setMessage('header-vary', rs.VARY_ASTERISK)
            return # bail; nothing else to see here
        elif len(vary) > 3:
            state.setMessage('header-vary', 
                rs.VARY_COMPLEX, 
                vary_count=f_num(len(vary))
            )
        else:
            if "user-agent" in vary:
                state.setMessage('header-vary', rs.VARY_USER_AGENT)
            if "host" in vary:
                state.setMessage('header-vary', rs.VARY_HOST)
            # TODO: enumerate the axes in a message

        # calculate age
        age_hdr = state.parsed_hdrs.get('age', 0)
        date_hdr = state.parsed_hdrs.get('date', 0)
        if date_hdr > 0:
            apparent_age = max(0,
              int(self.state.res_ts - date_hdr))
        else:
            apparent_age = 0
        current_age = max(apparent_age, age_hdr)
        current_age_str = relative_time(current_age, 0, 0)        
        age_str = relative_time(age_hdr, 0, 0)
        self.age = age_hdr
        if age_hdr >= 1:
            state.setMessage('header-age header-date', 
                rs.CURRENT_AGE,
                age=age_str
            )

        # Check for clock skew and dateless origin server.
        skew = date_hdr - self.state.res_ts + age_hdr
        if not date_hdr:
            state.setMessage('', rs.DATE_CLOCKLESS)
            if state.parsed_hdrs.has_key('expires') or \
              state.parsed_hdrs.has_key('last-modified'):
                state.setMessage('header-expires header-last-modified', 
                                rs.DATE_CLOCKLESS_BAD_HDR)
        elif age_hdr > max_clock_skew and current_age - skew < max_clock_skew:
            state.setMessage('header-date header-age', rs.AGE_PENALTY)
        elif abs(skew) > max_clock_skew:
            state.setMessage('header-date', rs.DATE_INCORRECT,
               clock_skew_string=relative_time(skew, 0, 2)
            )
        else:
            state.setMessage('header-date', rs.DATE_CORRECT)

        # calculate freshness
        freshness_lifetime = 0
        has_explicit_freshness = False
        has_cc_freshness = False
        freshness_hdrs = ['header-date']
        if 's-maxage' in cc_keys: # TODO: differentiate message for s-maxage
            freshness_lifetime = cc_dict['s-maxage']
            freshness_hdrs.append('header-cache-control')
            has_explicit_freshness = True
            has_cc_freshness = True
        elif 'max-age' in cc_keys:
            freshness_lifetime = cc_dict['max-age']
            freshness_hdrs.append('header-cache-control')
            has_explicit_freshness = True
            has_cc_freshness = True
        elif state.parsed_hdrs.has_key('expires'):
            has_explicit_freshness = True
            freshness_hdrs.append('header-expires')
            if state.parsed_hdrs.has_key('date'):
                freshness_lifetime = state.parsed_hdrs['expires'] - \
                    state.parsed_hdrs['date']
            else:
                freshness_lifetime = state.parsed_hdrs['expires'] - \
                    state.res_ts # ?

        freshness_left = freshness_lifetime - current_age
        freshness_left_str = relative_time(abs(int(freshness_left)), 0, 0)
        freshness_lifetime_str = relative_time(int(freshness_lifetime), 0, 0)

        state.freshness_lifetime = freshness_lifetime
        fresh = freshness_left > 0
        if has_explicit_freshness:
            if fresh:
                state.setMessage(" ".join(freshness_hdrs), rs.FRESHNESS_FRESH,
                     freshness_lifetime=freshness_lifetime_str,
                     freshness_left=freshness_left_str,
                     current_age = current_age_str
                )
            elif has_cc_freshness and state.age > freshness_lifetime:
                state.setMessage(" ".join(freshness_hdrs),
                    rs.FRESHNESS_STALE_CACHE,
                    freshness_lifetime=freshness_lifetime_str,
                    freshness_left=freshness_left_str,
                    current_age = current_age_str
                )
            else:
                state.setMessage(" ".join(freshness_hdrs),
                    rs.FRESHNESS_STALE_ALREADY,
                    freshness_lifetime=freshness_lifetime_str,
                    freshness_left=freshness_left_str,
                    current_age = current_age_str
                )

        # can heuristic freshness be used?
        elif state.res_status in heuristic_cacheable_status:
            state.setMessage('header-last-modified', rs.FRESHNESS_HEURISTIC)
        else:
            state.setMessage('', rs.FRESHNESS_NONE)

        # can stale responses be served?
        if 'must-revalidate' in cc_keys:
            if fresh:
                state.setMessage('header-cache-control',
                    rs.FRESH_MUST_REVALIDATE
            )
            elif has_explicit_freshness:
                state.setMessage('header-cache-control',
                    rs.STALE_MUST_REVALIDATE
                )
        elif 'proxy-revalidate' in cc_keys or 's-maxage' in cc_keys:
            if fresh:
                state.setMessage('header-cache-control',
                    rs.FRESH_PROXY_REVALIDATE
                )
            elif has_explicit_freshness:
                state.setMessage('header-cache-control',
                    rs.STALE_PROXY_REVALIDATE
                )
        else:
            if fresh:
                state.setMessage('header-cache-control', rs.FRESH_SERVABLE)
            elif has_explicit_freshness:
                state.setMessage('header-cache-control', rs.STALE_SERVABLE)

        # public?
        if 'public' in cc_keys: # TODO: check for authentication in request
            state.setMessage('header-cache-control', rs.PUBLIC)



class InspectingResourceExpertDroid(ResourceExpertDroid):
    """
    A RED that parses the response body to look for links. If descend
    is True, it will also spider linked resources and populate
    self.link_droids with their REDs.
    """
    def __init__(self, uri, method="GET", req_hdrs=None, req_body=None,
                status_cb=None, body_procs=None, descend=False):
        self.link_parser = link_parse.HTMLLinkParser(
            uri, self.process_link, status_cb
        )
        body_procs = ( body_procs or [] ) + [self.link_parser.feed]
        self.descend = descend
        ResourceExpertDroid.__init__(self, uri, method, req_hdrs, req_body,
                status_cb, body_procs)
        self.state.links = {}          # {type: set(link...)}
        self.state.link_count = 0
        self.state.link_droids = []    # list of linked REDs (if descend=True)
        self.state.base_uri = None        

    def process_link(self, link, tag, title):
        "Handle a link from content"
        state = self.state
        state.link_count += 1
        if not state.links.has_key(tag):
            state.links[tag] = set()
        if self.descend and tag not in ['a'] and link not in state.links[tag]:
            link_droid = ResourceExpertDroid(
                urljoin(self.link_parser.base, link),
                req_hdrs=state.orig_req_hdrs,
                status_cb=self.status_cb,
            )
            state.link_droids.append((link_droid.state, tag))
            self.add_task(link_droid.run)
        state.links[tag].add(link)
        if not self.state.base_uri:
            self.state.base_uri = self.link_parser.base



if "__main__" == __name__:
    import sys
    uri = sys.argv[1]
    def status_p(msg):
        print msg
    red = InspectingResourceExpertDroid(uri, status_cb=status_p)
    red.run()
    print red.messages
