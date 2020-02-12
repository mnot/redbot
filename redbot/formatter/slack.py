#!/usr/bin/env python

"""
Slack Formatter for REDbot.
"""

import json
from typing import Any, List, Dict

import thor.http.error as httperr

from redbot.formatter import Formatter
from redbot.message import HttpResponse
from redbot.resource import HttpResource
from redbot.resource.fetch import RedHttpClient
from redbot.speak import categories

NL = "\n"


class SlackFormatter(Formatter):
    """
    Slack formatter."""

    media_type = "text/plain"

    note_categories = [
        categories.GENERAL,
        categories.SECURITY,
        categories.CONNECTION,
        categories.CONNEG,
        categories.CACHING,
        categories.VALIDATION,
        categories.RANGE,
    ]

    def __init__(self, *args: Any, **kw: Any) -> None:
        Formatter.__init__(self, *args, **kw)

    def start_output(self) -> None:
        self.output("starting...")

    def feed(self, sample: bytes) -> None:
        pass

    def status(self, status: str) -> None:
        pass

    def finish_output(self) -> None:
        if self.resource.response.complete:
            # success
            blocks = [
                self.format_headers(self.resource.response)
            ] + self.format_recommendations(self.resource.response)
        else:
            blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": ""}}]
            if self.resource.response.http_error is None:
                blocks[0]["text"]["text"] = "no response error."
            elif isinstance(self.resource.response.http_error, httperr.HttpError):
                blocks[0]["text"]["text"] = "HTTP error."
            else:
                blocks[0]["text"]["text"] = "Unknown incomplete response error."
        payload = json.dumps({"blocks": blocks})

        client = RedHttpClient()
        client.request_start(
            b"POST", self.kw["slack_uri"], [("content-type", "application/json")]
        )
        client.request_body(payload)
        client.request_done()

    def error_output(self, message: str) -> None:
        self.output(message)

    def format_headers(self, response: HttpResponse) -> Dict:
        status_line = (
            f"HTTP/{response.version} {response.status_code} {response.status_phrase}\n"
        )
        headers = NL.join([f"{name}:{value}" for (name, value) in response.headers])
        return {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"```{status_line}{headers}```"},
        }

    def format_recommendations(self, resource: HttpResource) -> List:
        return [
            self.format_recommendation(resource, category)
            for category in self.note_categories
        ]

    def format_recommendation(
        self, resource: HttpResource, category: categories
    ) -> Dict:
        notes = [note for note in resource.notes if note.category == category]
        if not notes:
            return {}
        out = []
        if [note for note in notes]:
            out.append(f"*{category.value}*")
        for thing in notes:
            out.append(f" • {thing.show_summary('en')}")
        out.append(NL)
        return {"type": "section", "text": {"type": "mrkdwn", "text": NL.join(out)}}
