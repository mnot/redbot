"""
Subrequest for partial content checks.
"""

from configparser import SectionProxy
import random
from typing import TYPE_CHECKING

from httplint.util import display_bytes
from httplint.note import categories, levels
from redbot.note import RedbotNote

from redbot.resource.active_check.base import SubRequest
from redbot.formatter import f_num
from redbot.type import StrHeaderListType

from redbot.i18n import _

if TYPE_CHECKING:
    from redbot.resource import HttpResource  # pylint: disable=cyclic-import


class RangeRequest(SubRequest):
    """
    Check for partial content support.
    """

    check_name = _("Partial Content")
    check_id = "range"
    response_phrase = _("The partial response")

    def __init__(self, config: SectionProxy, resource: "HttpResource") -> None:
        self.range_start: int
        self.range_end: int
        self.range_target: bytes
        self.max_sample_size = 0  # unlimited
        SubRequest.__init__(self, config, resource)

    def modify_request_headers(
        self, base_headers: StrHeaderListType
    ) -> StrHeaderListType:
        if self.base.response_content_sample:
            sample_num = random.randint(0, len(self.base.response_content_sample) - 1)
            sample_len = min(96, len(self.base.response_content_sample[sample_num][1]))
            self.range_start = self.base.response_content_sample[sample_num][0]
            self.range_end = self.range_start + sample_len
            self.range_target = self.base.response_content_sample[sample_num][1][
                : sample_len + 1
            ]
            base_headers.append(("Range", f"bytes={self.range_start}-{self.range_end}"))
        return base_headers

    def preflight(self) -> bool:
        if (
            self.base.response.status_code
            and 300 <= self.base.response.status_code <= 399
        ):
            return False
        if self.base.response.status_code == 206:
            return False
        if "bytes" in self.base.response.headers.parsed.get("accept-ranges", []):
            if not self.base.response_content_sample:
                return False
            if self.range_start == self.range_end:
                # wow, that's a small body.
                return False
            return True
        self.base.partial_support = False
        return False

    def done(self) -> None:
        if not self.response.complete:
            if self.fetch_error:
                problem = self.fetch_error.desc
            else:
                problem = ""
            self.add_base_note("", RANGE_SUBREQ_PROBLEM, problem=problem)
            return

        if self.response.status_code == 206:
            c_e = "content-encoding"
            if ("gzip" in self.base.response.headers.parsed.get(c_e, [])) == (
                "gzip" not in self.response.headers.parsed.get(c_e, [])
            ):
                self.add_base_note(
                    "field-accept-ranges field-content-encoding", RANGE_NEG_MISMATCH
                )
                return
            self.check_missing_hdrs(
                [
                    "date",
                    "cache-control",
                    "content-location",
                    "etag",
                    "expires",
                    "vary",
                ],
                MISSING_HDRS_206,
            )

            if self.response.content_length == self.base.response.content_length:
                self.add_base_note("field-content-length", RANGE_CL_FULL)

            content_range = self.response.headers.parsed.get("content-range", None)
            if content_range:
                if (
                    content_range[2] is not None
                    and content_range[2] != self.base.response.content_length
                ):
                    self.add_base_note("field-content-range", RANGE_INCORRECT_LENGTH)

            if self.response.headers.parsed.get(
                "etag", None
            ) == self.base.response.headers.parsed.get("etag", None):
                content = b"".join([chunk[1] for chunk in self.response_content_sample])
                if content == self.range_target:
                    self.base.partial_support = True
                    self.add_base_note("field-accept-ranges", RANGE_CORRECT)
                else:
                    # the body samples are just bags of bits
                    self.base.partial_support = False
                    self.add_base_note(
                        "field-accept-ranges",
                        RANGE_INCORRECT,
                        range=f"bytes={self.range_start}-{self.range_end}",
                        range_expected=display_bytes(self.range_target),
                        range_expected_bytes=f_num(len(self.range_target)),
                        range_received=display_bytes(content),
                        range_received_bytes=f_num(self.response.content_length),
                    )
            else:
                self.add_base_note("field-accept-ranges", RANGE_CHANGED)

        elif self.response.status_code == self.base.response.status_code:
            self.base.partial_support = False
            self.add_base_note("field-accept-ranges", RANGE_FULL)
        else:
            self.add_base_note(
                "field-accept-ranges",
                RANGE_STATUS,
                range_status=self.response.status_code or 0,
                enc_range_status=self.response.status_code or "(unknown)",
            )


class RANGE_SUBREQ_PROBLEM(RedbotNote):
    category = categories.RANGE
    level = levels.INFO
    _summary = "There was a problem checking for Partial Content support."
    _text = """\
When REDbot tried to check the resource for partial content support, there was a problem:

`%(problem)s`

Trying again might fix it."""


class UNKNOWN_RANGE(RedbotNote):
    category = categories.RANGE
    level = levels.WARN
    _summary = "The resource advertises support for non-standard range-units."
    _text = """\
The `Accept-Ranges` response header tells clients what `range-unit`s a resource is willing to
process in future requests. HTTP only defines two: `bytes` and `none`.

Clients who don't know about the non-standard range-unit will not be able to use it."""


class RANGE_CORRECT(RedbotNote):
    category = categories.RANGE
    level = levels.GOOD
    _summary = "A ranged request returned the correct partial content."
    _text = """\
This resource advertises support for ranged requests with `Accept-Ranges`; that is, it allows
clients to specify that only part of it should be sent. REDbot has tested this by requesting part of
this response, which was returned correctly."""


class RANGE_INCORRECT(RedbotNote):
    category = categories.RANGE
    level = levels.BAD
    _summary = "A ranged request returned partial content, but it was incorrect."
    _text = """\
This resource advertises support for ranged requests with `Accept-Ranges`; that is, it allows
clients to specify that only part of the response should be sent. REDbot has tested this by
requesting part of this response, but the partial response doesn't correspond with the full
response retrieved at the same time. This could indicate that the range implementation isn't
working properly.

REDbot sent:

> Range: %(range)s

REDbot expected %(range_expected_bytes)s bytes:

> %(range_expected).100s

REDbot received %(range_received_bytes)s bytes:

> %(range_received).100s

_(showing samples of up to 100 characters)_"""


class RANGE_CHANGED(RedbotNote):
    category = categories.RANGE
    level = levels.WARN
    _summary = "A ranged request returned another representation."
    _text = """\
A new representation was retrieved when checking support of ranged request. This is not an error,
it just indicates that REDbot cannot draw any conclusion at this time."""


class RANGE_FULL(RedbotNote):
    category = categories.RANGE
    level = levels.WARN
    _summary = "A ranged request returned the full rather than partial content."
    _text = """\
This resource advertises support for ranged requests with `Accept-Ranges`; that is, it allows
clients to specify that only part of the response should be sent. REDbot has tested this by
requesting part of this response, but the entire response was returned. In other words, although
the resource advertises support for partial content, it doesn't appear to actually do so."""


class RANGE_STATUS(RedbotNote):
    category = categories.RANGE
    level = levels.INFO
    _summary = "A ranged request returned a %(range_status)s status."
    _text = """\
This resource advertises support for ranged requests; that is, it allows clients to specify that
only part of the response should be sent. REDbot has tested this by requesting part of this
response, but a %(enc_range_status)s response code was returned, which REDbot was not expecting."""


class RANGE_NEG_MISMATCH(RedbotNote):
    category = categories.RANGE
    level = levels.BAD
    _summary = "Partial responses don't have the same support for compression that full ones do."
    _text = """\
This resource supports ranged requests and also supports negotiation for gzip compression, but
doesn't support compression for both full and partial responses.

This can cause problems for clients when they compare the partial and full responses, since the
partial response is expressed as a byte range, and compression changes the bytes."""


class MISSING_HDRS_206(RedbotNote):
    category = categories.VALIDATION
    level = levels.WARN
    _summary = "The partial response is missing required headers."
    _text = """\
HTTP requires `206 Partial Content` responses to have certain headers, if they are also present in
a normal (e.g., `200 OK` response).

The partial response is missing the following headers: `%(missing_hdrs)s`.

This can affect cache operation; because the headers are missing, caches might remove them from
their stored copies."""


class RANGE_CL_FULL(RedbotNote):
    category = categories.RANGE
    level = levels.WARN
    _summary = "The partial response has a Content-Length equal to the full response."
    _text = """\
The `Content-Length` header in a 206 response should indicate the size of the partial content, not
the full response. This response has a `Content-Length` that matches the full size of the response,
which suggests it might be incorrect."""


class RANGE_INCORRECT_LENGTH(RedbotNote):
    category = categories.RANGE
    level = levels.WARN
    _summary = "The Content-Range header indicates an incorrect total length."
    _text = """\
The `Content-Range` header in a 206 response indicates the total length of the response. In this
case, it doesn't match the `Content-Length` of the full response, which suggests one of them is
incorrect."""
