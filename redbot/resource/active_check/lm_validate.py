"""
Subrequest for Last-Modified validation checks.
"""

from datetime import datetime

from httplint.note import categories, levels
from redbot.note import RedbotNote

from redbot.i18n import _
from redbot.resource.active_check.base import SubRequest, MISSING_HDRS_304
from redbot.type import StrHeaderListType


class LmValidate(SubRequest):
    """
    If the response has a Last-Modified, try to validate it.
    """

    check_name = _("Last-Modified Validation")
    check_id = "lm_validate"
    response_phrase = _("The Last-Modified validation response")
    _weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    _months = [
        None,
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]

    def modify_request_headers(
        self, base_headers: StrHeaderListType
    ) -> StrHeaderListType:
        lm_value = self.base.response.headers.parsed.get("last-modified", None)
        if lm_value:
            try:
                l_m = datetime.utcfromtimestamp(
                    self.base.response.headers.parsed["last-modified"]
                )
            except ValueError:
                return base_headers  # this shouldn't really happen
            date_str = (
                "%s, %.2d %s %.4d %.2d:%.2d:%.2d GMT"  # pylint: disable=consider-using-f-string
                % (
                    self._weekdays[l_m.weekday()],
                    l_m.day,
                    self._months[l_m.month],
                    l_m.year,
                    l_m.hour,
                    l_m.minute,
                    l_m.second,
                )
            )
            base_headers.append(("If-Modified-Since", date_str))
        return base_headers

    def preflight(self) -> bool:
        if (
            self.base.response.status_code
            and 300 <= self.base.response.status_code <= 399
        ):
            return False
        if self.base.response.headers.parsed.get("last-modified", None):
            return True
        self.base.ims_support = False
        return False

    def done(self) -> None:
        if not self.response.complete:
            if self.fetch_error:
                problem = self.fetch_error.desc
            else:
                problem = ""
            self.add_base_note("", LM_SUBREQ_PROBLEM, problem=problem)
            return

        if self.response.status_code == 304:
            self.base.ims_support = True
            self.add_base_note("field-last-modified", IMS_304)
            self.check_missing_hdrs(
                ["cache-control", "content-location", "etag", "expires", "vary"],
                MISSING_HDRS_304,
            )
        elif self.response.status_code == self.base.response.status_code:
            if self.response.content_hash == self.base.response.content_hash:
                self.base.ims_support = False
                self.add_base_note("field-last-modified", IMS_FULL)
            else:
                self.add_base_note("field-last-modified", IMS_UNKNOWN)
        else:
            self.add_base_note(
                "field-last-modified",
                IMS_STATUS,
                ims_status=self.response.status_code or 0,
                enc_ims_status=self.response.status_code or "(unknown)",
            )


class LM_SUBREQ_PROBLEM(RedbotNote):
    category = categories.VALIDATION
    level = levels.INFO
    _summary = "There was a problem checking for Last-Modified validation support."
    _text = """\
When REDbot tried to check the resource for Last-Modified validation support, there was a problem:

`%(problem)s`

Trying again might fix it."""


class IMS_304(RedbotNote):
    category = categories.VALIDATION
    level = levels.GOOD
    _summary = "If-Modified-Since conditional requests are supported."
    _text = """\
HTTP allows clients to make conditional requests to see if a copy that they hold is still valid.
Since this response has a `Last-Modified` header, clients should be able to use an
`If-Modified-Since` request header for validation.

REDbot has done this and found that the resource sends a `304 Not Modified` response, indicating
that it supports `Last-Modified` validation."""


class IMS_FULL(RedbotNote):
    category = categories.VALIDATION
    level = levels.WARN
    _summary = (
        "An If-Modified-Since conditional request returned the full content unchanged."
    )
    _text = """\
HTTP allows clients to make conditional requests to see if a copy that they hold is still valid.
Since this response has a `Last-Modified` header, clients should be able to use an
`If-Modified-Since` request header for validation.

REDbot has done this and found that the resource sends a full response even though it hadn't
changed, indicating that it doesn't support `Last-Modified` validation."""


class IMS_UNKNOWN(RedbotNote):
    category = categories.VALIDATION
    level = levels.INFO
    _summary = (
        "An If-Modified-Since conditional request returned the full content, "
        "but it had changed."
    )
    _text = """\
HTTP allows clients to make conditional requests to see if a copy that they hold is still valid.
Since this response has a `Last-Modified` header, clients should be able to use an
`If-Modified-Since` request header for validation.

REDbot has done this, but the response changed between the original request and the validating
request, so REDbot can't tell whether or not `Last-Modified` validation is supported."""


class IMS_STATUS(RedbotNote):
    category = categories.VALIDATION
    level = levels.INFO
    _summary = (
        "An If-Modified-Since conditional request returned a %(ims_status)s status."
    )
    _text = """\
HTTP allows clients to make conditional requests to see if a copy that they hold is still valid.
Since this response has a `Last-Modified` header, clients should be able to use an
`If-Modified-Since` request header for validation.

REDbot has done this, but the response had a %(enc_ims_status)s status code, so REDbot can't tell
whether or not `Last-Modified` validation is supported."""
