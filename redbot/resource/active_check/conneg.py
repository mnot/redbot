#!/usr/bin/env python

"""
Subrequest for content negotiation checks.
"""


from redbot.resource.active_check.base import SubRequest
from redbot.formatter import f_num
import redbot.speak as rs

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
            self.add_note('', rs.CONNEG_SUBREQ_PROBLEM,
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
                            rs.CONNEG_GZIP_WITHOUT_ASKING)
        else: # Apparently, content negotiation is happening.

            # check status
            if self.base.response.status_code != \
               self.response.status_code:
                self.add_note('status', rs.VARY_STATUS_MISMATCH, 
                  neg_status=self.base.response.status_code,
                  noneg_status=self.response.status_code)
                return  # Can't be sure what's going on...

            # check headers that should be invariant
            for hdr in ['content-type']:
                if self.base.response.parsed_headers.get(hdr) != \
                  self.response.parsed_headers.get(hdr, None):
                    self.add_note('header-%s' % hdr,
                      rs.VARY_HEADER_MISMATCH, 
                      header=hdr)
                    # TODO: expose on-the-wire values.

            # check Vary headers
            vary_headers = self.base.response.parsed_headers.get('vary', [])
            if (not "accept-encoding" in vary_headers) and \
               (not "*" in vary_headers):
                self.add_note('header-vary', rs.CONNEG_NO_VARY)
            if no_conneg_vary_headers != vary_headers:
                self.add_note('header-vary', 
                    rs.VARY_INCONSISTENT,
                    conneg_vary=", ".join(vary_headers),
                    no_conneg_vary=", ".join(no_conneg_vary_headers)
                )

            # check body
            if self.base.response.decoded_md5 != \
               self.response.payload_md5:
                self.add_note('body', rs.VARY_BODY_MISMATCH)

            # check ETag
            if (self.response.parsed_headers.get('etag', 1) == \
              self.base.response.parsed_headers.get('etag', 2)):
                if not self.base.response.parsed_headers['etag'][0]: # strong
                    self.add_note('header-etag',
                        rs.VARY_ETAG_DOESNT_CHANGE
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
                    rs.CONNEG_GZIP_GOOD,
                    savings=savings,
                    orig_size=f_num(self.response.payload_len),
                    gzip_size=f_num(self.base.response.payload_len)
                )
            else:
                self.add_note('header-content-encoding',
                    rs.CONNEG_GZIP_BAD,
                    savings=abs(savings),
                    orig_size=f_num(self.response.payload_len),
                    gzip_size=f_num(self.base.response.payload_len)
                )