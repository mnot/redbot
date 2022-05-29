#!/usr/bin/env python

"""
HAR Formatter for REDbot.
"""


import datetime
import json
from typing import Any, Dict, List
from typing_extensions import TypedDict

from redbot import __version__
from redbot.formatter import Formatter
from redbot.message.headers import StrHeaderListType
from redbot.resource import HttpResource


class HarLogDict(TypedDict):
    version: str
    creator: Dict[str, str]
    browser: Dict[str, str]
    pages: List[Any]
    entries: List[Dict[str, Any]]


class HarDict(TypedDict):
    log: HarLogDict


class HarFormatter(Formatter):
    """
    Format a HttpResource object (and any descendants) as HAR.
    """

    can_multiple = True
    name = "har"
    media_type = "application/json"

    def __init__(self, *args: Any, **kw: Any) -> None:
        Formatter.__init__(self, *args, **kw)
        self.har: HarDict = {
            "log": {
                "version": "1.1",
                "creator": {"name": "REDbot", "version": __version__},
                "browser": {"name": "REDbot", "version": __version__},
                "pages": [],
                "entries": [],
            }
        }
        self.last_id = 0

    def start_output(self) -> None:
        pass

    def status(self, msg: str) -> None:
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
        self.output(message)

    def add_entry(self, resource: HttpResource, page_ref: int = None) -> None:
        entry = {
            "startedDateTime": isoformat(resource.request.start_time),
            "time": int(
                (resource.response.complete_time - resource.request.start_time) * 1000
            ),
            "_red_messages": self.format_notes(resource),
        }
        if page_ref:
            entry["pageref"] = f"page{page_ref}"

        request = {
            "method": resource.request.method,
            "url": resource.request.uri,
            "httpVersion": "HTTP/1.1",
            "cookies": [],
            "headers": self.format_headers(resource.request.headers),
            "queryString": [],
            "headersSize": -1,
            "bodySize": -1,
        }

        response = {
            "status": resource.response.status_code,
            "statusText": resource.response.status_phrase,
            "httpVersion": f"HTTP/{resource.response.version}",
            "cookies": [],
            "headers": self.format_headers(resource.response.headers),
            "content": {
                "size": resource.response.decoded_len,
                "compression": resource.response.decoded_len
                - resource.response.payload_len,
                "mimeType": resource.response.parsed_headers.get("content-type", ""),
            },
            "redirectURL": resource.response.parsed_headers.get("location", ""),
            "headersSize": resource.response.header_length,
            "bodySize": resource.response.payload_len,
        }

        cache: Dict[None, None] = {}
        timings = {
            "dns": -1,
            "connect": -1,
            "blocked": 0,
            "send": 0,
            "wait": int(
                (resource.response.start_time - resource.request.start_time) * 1000
            ),
            "receive": int(
                (resource.response.complete_time - resource.response.start_time) * 1000
            ),
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
        page_id = self.last_id + 1
        page = {
            "startedDateTime": isoformat(resource.request.start_time),
            "id": f"page{page_id}",
            "title": "",
            "pageTimings": {"onContentLoad": -1, "onLoad": -1},
        }
        self.har["log"]["pages"].append(page)
        return page_id

    def format_headers(self, hdrs: StrHeaderListType) -> List[Dict[str, str]]:
        return [{"name": n, "value": v} for n, v in hdrs]

    def format_notes(self, resource: HttpResource) -> List[Dict[str, str]]:
        out = []
        for m in resource.notes:
            msg = {
                "note_id": m.__class__.__name__,
                "subject": m.subject,
                "category": m.category.name,
                "level": m.level.name,
                "summary": m.show_summary(self.lang),
            }
            out.append(msg)
        return out


def isoformat(timestamp: float) -> str:
    return f"{datetime.datetime.utcfromtimestamp(timestamp).isoformat()}Z"
