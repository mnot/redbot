#!/usr/bin/env python

"""
Subrequest for content negotiation checks.
"""


from redbot.resource.active_check.base import SubRequest
from redbot.formatter import f_num
from redbot.speak import Note, categories, levels


class ConnegCheck(SubRequest):
    """
    See if content negotiation for compression is supported, and how.

    Note that this depends on the "main" request being sent with
    Accept-Encoding: gzip
    """
    def modify_req_hdrs(self):
        return [h for h in self.base.orig_req_hdrs 
                  if h[0].lower() != 'accept-encoding'] + \
               [(u'accept-encoding', u'identity')]

    def preflight(self):
        if "gzip" in \
          self.base.response.parsed_headers.get('content-encoding', []):
            return True
        else:
            self.base.gzip_support = False
            return False

    def done(self):
        if not self.response.complete:
            self.add_note('', CONNEG_SUBREQ_PROBLEM,
                problem=self.response.http_error.desc
            )
            return
            
        # see if it was compressed when not negotiated
        no_conneg_vary_headers = \
          self.response.parsed_headers.get('vary', [])
        if 'gzip' in \
          self.response.parsed_headers.get('content-encoding', []) \
          or 'x-gzip' in \
          self.response.parsed_headers.get('content-encoding', []):
            self.add_note('header-vary header-content-encoding',
                            CONNEG_GZIP_WITHOUT_ASKING)
        else: # Apparently, content negotiation is happening.

            # check status
            if self.base.response.status_code != \
               self.response.status_code:
                self.add_note('status', VARY_STATUS_MISMATCH, 
                  neg_status=self.base.response.status_code,
                  noneg_status=self.response.status_code)
                return  # Can't be sure what's going on...

            # check headers that should be invariant
            for hdr in ['content-type']:
                if self.base.response.parsed_headers.get(hdr) != \
                  self.response.parsed_headers.get(hdr, None):
                    self.add_note('header-%s' % hdr,
                      VARY_HEADER_MISMATCH, 
                      header=hdr)
                    # TODO: expose on-the-wire values.

            # check Vary headers
            vary_headers = self.base.response.parsed_headers.get('vary', [])
            if (not "accept-encoding" in vary_headers) and \
               (not "*" in vary_headers):
                self.add_note('header-vary', CONNEG_NO_VARY)
            if no_conneg_vary_headers != vary_headers:
                self.add_note('header-vary', 
                    VARY_INCONSISTENT,
                    conneg_vary=", ".join(vary_headers),
                    no_conneg_vary=", ".join(no_conneg_vary_headers)
                )

            # check body
            if self.base.response.decoded_md5 != \
               self.response.payload_md5:
                self.add_note('body', VARY_BODY_MISMATCH)

            # check ETag
            if (self.response.parsed_headers.get('etag', 1) == \
              self.base.response.parsed_headers.get('etag', 2)):
                if not self.base.response.parsed_headers['etag'][0]: # strong
                    self.add_note('header-etag',
                        VARY_ETAG_DOESNT_CHANGE
                    ) 

            # check compression efficiency
            if self.response.payload_len > 0:
                savings = int(100 * 
                    (
                        (float(self.response.payload_len) - \
                        self.base.response.payload_len
                        ) / self.response.payload_len
                    )
                )
            else:
                savings = 0
            self.base.gzip_support = True
            self.base.gzip_savings = savings
            if savings >= 0:
                self.add_note('header-content-encoding',
                    CONNEG_GZIP_GOOD,
                    savings=savings,
                    orig_size=f_num(self.response.payload_len),
                    gzip_size=f_num(self.base.response.payload_len)
                )
            else:
                self.add_note('header-content-encoding',
                    CONNEG_GZIP_BAD,
                    savings=abs(savings),
                    orig_size=f_num(self.response.payload_len),
                    gzip_size=f_num(self.base.response.payload_len)
                )
                

class CONNEG_SUBREQ_PROBLEM(Note):
    category = categories.CONNEG
    level = levels.BAD
    summary = u"There was a problem checking for Content Negotiation support."
    text = u"""\
When RED tried to check the resource for content negotiation support, there was a problem:

`%(problem)s`

Trying again might fix it."""

class CONNEG_GZIP_GOOD(Note):
    category = categories.CONNEG
    level = levels.GOOD
    summary = u'Content negotiation for gzip compression is supported, saving %(savings)s%%.'
    text = u"""\
HTTP supports compression of responses by negotiating for `Content-Encoding`. When RED asked for a
compressed response, the resource provided one, saving %(savings)s%% of its original size (from
%(orig_size)s to %(gzip_size)s bytes).

The compressed response's headers are displayed."""

class CONNEG_GZIP_BAD(Note):
    category = categories.CONNEG
    level = levels.WARN
    summary = u'Content negotiation for gzip compression makes the response %(savings)s%% larger.'
    text = u"""\
HTTP supports compression of responses by negotiating for `Content-Encoding`. When RED asked for a
compressed response, the resource provided one, but it was %(savings)s%% _larger_ than the original
response; from %(orig_size)s to %(gzip_size)s bytes.

Often, this happens when the uncompressed response is very small, or can't be compressed more;
since gzip compression has some overhead, it can make the response larger. Turning compression
**off** for this resource may slightly improve response times and save bandwidth.

The compressed response's headers are displayed."""

class CONNEG_NO_GZIP(Note):
    category = categories.CONNEG
    level = levels.INFO
    summary = u'Content negotiation for gzip compression isn\'t supported.'
    text = u"""\
HTTP supports compression of responses by negotiating for `Content-Encoding`. When RED asked for a
compressed response, the resource did not provide one."""

class CONNEG_NO_VARY(Note):
    category = categories.CONNEG
    level = levels.BAD
    summary = u"%(response)s is negotiated, but doesn't have an appropriate Vary header."
    text = u"""\
All content negotiated responses need to have a `Vary` header that reflects the header(s) used to
select the response.

%(response)s was negotiated for `gzip` content encoding, so the `Vary` header needs to contain
`Accept-Encoding`, the request header used."""

class CONNEG_GZIP_WITHOUT_ASKING(Note):
    category = categories.CONNEG
    level = levels.WARN
    summary = u"A gzip-compressed response was sent when it wasn't asked for."
    text = u"""\
HTTP supports compression of responses by negotiating for `Content-Encoding`. Even though RED
didn't ask for a compressed response, the resource provided one anyway.

It could be that the response is always compressed, but doing so can break clients that aren't
expecting a compressed response."""

class VARY_INCONSISTENT(Note):
    category = categories.CONNEG
    level = levels.BAD
    summary = u"The resource doesn't send Vary consistently."
    text = u"""\
HTTP requires that the `Vary` response header be sent consistently for all responses if they change
based upon different aspects of the request.

This resource has both compressed and uncompressed variants available, negotiated by the
`Accept-Encoding` request header, but it sends different Vary headers for each;

* "`%(conneg_vary)s`" when the response is compressed, and
* "`%(no_conneg_vary)s`" when it is not.

This can cause problems for downstream caches, because they cannot consistently determine what the
cache key for a given URI is."""

class VARY_STATUS_MISMATCH(Note):
    category = categories.CONNEG
    level = levels.WARN
    summary = u"The response status is different when content negotiation happens."
    text = u"""\
When content negotiation is used, the response status shouldn't change between negotiated and
non-negotiated responses.

When RED send asked for a negotiated response, it got a `%(neg_status)s` status code; when it
didn't, it got `%(noneg_status)s`.

RED hasn't checked other aspects of content negotiation because of this."""
    
class VARY_HEADER_MISMATCH(Note):
    category = categories.CONNEG
    level = levels.BAD
    summary = u"The %(header)s header is different when content negotiation happens."
    text = u"""\
When content negotiation is used, the %(header)s response header shouldn't change between
negotiated and non-negotiated responses."""

class VARY_BODY_MISMATCH(Note):
    category = categories.CONNEG
    level = levels.INFO
    summary = u"The response body is different when content negotiation happens."
    text = u"""\
When content negotiation is used, the response body typically shouldn't change between negotiated
and non-negotiated responses.

There might be legitimate reasons for this; e.g., because different servers handled the two
requests. However, RED's output may be skewed as a result."""

class VARY_ETAG_DOESNT_CHANGE(Note):
    category = categories.CONNEG
    level = levels.BAD
    summary = u"The ETag doesn't change between negotiated representations."
    text = u"""\
HTTP requires that the `ETag`s for two different responses associated with the same URI be
different as well, to help caches and other receivers disambiguate them.

This resource, however, sent the same strong ETag for both its compressed and uncompressed versions
(negotiated by `Accept-Encoding`). This can cause interoperability problems, especially with caches.

Please note that some versions of the Apache HTTP Server sometimes send the same ETag for both
compressed and uncompressed versions of a ressource. This is a [known
bug](https://issues.apache.org/bugzilla/show_bug.cgi?id=39727)."""
