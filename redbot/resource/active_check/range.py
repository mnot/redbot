#!/usr/bin/env python

"""
Subrequest for partial content checks.
"""

import random

from redbot.resource.active_check.base import SubRequest
from redbot.formatter import f_num
import redbot.speak as rs

class RangeRequest(SubRequest):
    "Check for partial content support (if advertised)"

    def __init__(self, red, name):
        self.range_start = None
        self.range_end = None
        self.range_target = None
        SubRequest.__init__(self, red, name)
        
    def modify_req_hdrs(self):
        req_hdrs = list(self.base.request.headers)
        if len(self.base.response.payload_sample) != 0:
            sample_num = random.randint(
                0, 
                len(self.base.response.payload_sample) - 1
            )
            sample_len = min(
                96, 
                len(self.base.response.payload_sample[sample_num][1])
            )
            self.range_start = \
              self.base.response.payload_sample[sample_num][0]
            self.range_end = self.range_start + sample_len
            self.range_target = \
              self.base.response.payload_sample[sample_num][1] \
                [:sample_len + 1]
            # TODO: uses the compressed version (if available). Revisit.
            req_hdrs += [
                (u'Range', u"bytes=%s-%s" % (
                    self.range_start, self.range_end
                ))
            ]
        return req_hdrs
        
    def preflight(self):
        if 'bytes' in \
          self.base.response.parsed_headers.get('accept-ranges', []):
            if len(self.base.response.payload_sample) == 0:
                return False
            if self.range_start == self.range_end: 
                # wow, that's a small body.
                return False
            return True
        else:
            self.base.partial_support = False
            return False

    def done(self):
        if not self.response.complete:
            self.add_note('', RANGE_SUBREQ_PROBLEM,
                problem=self.response.http_error.desc
            )
            return
            
        if self.response.status_code == '206':
            c_e = 'content-encoding'
            if 'gzip' in self.base.response.parsed_headers.get(c_e, []) == \
               'gzip' not in self.response.parsed_headers.get(c_e, []):
                self.add_note(
                    'header-accept-ranges header-content-encoding',
                    RANGE_NEG_MISMATCH
                )
                return
            if not [True for h in self.base.orig_req_hdrs 
                if h[0].lower() == 'if-range']:
                self.check_missing_hdrs([
                        'date', 'cache-control', 'content-location', 'etag', 
                        'expires', 'vary'
                    ], MISSING_HDRS_206, 'Range'
                )
            if self.response.parsed_headers.get('etag', 1) == \
              self.base.response.parsed_headers.get('etag', 2):
                if self.response.payload == self.range_target:
                    self.base.partial_support = True
                    self.add_note('header-accept-ranges', RANGE_CORRECT)
                else:
                    # the body samples are just bags of bits
                    self.base.partial_support = False
                    self.add_note('header-accept-ranges',
                        RANGE_INCORRECT,
                        range="bytes=%s-%s" % (
                            self.range_start, self.range_end
                        ),
                        range_expected = \
                          self.range_target.encode('string_escape'),
                        range_expected_bytes = f_num(len(self.range_target)),
                        range_received = \
                          self.response.payload.encode('string_escape'),
                        range_received_bytes = \
                          f_num(self.response.payload_len)
                    )
            else:
                self.add_note('header-accept-ranges', RANGE_CHANGED)

        # TODO: address 416 directly
        elif self.response.status_code == \
          self.base.response.status_code:
            self.base.partial_support = False
            self.add_note('header-accept-ranges', RANGE_FULL)
        else:
            self.add_note('header-accept-ranges', 
                RANGE_STATUS,
                range_status=self.response.status_code,
                enc_range_status=self.response.status_code or \
                  '(unknown)'
            )



class RANGE_SUBREQ_PROBLEM(Note):
    category = categories.RANGE
    level = levels.BAD
    summary = u"There was a problem checking for Partial Content support."
    text = u"""\
When RED tried to check the resource for partial content support, there was a problem:

`%(problem)s`

Trying again might fix it."""

class UNKNOWN_RANGE(Note):
    category = categories.RANGE
    level = levels.WARN
    summary = u"%(response)s advertises support for non-standard range-units."
    text = u"""\
The `Accept-Ranges` response header tells clients what `range-unit`s a resource is willing to
process in future requests. HTTP only defines two: `bytes` and `none`.

Clients who don't know about the non-standard range-unit will not be able to use it."""

class RANGE_CORRECT(Note):
    category = categories.RANGE
    level = levels.GOOD
    summary = u"A ranged request returned the correct partial content."
    text = u"""\
This resource advertises support for ranged requests with `Accept-Ranges`; that is, it allows
clients to specify that only part of it should be sent. RED has tested this by requesting part of
this response, which was returned correctly."""

class RANGE_INCORRECT(Note):
    category = categories.RANGE
    level = levels.BAD
    summary = u'A ranged request returned partial content, but it was incorrect.'
    text = u"""\
This resource advertises support for ranged requests with `Accept-Ranges`; that is, it allows
clients to specify that only part of the response should be sent. RED has tested this by requesting
part of this response, but the partial response doesn't correspond with the full response retrieved
at the same time. This could indicate that the range implementation isn't working properly.

RED sent:
    `Range: %(range)s`

RED expected %(range_expected_bytes)s bytes:
    `%(range_expected).100s`

RED received %(range_received_bytes)s bytes:
    `%(range_received).100s`

_(showing samples of up to 100 characters)_"""

class RANGE_CHANGED(Note):
    category = categories.RANGE
    level = levels.WARN
    summary = u"A ranged request returned another representation."
    text = u"""\
A new representation was retrieved when checking support of ranged request. This is not an error,
it just indicates that RED cannot draw any conclusion at this time."""

class RANGE_FULL(Note):
    category = categories.RANGE
    level = levels.WARN
    summary = u"A ranged request returned the full rather than partial content."
    text = u"""\
This resource advertises support for ranged requests with `Accept-Ranges`; that is, it allows
clients to specify that only part of the response should be sent. RED has tested this by requesting
part of this response, but the entire response was returned. In other words, although the resource
advertises support for partial content, it doesn't appear to actually do so."""

class RANGE_STATUS(Note):
    category = categories.RANGE
    level = levels.INFO
    summary = u"A ranged request returned a %(range_status)s status."
    text = u"""\
This resource advertises support for ranged requests; that is, it allows clients to specify that
only part of the response should be sent. RED has tested this by requesting part of this response,
but a %(enc_range_status)s response code was returned, which RED was not expecting."""

class RANGE_NEG_MISMATCH(Note):
    category = categories.RANGE
    level = levels.BAD
    summary = u"Partial responses don't have the same support for compression that full ones do."
    text = u"""\
This resource supports ranged requests and also supports negotiation for gzip compression, but
doesn't support compression for both full and partial responses.

This can cause problems for clients when they compare the partial and full responses, since the
partial response is expressed as a byte range, and compression changes the bytes."""

class MISSING_HDRS_206(Note):
    category = c.VALIDATION
    level = levels.WARN
    summary = u"The %(subreq_type)s response is missing required headers."
    text = u"""\
HTTP requires `206 Parital Content` responses to have certain headers, if they are also present in
a normal (e.g., `200 OK` response).

%(response)s is missing the following headers: `%(missing_hdrs)s`.

This can affect cache operation; because the headers are missing, caches might remove them from
their stored copies."""