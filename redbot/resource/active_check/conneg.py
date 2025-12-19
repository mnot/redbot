"""
Subrequest for content negotiation checks.
"""

from httplint.note import categories, levels
from redbot.note import RedbotNote

from redbot.i18n import _
from redbot.resource.active_check.base import SubRequest
from redbot.formatter import f_num
from redbot.type import StrHeaderListType


class ConnegCheck(SubRequest):
    """
    See if content negotiation for compression is supported, and how.
    """

    check_name = _("Content Negotiation")
    check_id = "conneg"
    response_phrase = _("The compressed response")

    def modify_request_headers(
        self, base_headers: StrHeaderListType
    ) -> StrHeaderListType:
        return [h for h in base_headers if h[0].lower() != "accept-encoding"] + [
            ("accept-encoding", "gzip")
        ]

    def preflight(self) -> bool:
        if "accept-encoding" in [
            k.lower() for (k, v) in self.base.request.headers.text
        ]:
            return False
        if self.base.response.status_code == 206:
            return False
        return True

    def done(self) -> None:
        negotiated = self.response
        bare = self.base.response

        if not negotiated.complete:
            if self.fetch_error:
                problem = self.fetch_error.desc
            else:
                problem = ""
            self.add_base_note("", CONNEG_SUBREQ_PROBLEM, problem=problem)
            return

        if "gzip" not in negotiated.headers.parsed.get(
            "content-encoding", []
        ) and "x-gzip" not in negotiated.headers.parsed.get("content-encoding", []):
            self.base.gzip_support = False
        else:  # Apparently, content negotiation is happening.
            # check status
            if bare.status_code != negotiated.status_code:
                self.add_base_note(
                    "status",
                    VARY_STATUS_MISMATCH,
                    neg_status=negotiated.status_code or 0,
                    noneg_status=bare.status_code or 0,
                )
                return  # Can't be sure what's going on...

            # check headers that should be invariant
            for hdr in ["content-type"]:
                bare_val = bare.headers.parsed.get(hdr)
                negotiated_val = negotiated.headers.parsed.get(hdr, None)
                if bare_val != negotiated_val:
                    self.add_base_note(
                        f"field-{hdr}",
                        VARY_HEADER_MISMATCH,
                        header=hdr,
                        bare_val=str(bare_val),
                        negotiated_val=str(negotiated_val),
                    )

            # check Vary headers
            vary_headers = negotiated.headers.parsed.get("vary", [])
            no_conneg_vary_headers = bare.headers.parsed.get("vary", [])
            if (not "accept-encoding" in vary_headers) and (not "*" in vary_headers):
                self.add_base_note("field-vary", CONNEG_NO_VARY)
            if no_conneg_vary_headers != vary_headers:
                self.add_base_note(
                    "field-vary",
                    VARY_INCONSISTENT,
                    conneg_vary=", ".join(vary_headers),
                    no_conneg_vary=", ".join(no_conneg_vary_headers) or "-",
                )

            # check ETag
            if bare.headers.parsed.get("etag", 1) == negotiated.headers.parsed.get(
                "etag", 2
            ):
                if not self.base.response.headers.parsed["etag"][0]:  # strong
                    self.add_base_note("field-etag", VARY_ETAG_DOESNT_CHANGE)

            # bail if decode didn't complete.
            if not negotiated.decoded.decode_ok:
                return

            # check body
            if bare.content_hash != negotiated.decoded.hash:
                self.add_base_note("body", VARY_BODY_MISMATCH)

            # check compression efficiency
            if negotiated.content_length > 0 and bare.content_length > 0:
                savings = int(
                    100
                    * (
                        (float(bare.content_length) - negotiated.content_length)
                        / bare.content_length
                    )
                )
            elif negotiated.content_length > 0 and bare.content_length == 0:
                # weird.
                return
            else:
                savings = 0
            self.base.gzip_support = True
            self.base.gzip_savings = savings
            if savings >= 0:
                self.add_base_note(
                    "field-content-encoding",
                    CONNEG_GZIP_GOOD,
                    savings=savings,
                    orig_size=f_num(bare.content_length),
                    gzip_size=f_num(negotiated.content_length),
                )
            else:
                self.add_base_note(
                    "field-content-encoding",
                    CONNEG_GZIP_BAD,
                    savings=abs(savings),
                    orig_size=f_num(bare.content_length),
                    gzip_size=f_num(negotiated.content_length),
                )


class CONNEG_SUBREQ_PROBLEM(RedbotNote):
    category = categories.CONNEG
    level = levels.INFO
    _summary = "There was a problem checking for Content Negotiation support."
    _text = """\
When REDbot tried to check the resource for content negotiation support, there was a problem:

`%(problem)s`

Trying again might fix it."""


class CONNEG_GZIP_GOOD(RedbotNote):
    category = categories.CONNEG
    level = levels.GOOD
    _summary = (
        "Content negotiation for gzip compression is supported, saving %(savings)s%%."
    )
    _text = """\
HTTP supports compression of responses by negotiating for `Content-Encoding`. When REDbot asked for
a compressed response, the resource provided one, saving %(savings)s%% of its original size (from
%(orig_size)s to %(gzip_size)s bytes).

The compressed response's headers are displayed."""


class CONNEG_GZIP_BAD(RedbotNote):
    category = categories.CONNEG
    level = levels.WARN
    _summary = "Content negotiation for gzip compression makes the response %(savings)s%% larger."
    _text = """\
HTTP supports compression of responses by negotiating for `Content-Encoding`. When REDbot asked for
a compressed response, the resource provided one, but it was %(savings)s%% _larger_ than the
original response; from %(orig_size)s to %(gzip_size)s bytes.

Often, this happens when the uncompressed response is very small, or can't be compressed more;
since gzip compression has some overhead, it can make the response larger. Turning compression
**off** for this resource may slightly improve response times and save bandwidth.

The compressed response's headers are displayed."""


class CONNEG_NO_GZIP(RedbotNote):
    category = categories.CONNEG
    level = levels.INFO
    _summary = "Content negotiation for gzip compression isn't supported."
    _text = """\
HTTP supports compression of responses by negotiating for `Content-Encoding`. When REDbot asked for
a compressed response, the resource did not provide one."""


class CONNEG_NO_VARY(RedbotNote):
    category = categories.CONNEG
    level = levels.BAD
    _summary = "The compressed response is negotiated, but doesn't have an appropriate Vary header."
    _text = """\
All content negotiated responses need to have a `Vary` header that reflects the header(s) used to
select the response.

The compressed response was negotiated for `gzip` content encoding, so the `Vary` header needs to contain
`Accept-Encoding`, the request header used."""


class VARY_INCONSISTENT(RedbotNote):
    category = categories.CONNEG
    level = levels.BAD
    _summary = "The resource doesn't send Vary consistently."
    _text = """\
HTTP requires that the `Vary` response header be sent consistently for all responses if they change
based upon different aspects of the request.

This resource has both compressed and uncompressed variants available, negotiated by the
`Accept-Encoding` request header, but it sends different Vary headers for each;

* "`%(conneg_vary)s`" when the response is compressed, and
* "`%(no_conneg_vary)s`" when it is not.

This can cause problems for downstream caches, because they cannot consistently determine what the
cache key for a given URI is."""


class VARY_STATUS_MISMATCH(RedbotNote):
    category = categories.CONNEG
    level = levels.WARN
    _summary = "The response status is different when content negotiation happens."
    _text = """\
When content negotiation is used, the response status shouldn't change between negotiated and
non-negotiated responses.

When REDbot send asked for a negotiated response, it got a `%(neg_status)s` status code; when it
didn't, it got `%(noneg_status)s`.

REDbot hasn't checked other aspects of content negotiation because of this."""


class VARY_HEADER_MISMATCH(RedbotNote):
    category = categories.CONNEG
    level = levels.BAD
    _summary = "The %(header)s header is different when content negotiation happens."
    _text = """\
When content negotiation is used, the %(header)s response header shouldn't change between
negotiated and non-negotiated responses.

* Negotiated: `%(negotiated_val)s`
* Non-negotiated: `%(bare_val)s`"""


class VARY_BODY_MISMATCH(RedbotNote):
    category = categories.CONNEG
    level = levels.INFO
    _summary = "The response content is different when content negotiation happens."
    _text = """\
When content negotiation is used, the response content typically shouldn't change between negotiated
and non-negotiated responses.

There might be legitimate reasons for this; e.g., because different servers handled the two
requests. However, RED's output may be skewed as a result."""


class VARY_ETAG_DOESNT_CHANGE(RedbotNote):
    category = categories.CONNEG
    level = levels.BAD
    _summary = "The ETag doesn't change between negotiated representations."
    _text = """\
HTTP requires that the `ETag`s for two different responses associated with the same URI be
different as well, to help caches and other receivers disambiguate them.

This resource, however, sent the same strong ETag for both its compressed and uncompressed versions
(negotiated by `Accept-Encoding`). This can cause interoperability problems, especially with caches.

Note that some versions of the Apache HTTP Server sometimes send the same ETag for both
compressed and uncompressed versions of a resource. This is a [known
bug](https://issues.apache.org/bugzilla/show_bug.cgi?id=39727)."""
