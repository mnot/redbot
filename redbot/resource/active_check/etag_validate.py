"""
Subrequest for ETag validation checks.
"""

from httplint.note import categories, levels
from redbot.note import RedbotNote

from redbot.i18n import _
from redbot.resource.active_check.base import SubRequest, MISSING_HDRS_304
from redbot.type import StrHeaderListType


class ETagValidate(SubRequest):
    """
    If the response has an ETag, try to validate it.
    """

    check_name = _("ETag Validation")
    check_id = "etag_validate"
    response_phrase = _("The ETag validation response")

    def modify_request_headers(
        self, base_headers: StrHeaderListType
    ) -> StrHeaderListType:
        etag_value = self.base.response.headers.parsed.get("etag", None)
        if etag_value:
            weak, etag = etag_value
            if weak:
                weak_str = "W/"
                # #65: note on weak etag
            else:
                weak_str = ""
            etag_str = f'{weak_str}"{etag}"'
            base_headers.append(("If-None-Match", etag_str))
        return base_headers

    def preflight(self) -> bool:
        if (
            self.base.response.status_code
            and 300 <= self.base.response.status_code <= 399
        ):
            return False
        etag = self.base.response.headers.parsed.get("etag", None)
        if etag:
            return True
        self.base.inm_support = False
        return False

    def done(self) -> None:
        if not self.response.complete:
            if self.fetch_error:
                problem = self.fetch_error.desc
            else:
                problem = ""
            self.add_base_note("", ETAG_SUBREQ_PROBLEM, problem=problem)
            return

        if self.response.status_code == 304:
            self.base.inm_support = True
            self.add_base_note("field-etag", INM_304)
            self.check_missing_hdrs(
                ["cache-control", "content-location", "etag", "expires", "vary"],
                MISSING_HDRS_304,
            )
        elif self.response.status_code == self.base.response.status_code:
            if self.response.content_hash == self.base.response.content_hash:
                self.base.inm_support = False
                self.add_base_note("field-etag", INM_FULL)
            else:  # bodies are different
                if self.base.response.headers.parsed[
                    "etag"
                ] == self.response.headers.parsed.get("etag", 1):
                    if self.base.response.headers.parsed["etag"][0]:  # weak
                        self.add_base_note("field-etag", INM_DUP_ETAG_WEAK)
                    else:  # strong
                        self.add_base_note(
                            "field-etag",
                            INM_DUP_ETAG_STRONG,
                            etag=self.base.response.headers.parsed["etag"],
                        )
                else:
                    self.add_base_note("field-etag", INM_UNKNOWN)
        else:
            self.add_base_note(
                "field-etag",
                INM_STATUS,
                inm_status=self.response.status_code or 0,
                enc_inm_status=self.response.status_code or "(unknown)",
            )


class ETAG_SUBREQ_PROBLEM(RedbotNote):
    category = categories.VALIDATION
    level = levels.INFO
    _summary = "There was a problem checking for ETag validation support."
    _text = """\
When REDbot tried to check the resource for ETag validation support, there was a problem:

`%(problem)s`

Trying again might fix it."""


class INM_304(RedbotNote):
    category = categories.VALIDATION
    level = levels.GOOD
    _summary = "If-None-Match conditional requests are supported."
    _text = """\
HTTP allows clients to make conditional requests to see if a copy that they hold is still valid.
Since this response has an `ETag`, clients should be able to use an `If-None-Match` request header
for validation. REDbot has done this and found that the resource sends a `304 Not Modified`
response, indicating that it supports `ETag` validation."""


class INM_FULL(RedbotNote):
    category = categories.VALIDATION
    level = levels.WARN
    _summary = "An If-None-Match conditional request returned the full content \
unchanged."
    _text = """\
HTTP allows clients to make conditional requests to see if a copy that they hold is still valid.
Since this response has an `ETag`, clients should be able to use an `If-None-Match` request header
for validation.

REDbot has done this and found that the resource sends the same, full response even though it hadn't
changed, indicating that it doesn't support `ETag` validation."""


class INM_DUP_ETAG_WEAK(RedbotNote):
    category = categories.VALIDATION
    level = levels.INFO
    _summary = "During validation, the ETag didn't change, even though the response content did."
    _text = """\
`ETag`s are supposed to uniquely identify the response representation; if the content changes, so
should the ETag.

However, HTTP allows reuse of an `ETag` if it's "weak", as long as the server is OK with the two
different responses being considered as interchangeable by clients.

For example, if a small detail of a Web page changes, and it doesn't affect the overall meaning of
the page, you can use the same weak `ETag` to identify both versions.

If the changes are important, a different `ETag` should be used."""


class INM_DUP_ETAG_STRONG(RedbotNote):
    category = categories.VALIDATION
    level = levels.BAD
    _summary = "During validation, the ETag didn't change, even though the response content did."
    _text = """\
`ETag`s are supposed to uniquely identify the response representation; if the content changes, so
should the ETag.

Here, the same `ETag` was used for two different responses during validation, which means that
downstream clients and caches might confuse them.

If the changes between the two representations aren't important (i.e., they can be used
interchangeably), they can share a "weak" ETag; to do that, just prepend `W/`, to make its value
`W/%(etag)s`. Otherwise, they need to use different `ETag`s."""


class INM_UNKNOWN(RedbotNote):
    category = categories.VALIDATION
    level = levels.INFO
    _summary = "An If-None-Match conditional request returned the full content, but it had changed."
    _text = """\
HTTP allows clients to make conditional requests to see if a copy that they hold is still valid.
Since this response has an `ETag`, clients should be able to use an `If-None-Match` request header
for validation.

REDbot has done this, but the response changed between the original request and the validating
request, so REDbot can't tell whether or not `ETag` validation is supported."""


class INM_STATUS(RedbotNote):
    category = categories.VALIDATION
    level = levels.INFO
    _summary = "An If-None-Match conditional request returned a %(inm_status)s status."
    _text = """\
HTTP allows clients to make conditional requests to see if a copy that they hold is still valid.
Since this response has an `ETag`, clients should be able to use an `If-None-Match` request header
for validation. REDbot has done this, but the response had a %(enc_inm_status)s status code, so RED
can't tell whether or not `ETag` validation is supported."""
