"""
Subrequests to do things like range requests, content negotiation checks,
and validation.

This is the base class for all subrequests.
"""

from abc import ABCMeta, abstractmethod
from configparser import SectionProxy
from typing import List, Type, Union, TYPE_CHECKING

from httplint.note import Note, levels, categories

from redbot.resource.fetch import RedFetcher
from redbot.type import StrHeaderListType
from redbot.note import RedbotNote

if TYPE_CHECKING:
    from redbot.resource import HttpResource  # pylint: disable=cyclic-import


class SubRequest(RedFetcher, metaclass=ABCMeta):
    """
    Base class for a subrequest of a "main" HttpResource, made to perform
    additional behavioural tests on the resource.
    """

    check_name = "undefined"
    check_id = "undefined"

    def __init__(self, config: SectionProxy, base_resource: "HttpResource") -> None:
        self.config = config
        self.base: HttpResource = (  # pylint: disable=used-before-assignment
            base_resource
        )
        RedFetcher.__init__(self, config)
        self.check_done = False
        self.on("fetch_done", self._check_done)

    @abstractmethod
    def done(self) -> None:
        """The subrequest is done, process it. Must be overridden."""
        raise NotImplementedError

    def _check_done(self) -> None:
        if self.preflight():
            self.done()
        self.check_done = True
        self.emit("check_done")

    def check(self) -> None:
        modified_headers = self.modify_request_headers(
            list(self.base.request.headers.text)
        )
        assert self.base.request.uri, "Base URI not set in SubRequest.check"
        assert self.base.request.method, "Base method not set in SubRequest.check"
        RedFetcher.set_request(
            self,
            self.base.request.uri,
            self.base.request.method,
            modified_headers,
            self.base.request_content,
        )
        RedFetcher.check(self)

    @abstractmethod
    def modify_request_headers(
        self, base_headers: StrHeaderListType
    ) -> StrHeaderListType:
        """Usually overridden; modifies the request headers."""
        return base_headers

    def add_base_note(
        self, subject: str, note: Type[Note], **kw: Union[str, int]
    ) -> None:
        "Add a Note to the base resource."
        self.base.response.notes.add(subject, note, **kw)

    def check_missing_hdrs(self, hdrs: List[str], note: Type[Note]) -> None:
        """
        See if the listed headers are missing in the subrequest; if so,
        set the specified note.
        """
        missing_hdrs = []
        for hdr in hdrs:
            if (
                hdr in self.base.response.headers.parsed
                and hdr not in self.response.headers.parsed
            ):
                missing_hdrs.append(hdr)
        if missing_hdrs:
            self.add_base_note("headers", note, missing_hdrs=", ".join(missing_hdrs))
            self.response.notes.add(
                "headers", note, missing_hdrs=", ".join(missing_hdrs)
            )


class MISSING_HDRS_304(RedbotNote):
    category = categories.VALIDATION
    level = levels.WARN
    _summary = "This response is missing required headers."
    _text = """\
HTTP requires `304 Not Modified` responses to have certain headers, if they are also present in a
normal (e.g., `200 OK` response).

This response is missing the following headers: `%(missing_hdrs)s`.

This can affect cache operation; because the headers are missing, caches might remove them from
their cached copies."""
