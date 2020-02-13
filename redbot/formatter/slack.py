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
from redbot.speak import categories, levels

NL = "\n"


class SlackFormatter(Formatter):
    """
    Slack formatter."""

    media_type = "application/json"

    note_categories = [
        categories.GENERAL,
        categories.SECURITY,
        categories.CONNECTION,
        categories.CONNEG,
        categories.CACHING,
        categories.VALIDATION,
        categories.RANGE,
    ]
    emoji = {
        levels.GOOD: ":small_blue_diamond:",
        levels.WARN: ":small_orange_diamond:",
        levels.BAD: ":small_red_triangle:",
        levels.INFO: ":black_small_square:"
    }

    def __init__(self, *args: Any, **kw: Any) -> None:
        Formatter.__init__(self, *args, **kw)

    def start_output(self) -> None:
        self.output(json.dumps({
            "response_type": "ephemeral",
            "text": f"_Checking_ {self.resource.request.uri} _..._"
        }))

    def feed(self, sample: bytes) -> None:
        pass

    def status(self, status: str) -> None:
        pass

    def finish_output(self) -> None:
        if self.resource.response.complete:
            # success
            blocks = [
                self.format_headers(self.resource.response)
            ] + self.format_recommendations(self.resource)
        else:
            blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": ""}}]
            if self.resource.response.http_error is None:
                blocks[0]["text"]["text"] = "_No response error._"
            elif isinstance(self.resource.response.http_error, httperr.HttpError):
                blocks[0]["text"]["text"] = f"_Sorry, I can't do that; {self.resource.response.http_error.desc}_"
            else:
                blocks[0]["text"]["text"] = "_Unknown incomplete response error._"
        payload = json.dumps({"blocks": blocks})

        client = RedHttpClient().exchange()
        client.request_start(
            b"POST",
            self.kw["slack_uri"].encode("utf-8"),
            [(b"content-type", b"application/json")],
        )
        client.request_body(payload.encode("utf-8"))
        client.request_done([])

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
        out = []
        for category in self.note_categories:
            rec = self.format_recommendation(resource, category)
            if rec:
                out.append(rec)
        return out

    def format_recommendation(
        self, resource: HttpResource, category: categories
    ) -> Dict:
        notes = [note for note in resource.notes if note.category == category]
        if not notes:
            return
        out = []
        if [note for note in notes]:
            out.append(f"*{category.value}*")
        for thing in notes:
            out.append(f" {self.emoji.get(thing.level, '•')} {thing.show_summary('en')}")
        out.append(NL)
        return {"type": "section", "text": {"type": "mrkdwn", "text": NL.join(out)}}

