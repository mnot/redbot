#!/usr/bin/env python

"""
Subrequest for Last-Modified validation checks.
"""

from datetime import datetime

from redbot.resource.active_check.base import SubRequest, MISSING_HDRS_304
from redbot.speak import Note, categories, levels


class LmValidate(SubRequest):
    "If Last-Modified is present, see if it will validate."
    check_name = "Last-Modified Validation"
    response_phrase = "The 304 response"
    _weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    _months = [None, 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul',
               'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    def modify_request_headers(self, base_headers):
        lm_value = self.base.response.parsed_headers.get('last-modified', None)
        if lm_value:
            try:
                l_m = datetime.utcfromtimestamp(self.base.response.parsed_headers['last-modified'])
            except ValueError:
                return base_headers # this shouldn't really happen
            date_str = "%s, %.2d %s %.4d %.2d:%.2d:%.2d GMT" % (
                self._weekdays[l_m.weekday()],
                l_m.day,
                self._months[l_m.month],
                l_m.year,
                l_m.hour,
                l_m.minute,
                l_m.second)
            base_headers.append(('If-Modified-Since', date_str))
        return base_headers

    def preflight(self):
        if self.base.response.status_code[0] == '3':
            return False
        if self.base.response.parsed_headers.get('last-modified', None):
            return True
        else:
            self.base.ims_support = False
            return False

    def done(self):
        if not self.response.complete:
            self.add_base_note('', LM_SUBREQ_PROBLEM, problem=self.response.http_error.desc)
            return

        if self.response.status_code == '304':
            self.base.ims_support = True
            self.add_base_note('header-last-modified', IMS_304)
            self.check_missing_hdrs([
                'cache-control', 'content-location', 'etag', 'expires', 'vary'], MISSING_HDRS_304)
        elif self.response.status_code == self.base.response.status_code:
            if self.response.payload_md5 == self.base.response.payload_md5:
                self.base.ims_support = False
                self.add_base_note('header-last-modified', IMS_FULL)
            else:
                self.add_base_note('header-last-modified', IMS_UNKNOWN)
        else:
            self.add_base_note('header-last-modified', IMS_STATUS,
                               ims_status=self.response.status_code,
                               enc_ims_status=self.response.status_code or '(unknown)')


class LM_SUBREQ_PROBLEM(Note):
    category = categories.VALIDATION
    level = levels.INFO
    summary = "There was a problem checking for Last-Modified validation support."
    text = """\
When RED tried to check the resource for Last-Modified validation support, there was a problem:

`%(problem)s`

Trying again might fix it."""

class IMS_304(Note):
    category = categories.VALIDATION
    level = levels.GOOD
    summary = "If-Modified-Since conditional requests are supported."
    text = """\
HTTP allows clients to make conditional requests to see if a copy that they hold is still valid.
Since this response has a `Last-Modified` header, clients should be able to use an
`If-Modified-Since` request header for validation.

RED has done this and found that the resource sends a `304 Not Modified` response, indicating that
it supports `Last-Modified` validation."""

class IMS_FULL(Note):
    category = categories.VALIDATION
    level = levels.WARN
    summary = "An If-Modified-Since conditional request returned the full content unchanged."
    text = """\
HTTP allows clients to make conditional requests to see if a copy that they hold is still valid.
Since this response has a `Last-Modified` header, clients should be able to use an
`If-Modified-Since` request header for validation.

RED has done this and found that the resource sends a full response even though it hadn't changed,
indicating that it doesn't support `Last-Modified` validation."""

class IMS_UNKNOWN(Note):
    category = categories.VALIDATION
    level = levels.INFO
    summary = \
    "An If-Modified-Since conditional request returned the full content, but it had changed."
    text = """\
HTTP allows clients to make conditional requests to see if a copy that they hold is still valid.
Since this response has a `Last-Modified` header, clients should be able to use an
`If-Modified-Since` request header for validation.

RED has done this, but the response changed between the original request and the validating
request, so RED can't tell whether or not `Last-Modified` validation is supported."""

class IMS_STATUS(Note):
    category = categories.VALIDATION
    level = levels.INFO
    summary = "An If-Modified-Since conditional request returned a %(ims_status)s status."
    text = """\
HTTP allows clients to make conditional requests to see if a copy that they hold is still valid.
Since this response has a `Last-Modified` header, clients should be able to use an
`If-Modified-Since` request header for validation.

RED has done this, but the response had a %(enc_ims_status)s status code, so RED can't tell whether
or not `Last-Modified` validation is supported."""
