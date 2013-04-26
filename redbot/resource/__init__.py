#!/usr/bin/env python

"""
The Resource Expert Droid.

RED will examine a HTTP resource for problems and other interesting
characteristics, making a list of these observation notes available
for presentation to the user. It does so by potentially making a number
of requests to probe the resource's behaviour.

See webui.py for the Web front-end.
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

import re
from urlparse import urljoin

import redbot.speak as rs
from redbot import link_parse
from redbot.fetch import RedFetcher
from redbot.formatter import f_num
from redbot.resource import active_check
from redbot.uri_validate import absolute_URI, URI

### configuration
max_uri = 8000

                

class HttpResource(RedFetcher):
    """
    Given a URI (optionally with method, request headers and body), as well
    as an optional status callback and list of body processors, examine the
    URI for issues and notable conditions, making any necessary additional
    requests.

    Note that this primary request negotiates for gzip content-encoding;
    see ConnegCheck.

    After processing the response-specific attributes of RedFetcher will be
    populated, as well as its notes; see that class for details.
    """
    def __init__(self, uri, method="GET", req_hdrs=None, req_body=None,
                status_cb=None, body_procs=None):
        orig_req_hdrs = req_hdrs or []
        rh = orig_req_hdrs + [(u'Accept-Encoding', u'gzip')]
        RedFetcher.__init__(self, uri, method, rh, req_body,
                            status_cb, body_procs, check_type=method)

        # Extra metadata that the "main" RED will be adorned with 
        self.state.orig_req_hdrs = orig_req_hdrs
        self.state.partial_support = None
        self.state.inm_support = None
        self.state.ims_support = None
        self.state.gzip_support = None
        self.state.gzip_savings = 0

        # check the URI
        if not re.match("^\s*%s\s*$" % URI, uri, re.VERBOSE):
            self.state.add_note('uri', rs.URI_BAD_SYNTAX)
        if '#' in uri:
            # chop off the fragment
            uri = uri[:uri.index('#')]
        if len(uri) > max_uri:
            self.state.add_note('uri', 
                rs.URI_TOO_LONG, 
                uri_len=f_num(len(uri))
            )

    def done(self):
        """
        Response is available; perform further processing that's specific to
        the "main" response.
        """
        if self.state.response.complete:
            active_check.spawn_all(self)
            

class InspectingHttpResource(HttpResource):
    """
    A RED that parses the response body to look for links. If descend
    is True, it will also spider linked resources and populate
    self.linked with their HttpResources.
    """
    def __init__(self, uri, method="GET", req_hdrs=None, req_body=None,
                status_cb=None, body_procs=None, descend=False):
        self.link_parser = link_parse.HTMLLinkParser(
            uri, self.process_link, status_cb
        )
        body_procs = ( body_procs or [] ) + [self.link_parser.feed]
        self.descend = descend
        HttpResource.__init__(self, uri, method, req_hdrs, req_body,
                status_cb, body_procs)
        self.state.links = {}          # {type: set(link...)}
        self.state.link_count = 0
        self.state.linked = []    # list of linked HttpResources (if descend=True)
        self.state.base_uri = None        

    def process_link(self, link, tag, title):
        "Handle a link from content"
        state = self.state
        state.link_count += 1
        if not state.links.has_key(tag):
            state.links[tag] = set()
        if self.descend and tag not in ['a'] and link not in state.links[tag]:
            linked = HttpResource(
                urljoin(self.link_parser.base, link),
                req_hdrs=state.orig_req_hdrs,
                status_cb=self.status_cb,
            )
            state.linked.append((linked.state, tag))
            self.add_task(linked.run)
        state.links[tag].add(link)
        if not self.state.base_uri:
            self.state.base_uri = self.link_parser.base



if "__main__" == __name__:
    import sys
    test_uri = sys.argv[1]
    def status_p(msg):
        print msg
    red = InspectingHttpResource(test_uri, status_cb=status_p)
    red.run()
    print red.state.notes
