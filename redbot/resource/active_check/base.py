#!/usr/bin/env python

"""
Subrequests to do things like range requests, content negotiation checks,
and validation.

This is the base class for all subrequests.
"""


from redbot.resource.fetch import RedFetcher
from redbot.speak import Note, levels, categories


class SubRequest(RedFetcher):
    """
    Base class for a subrequest of a "main" HttpResource, made to perform
    additional behavioural tests on the resource.
    """
    check_name = u"undefined"
    response_phrase = u"undefined"
    
    def __init__(self, base_resource):
        self.base = base_resource
        req_hdrs = self.modify_req_hdrs()
        RedFetcher.__init__(self,
                            self.base.request.uri,
                            self.base.request.method,
                            req_hdrs,
                            self.base.request.payload)
        if self.preflight():
            self.base.subreqs[self.check_name] = self
            self.on('fetch_done', self.done)
        self.on('fetch_done', self.subrequest_done)
        self.on('status', self.status)

    def status(self, msg):
        self.base.emit('status', msg)

    def done(self):
        raise NotImplementedError

    def subrequest_done(self):
        self.emit("done")

    def modify_req_hdrs(self):
        """
        Usually overidden; modifies the request's headers.

        Make sure it returns a copy of the orignals, not them.
        """
        return list(self.base.orig_req_hdrs)

    def add_base_note(self, subject, note, **kw):
        "Add a Note to the base resource."
        self.base.add_note(subject, note, **kw)

    def check_missing_hdrs(self, hdrs, note, subreq_type):
        """
        See if the listed headers are missing in the subrequest; if so,
        set the specified note.
        """
        missing_hdrs = []
        for hdr in hdrs:
            if self.base.response.parsed_headers.has_key(hdr) \
            and not self.response.parsed_headers.has_key(hdr):
                missing_hdrs.append(hdr)
        if missing_hdrs:
            self.add_note('headers', note,
                          missing_hdrs=", ".join(missing_hdrs),
                          subreq_type=subreq_type)


class MISSING_HDRS_304(Note):
    category = categories.VALIDATION
    level = levels.WARN
    summary = u"The %(subreq_type)s response is missing required headers."
    text = u"""\
HTTP requires `304 Not Modified` responses to have certain headers, if they are also present in a
normal (e.g., `200 OK` response).

%(response)s is missing the following headers: `%(missing_hdrs)s`.

This can affect cache operation; because the headers are missing, caches might remove them from
their cached copies."""