#!/usr/bin/env python

"""
The Resource Expert Droid.

RED will examine a HTTP resource for problems and other interesting
characteristics, making a list of these observation notes available
for presentation to the user. It does so by potentially making a number
of requests to probe the resource's behaviour.

See webui.py for the Web front-end.
"""

from urlparse import urljoin

import thor

from redbot.formatter import f_num
from redbot.message import link_parse
from redbot.resource.fetch import RedFetcher, UA_STRING
from redbot.resource import active_check



class HttpResource(RedFetcher):
    """
    Given a URI (optionally with method, request headers and body), examine the URI for issues and
    notable conditions, making any necessary additional requests.

    Note that this primary request negotiates for gzip content-encoding; see ConnegCheck.

    After processing the response-specific attributes of RedFetcher will be populated, as well as
    its notes; see that class for details.
    
    if descend is true, the response will be parsed for links and HttpResources started for each
    link, enumerated in .linked.
  
    Emits "done" when everything has finished.
    """
    def __init__(self, uri, method="GET", req_hdrs=None, req_body=None, descend=False):
        orig_req_hdrs = req_hdrs or []
        new_req_hdrs = orig_req_hdrs + [(u'Accept-Encoding', u'gzip')]
        RedFetcher.__init__(self, uri, method, new_req_hdrs, req_body, name=method)
        self.descend = descend
        self.subreqs = {}  # subordinate requests
        self.links = {}    # {type: set(link...)}
        self.link_count = 0
        self.linked = []   # list of linked HttpResources (if descend=True)
        self.orig_req_hdrs = orig_req_hdrs
        self.partial_support = None
        self.inm_support = None
        self.ims_support = None
        self.gzip_support = None
        self.gzip_savings = 0
        self._outstanding_tasks = 1
        self.response.on("content_available", self.active_checks)
        self.on("fetch_done", self.finish_check)
        self._link_parser = link_parse.HTMLLinkParser(self.response.base_uri,
                                                      [self.process_link])
        self.response.on("chunk", self._link_parser.feed)

    def active_checks(self):
        """
        Response is available; perform further processing that's specific to
        the "main" response.
        """
        if self.response.complete:
            active_check.start(self)

    def add_check(self, *resources):
        "Do a subordinate check on one or more HttpResource instance."
        for resource in resources:
            self._outstanding_tasks += 1
            self._st.append('add_check(%s)' % str(resource))
            @thor.events.on(resource)
            def done():
                self.finish_check()

    def finish_check(self):
        self._outstanding_tasks -= 1
        self._st.append('finish_check')
        assert self._outstanding_tasks >= 0, self._st
        if self._outstanding_tasks == 0:
            self.emit('done')

    def process_link(self, base, link, tag, title):
        "Handle a link from content"
        self.link_count += 1
        if not self.links.has_key(tag):
            self.links[tag] = set()
        if self.descend and tag not in ['a'] and link not in self.links[tag]:
            linked = HttpResource(
                urljoin(base, link),
                req_hdrs=self.orig_req_hdrs,
            )
            self.linked.append((linked, tag))
            self.add_check(linked)
            linked.check()
        self.links[tag].add(link)
        if not self.response.base_uri:
            self.response.base_uri = base


if __name__ == "__main__":
    import sys
    RED = HttpResource(sys.argv[1])
    @thor.events.on(RED)
    def status(msg):
        print msg
    @thor.events.on(RED)
    def done():
        print 'done'
        thor.stop()
    RED.check()
    thor.run()
    print RED.notes
