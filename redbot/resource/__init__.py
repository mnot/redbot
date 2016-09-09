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

from redbot.resource.fetch import RedFetcher, UA_STRING
from redbot.formatter import f_num
from redbot.resource import active_check


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
                 status_cb=None, body_procs=None, descend=False):
        orig_req_hdrs = req_hdrs or []
        new_req_hdrs = orig_req_hdrs + [(u'Accept-Encoding', u'gzip')]
        RedFetcher.__init__(self, uri, method, new_req_hdrs, req_body,
                            status_cb, body_procs, name=method)
        self.descend = descend
        self.response.set_link_procs([self.process_link])
        self.links = {}          # {type: set(link...)}
        self.link_count = 0
        self.linked = []    # list of linked HttpResources (if descend=True)
        self.orig_req_hdrs = orig_req_hdrs
        self.partial_support = None
        self.inm_support = None
        self.ims_support = None
        self.gzip_support = None
        self.gzip_savings = 0

    def done(self):
        """
        Response is available; perform further processing that's specific to
        the "main" response.
        """
        if self.response.complete:
            active_check.spawn_all(self)

    def process_link(self, base, link, tag, title):
        "Handle a link from content"
        self.link_count += 1
        if not self.links.has_key(tag):
            self.links[tag] = set()
        if self.descend and tag not in ['a'] and link not in self.links[tag]:
            linked = HttpResource(
                urljoin(base, link),
                req_hdrs=self.orig_req_hdrs,
                status_cb=self.status_cb,
            )
            self.linked.append((linked, tag))
            self.add_task(linked.run)
        self.links[tag].add(link)
        if not self.response.base_uri:
            self.response.base_uri = base


if __name__ == "__main__":
    import sys
    def status_p(msg):
        'print the status message'
        print msg
    RED = HttpResource(sys.argv[1], status_cb=status_p)
    RED.run()
    print RED.notes
