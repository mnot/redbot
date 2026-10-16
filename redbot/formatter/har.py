"""
HAR Formatter for REDbot.
"""

import datetime
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from typing_extensions import NotRequired, TypedDict, Unpack

from redbot import __version__
from redbot.formatter import Formatter, FormatterArgs
from redbot.resource import HttpResource
from redbot.type import StrHeaderListType

TOKEN_RE = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+")


class HarLogDict(TypedDict):
    version: str
    creator: Dict[str, str]
    browser: Dict[str, str]
    pages: List[Any]
    entries: List[Dict[str, Any]]
    _red_error: NotRequired[str]


class HarDict(TypedDict):
    log: HarLogDict


class HarFormatter(Formatter):
    """
    Format a HttpResource object (and any descendants) as HAR.
    """

    can_multiple = True
    name = "har"
    media_type = "application/json"

    def __init__(self, *args: Unpack[FormatterArgs]) -> None:
        Formatter.__init__(self, *args)
        self.har = self.empty_har()
        self.last_id = 0

    @staticmethod
    def empty_har() -> HarDict:
        return {
            "log": {
                "version": "1.1",
                "creator": {"name": "REDbot", "version": __version__},
                "browser": {"name": "REDbot", "version": __version__},
                "pages": [],
                "entries": [],
            }
        }

    def start_output(self) -> None:
        pass

    def status(self, status: str) -> None:
        pass

    def feed(self, sample: bytes) -> None:
        pass

    def finish_output(self) -> None:
        "Fill in the template with RED's results."
        if self.resource.response.complete:
            page_id = self.add_page(self.resource)
            self.add_entry(self.resource, page_id)
            for linked_resource in [d[0] for d in self.resource.linked]:
                # filter out incomplete responses
                if linked_resource.response.complete:
                    self.add_entry(linked_resource, page_id)
        self.output(json.dumps(self.har, indent=4))

    def error_output(self, message: str) -> None:
        "Output a valid (empty) HAR document, with the error in a custom field."
        har = self.empty_har()
        har["log"]["_red_error"] = message
        self.output(json.dumps(har, indent=4))

    def add_entry(self, resource: HttpResource, page_ref: Optional[int] = None) -> None:
        assert resource.request.start_time, "request.start_time not set in add_entry"
        assert resource.response.start_time, "response.start_time not set in add_entry"
        assert resource.response.finish_time, "response.finish_time not set in add_entry"
        entry = {
            "startedDateTime": isoformat(resource.request.start_time),
            "time": int((resource.response.finish_time - resource.request.start_time) * 1000),
            "_red_messages": self.format_notes(resource),
        }
        if page_ref:
            entry["pageref"] = f"page{page_ref}"

        request = {
            "method": resource.request.method,
            "url": resource.request.uri,
            "httpVersion": "HTTP/1.1",
            "cookies": [],
            "headers": self.format_headers(resource.request.headers.text),
            "queryString": [],
            "headersSize": -1,
            "bodySize": -1,
        }

        response = {
            "status": resource.response.status_code,
            "statusText": resource.response.status_phrase,
            "httpVersion": f"HTTP/{resource.response.version}",
            "cookies": [],
            "headers": self.format_headers(resource.response.headers.text),
            "content": {
                "size": resource.response.decoded.length,
                "compression": resource.response.decoded.length - resource.response.content_length,
                "mimeType": format_media_type(resource.response.headers.parsed.get("content-type")),
            },
            "redirectURL": resource.response.headers.parsed.get("location", ""),
            "headersSize": resource.response_header_length,
            "bodySize": resource.response.content_length,
        }

        cache: Dict[None, None] = {}
        timings = {
            "dns": -1,
            "connect": -1,
            "blocked": 0,
            "send": 0,
            "wait": int((resource.response.start_time - resource.request.start_time) * 1000),
            "receive": int((resource.response.finish_time - resource.response.start_time) * 1000),
        }

        entry.update(
            {
                "request": request,
                "response": response,
                "cache": cache,
                "timings": timings,
            }
        )
        self.har["log"]["entries"].append(entry)

    def add_page(self, resource: HttpResource) -> int:
        assert resource.request.start_time, "request.start_time not set in add_page"
        page_id = self.last_id + 1
        page = {
            "startedDateTime": isoformat(resource.request.start_time),
            "id": f"page{page_id}",
            "title": "",
            "pageTimings": {"onContentLoad": -1, "onLoad": -1},
        }
        self.har["log"]["pages"].append(page)
        return page_id

    @staticmethod
    def format_headers(hdrs: StrHeaderListType) -> List[Dict[str, str]]:
        return [{"name": n, "value": v} for n, v in hdrs]

    def format_notes(self, resource: HttpResource) -> List[Dict[str, Any]]:
        return [self.format_note(note) for note in resource.response.notes]

    def format_note(self, note: Any) -> Dict[str, Any]:
        msg = {
            "note_id": note.__class__.__name__,
            "subject": note.subject,
            "category": note.category.name,
            "level": note.level.name,
            "summary": note.summary,
        }
        if note.subnotes:
            msg["subnotes"] = [self.format_note(subnote) for subnote in note.subnotes]
        return msg


def isoformat(timestamp: float) -> str:
    return f"{datetime.datetime.utcfromtimestamp(timestamp).isoformat()}Z"


def format_media_type(content_type: Optional[Tuple[str, Dict[str, Optional[str]]]]) -> str:
    "Serialise a parsed (media type, parameters) pair as a string, as HAR requires."
    if not content_type:
        return ""
    media_type, params = content_type
    out = [media_type]
    for name, value in params.items():
        if value is None:
            out.append(name)
        elif TOKEN_RE.fullmatch(value):
            out.append(f"{name}={value}")
        else:
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            out.append(f'{name}="{escaped}"')
    return "; ".join(out)
