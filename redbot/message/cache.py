#!/usr/bin/env python

"""
Cacheability checking function. Called on complete responses by RedFetcher.
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

from redbot.formatter import relative_time, f_num
import headers as rh
import redbot.speak as rs

### configuration
cacheable_methods = ['GET']
heuristic_cacheable_status = ['200', '203', '206', '300', '301', '410']
max_clock_skew = 5  # seconds

def checkCaching(state):
    "Examine HTTP caching characteristics."
    
    # TODO: check URI for query string, message about HTTP/1.0 if so

    # get header values
    lm = state.response.parsed_headers.get('last-modified', None)
    date = state.response.parsed_headers.get('date', None)
    cc_set = state.response.parsed_headers.get('cache-control', [])
    cc_list = [k for (k, v) in cc_set]
    cc_dict = dict(cc_set)
    cc_keys = cc_dict.keys()
    
    # Last-Modified
    if lm:
        serv_date = date or state.response.start_time
        if lm > (date or serv_date):
            state.set_message('header-last-modified', rs.LM_FUTURE)
        else:
            state.set_message('header-last-modified', rs.LM_PRESENT,
            last_modified_string=relative_time(lm, serv_date))
    
    # known Cache-Control directives that don't allow duplicates
    known_cc = ["max-age", "no-store", "s-maxage", "public",
                "private", "pre-check", "post-check",
                "stale-while-revalidate", "stale-if-error",
    ]

    # check for mis-capitalised directives /
    # assure there aren't any dup directives with different values
    for cc in cc_keys:
        if cc.lower() in known_cc and cc != cc.lower():
            state.set_message('header-cache-control', rs.CC_MISCAP,
                cc_lower = cc.lower(), cc=cc
            )
        if cc in known_cc and cc_list.count(cc) > 1:
            state.set_message('header-cache-control', rs.CC_DUP,
                cc=cc
            )

    # Who can store this?
    if state.request.method not in cacheable_methods:
        state.store_shared = state.store_private = False
        state.set_message('method', 
            rs.request.method_UNCACHEABLE, 
            method=state.request.method
        )
        return # bail; nothing else to see here
    elif 'no-store' in cc_keys:
        state.store_shared = state.store_private = False
        state.set_message('header-cache-control', rs.NO_STORE)
        return # bail; nothing else to see here
    elif 'private' in cc_keys:
        state.store_shared = False
        state.store_private = True
        state.set_message('header-cache-control', rs.PRIVATE_CC)
    elif 'authorization' in [k.lower() for k, v in state.request.headers] and \
      not 'public' in cc_keys:
        state.store_shared = False
        state.store_private = True
        state.set_message('header-cache-control', rs.PRIVATE_AUTH)
    else:
        state.store_shared = state.store_private = True
        state.set_message('header-cache-control', rs.STOREABLE)

    # no-cache?
    if 'no-cache' in cc_keys:
        if "last-modified" not in state.response.parsed_headers.keys() and \
           "etag" not in state.response.parsed_headers.keys():
            state.set_message('header-cache-control',
                rs.NO_CACHE_NO_VALIDATOR
            )
        else:
            state.set_message('header-cache-control', rs.NO_CACHE)
        return

    # pre-check / post-check
    if 'pre-check' in cc_keys or 'post-check' in cc_keys:
        if 'pre-check' not in cc_keys or 'post-check' not in cc_keys:
            state.set_message('header-cache-control', rs.CHECK_SINGLE)
        else:
            pre_check = post_check = None
            try:
                pre_check = int(cc_dict['pre-check'])
                post_check = int(cc_dict['post-check'])
            except ValueError:
                state.set_message('header-cache-control',
                    rs.CHECK_NOT_INTEGER
                )
            if pre_check is not None and post_check is not None:
                if pre_check == 0 and post_check == 0:
                    state.set_message('header-cache-control',
                        rs.CHECK_ALL_ZERO
                    )
                elif post_check > pre_check:
                    state.set_message('header-cache-control',
                        rs.CHECK_POST_BIGGER
                    )
                    post_check = pre_check
                elif post_check == 0:
                    state.set_message('header-cache-control',
                        rs.CHECK_POST_ZERO
                    )
                else:
                    state.set_message('header-cache-control',
                        rs.CHECK_POST_PRE,
                        pre_check=pre_check,
                        post_check=post_check
                    )

    # vary?
    vary = state.response.parsed_headers.get('vary', set())
    if "*" in vary:
        state.set_message('header-vary', rs.VARY_ASTERISK)
        return # bail; nothing else to see here
    elif len(vary) > 3:
        state.set_message('header-vary', 
            rs.VARY_COMPLEX, 
            vary_count=f_num(len(vary))
        )
    else:
        if "user-agent" in vary:
            state.set_message('header-vary', rs.VARY_USER_AGENT)
        if "host" in vary:
            state.set_message('header-vary', rs.VARY_HOST)
        # TODO: enumerate the axes in a message

    # calculate age
    age_hdr = state.response.parsed_headers.get('age', 0)
    date_hdr = state.response.parsed_headers.get('date', 0)
    if date_hdr > 0:
        apparent_age = max(0,
          int(state.response.start_time - date_hdr))
    else:
        apparent_age = 0
    current_age = max(apparent_age, age_hdr)
    current_age_str = relative_time(current_age, 0, 0)        
    age_str = relative_time(age_hdr, 0, 0)
    state.age = age_hdr
    if age_hdr >= 1:
        state.set_message('header-age header-date', 
            rs.CURRENT_AGE,
            age=age_str
        )

    # Check for clock skew and dateless origin server.
    skew = date_hdr - state.response.start_time + age_hdr
    if not date_hdr:
        state.set_message('', rs.DATE_CLOCKLESS)
        if state.response.parsed_headers.has_key('expires') or \
          state.response.parsed_headers.has_key('last-modified'):
            state.set_message('header-expires header-last-modified', 
                            rs.DATE_CLOCKLESS_BAD_HDR)
    elif age_hdr > max_clock_skew and current_age - skew < max_clock_skew:
        state.set_message('header-date header-age', rs.AGE_PENALTY)
    elif abs(skew) > max_clock_skew:
        state.set_message('header-date', rs.DATE_INCORRECT,
           clock_skew_string=relative_time(skew, 0, 2)
        )
    else:
        state.set_message('header-date', rs.DATE_CORRECT)

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
    elif state.response.parsed_headers.has_key('expires'):
        has_explicit_freshness = True
        freshness_hdrs.append('header-expires')
        if state.response.parsed_headers.has_key('date'):
            freshness_lifetime = state.response.parsed_headers['expires'] - \
                state.response.parsed_headers['date']
        else:
            freshness_lifetime = state.response.parsed_headers['expires'] - \
                state.response.start_time # ?

    freshness_left = freshness_lifetime - current_age
    freshness_left_str = relative_time(abs(int(freshness_left)), 0, 0)
    freshness_lifetime_str = relative_time(int(freshness_lifetime), 0, 0)

    state.freshness_lifetime = freshness_lifetime
    fresh = freshness_left > 0
    if has_explicit_freshness:
        if fresh:
            state.set_message(" ".join(freshness_hdrs), rs.FRESHNESS_FRESH,
                 freshness_lifetime=freshness_lifetime_str,
                 freshness_left=freshness_left_str,
                 current_age = current_age_str
            )
        elif has_cc_freshness and state.age > freshness_lifetime:
            state.set_message(" ".join(freshness_hdrs),
                rs.FRESHNESS_STALE_CACHE,
                freshness_lifetime=freshness_lifetime_str,
                freshness_left=freshness_left_str,
                current_age = current_age_str
            )
        else:
            state.set_message(" ".join(freshness_hdrs),
                rs.FRESHNESS_STALE_ALREADY,
                freshness_lifetime=freshness_lifetime_str,
                freshness_left=freshness_left_str,
                current_age = current_age_str
            )

    # can heuristic freshness be used?
    elif state.response.status_code in heuristic_cacheable_status:
        state.set_message('header-last-modified', rs.FRESHNESS_HEURISTIC)
    else:
        state.set_message('', rs.FRESHNESS_NONE)

    # can stale responses be served?
    if 'must-revalidate' in cc_keys:
        if fresh:
            state.set_message('header-cache-control',
                rs.FRESH_MUST_REVALIDATE
        )
        elif has_explicit_freshness:
            state.set_message('header-cache-control',
                rs.STALE_MUST_REVALIDATE
            )
    elif 'proxy-revalidate' in cc_keys or 's-maxage' in cc_keys:
        if fresh:
            state.set_message('header-cache-control',
                rs.FRESH_PROXY_REVALIDATE
            )
        elif has_explicit_freshness:
            state.set_message('header-cache-control',
                rs.STALE_PROXY_REVALIDATE
            )
    else:
        if fresh:
            state.set_message('header-cache-control', rs.FRESH_SERVABLE)
        elif has_explicit_freshness:
            state.set_message('header-cache-control', rs.STALE_SERVABLE)

    # public?
    if 'public' in cc_keys: # TODO: check for authentication in request
        state.set_message('header-cache-control', rs.PUBLIC)
