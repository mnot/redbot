#!/usr/bin/env python

"""
Subrequest for ETag validation checks.
"""


from redbot.resource.active_check.base import SubRequest
from redbot.speak import Note, categories, levels, MISSING_HDRS_304


class ETagValidate(SubRequest):
    "If an ETag is present, see if it will validate."

    def modify_req_hdrs(self):
        req_hdrs = list(self.base.request.headers)
        if self.base.response.parsed_headers.has_key('etag'):
            weak, etag = self.base.response.parsed_headers['etag']
            if weak:
                weak_str = u"W/"
                # #65: note on weak etag
            else:
                weak_str = u""
            etag_str = u'%s"%s"' % (weak_str, etag)
            req_hdrs += [
                (u'If-None-Match', etag_str),
            ]
        return req_hdrs
            
    def preflight(self):
        if self.base.response.parsed_headers.has_key('etag'):
            return True
        else:
            self.base.inm_support = False
            return False

    def done(self):
        if not self.response.complete:
            self.add_note('', ETAG_SUBREQ_PROBLEM,
                problem=self.response.http_error.desc
            )
            return
            
        if self.response.status_code == '304':
            self.base.inm_support = True
            self.add_note('header-etag', INM_304)
            self.check_missing_hdrs([
                    'cache-control', 'content-location', 'etag', 
                    'expires', 'vary'
                ], MISSING_HDRS_304, 'If-None-Match'
            )
        elif self.response.status_code \
          == self.base.response.status_code:
            if self.response.payload_md5 \
              == self.base.response.payload_md5:
                self.base.inm_support = False
                self.add_note('header-etag', INM_FULL)
            else: # bodies are different
                if self.base.response.parsed_headers['etag'] == \
                  self.response.parsed_headers.get('etag', 1):
                    if self.base.response.parsed_headers['etag'][0]: # weak
                        self.add_note('header-etag', INM_DUP_ETAG_WEAK)
                    else: # strong
                        self.add_note('header-etag',
                            INM_DUP_ETAG_STRONG,
                            etag=self.base.response.parsed_headers['etag']
                        )
                else:
                    self.add_note('header-etag', INM_UNKNOWN)
        else:
            self.add_note('header-etag', 
                INM_STATUS, 
                inm_status = self.response.status_code,
                enc_inm_status = self.response.status_code \
                  or '(unknown)'
            )
        # TODO: check entity headers


class ETAG_SUBREQ_PROBLEM(Note):
    category = categories.VALIDATION
    level = levels.BAD
    summary = u"There was a problem checking for ETag validation support."
    text = u"""\
When RED tried to check the resource for ETag validation support, there was a problem:

`%(problem)s`

Trying again might fix it."""
    
class INM_304(Note):
    category = categories.VALIDATION
    level = levels.GOOD
    summary = u"If-None-Match conditional requests are supported."
    text = u"""\
HTTP allows clients to make conditional requests to see if a copy that they hold is still valid.
Since this response has an `ETag`, clients should be able to use an `If-None-Match` request header
for validation. RED has done this and found that the resource sends a `304 Not Modified` response,
indicating that it supports `ETag` validation."""

class INM_FULL(Note):
    category = categories.VALIDATION
    level = levels.WARN
    summary = u"An If-None-Match conditional request returned the full content \
unchanged."
    text = u"""\
HTTP allows clients to make conditional requests to see if a copy that they hold is still valid.
Since this response has an `ETag`, clients should be able to use an `If-None-Match` request header
for validation.

RED has done this and found that the resource sends the same, full response even though it hadn't
changed, indicating that it doesn't support `ETag` validation."""

class INM_DUP_ETAG_WEAK(Note):
    category = categories.VALIDATION
    level = levels.INFO
    summary = u"During validation, the ETag didn't change, even though the response body did."
    text = u"""\
`ETag`s are supposed to uniquely identify the response representation; if the content changes, so
should the ETag.

However, HTTP allows reuse of an `ETag` if it's "weak", as long as the server is OK with the two
different responses being considered as interchangeable by clients.

For example, if a small detail of a Web page changes, and it doesn't affect the overall meaning of
the page, you can use the same weak `ETag` to identify both versions.

If the changes are important, a different `ETag` should be used."""
    
class INM_DUP_ETAG_STRONG(Note):
    category = categories.VALIDATION
    level = levels.BAD
    summary = u"During validation, the ETag didn't change, even though the response body did."
    text = u"""\
`ETag`s are supposed to uniquely identify the response representation; if the content changes, so
should the ETag.

Here, the same `ETag` was used for two different responses during validation, which means that
downstream clients and caches might confuse them.

If the changes between the two versions aren't important, and they can be used interchangeably, a
"weak" ETag should be used; to do that, just prepend `W/`, to make it `W/%(etag)s`. Otherwise, a
different `ETag` needs to be used."""

class INM_UNKNOWN(Note):
    category = categories.VALIDATION
    level = levels.INFO
    summary = u"An If-None-Match conditional request returned the full content, but it had changed."
    text = u"""\
HTTP allows clients to make conditional requests to see if a copy that they hold is still valid.
Since this response has an `ETag`, clients should be able to use an `If-None-Match` request header
for validation.

RED has done this, but the response changed between the original request and the validating
request, so RED can't tell whether or not `ETag` validation is supported."""

class INM_STATUS(Note):
    category = categories.VALIDATION
    level = levels.INFO
    summary = u"An If-None-Match conditional request returned a %(inm_status)s status."
    text = u"""\
HTTP allows clients to make conditional requests to see if a copy that they hold is still valid.
Since this response has an `ETag`, clients should be able to use an `If-None-Match` request header
for validation. RED has done this, but the response had a %(enc_inm_status)s status code, so RED
can't tell whether or not `ETag` validation is supported."""
