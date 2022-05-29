"""
Slack Formatter for REDbot.
"""

import json
from typing import Any, List, Dict, Union

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
        levels.GOOD: ":white_check_mark:",
        levels.WARN: ":warning:",
        levels.BAD: ":no_entry:",
        levels.INFO: ":information_source:",
    }

    def __init__(self, *args: Any, **kw: Any) -> None:
        Formatter.__init__(self, *args, **kw)

    def start_output(self) -> None:
        pass

    def feed(self, sample: bytes) -> None:
        pass

    def status(self, status: str) -> None:
        pass

    def finish_output(self) -> None:
        if self.resource.response.complete:
            # success
            notification = None
            blocks = (
                self.format_headers(self.resource.response)
                + self.format_recommendations(self.resource)
                + self.link_saved()
            )
        else:
            if self.resource.response.http_error is None:
                notification = "No response error."
            elif isinstance(self.resource.response.http_error, httperr.HttpError):
                notification = (
                    f"Sorry, I can't do that; {self.resource.response.http_error.desc}"
                )
            else:
                notification = "Unknown incomplete response error."
            blocks = [self.markdown_block(f"_{notification}_")]
        self.send_slack_message(blocks, notification)

    def error_output(self, message: str) -> None:
        self.output(message)

    def timeout(self) -> None:
        self.send_slack_message([self.markdown_block("_Timed out._")], "Timed out.")

    def send_slack_message(self, blocks: List[Dict], notification: str = None) -> None:
        data: Dict[str, Any] = {"blocks": blocks}
        if notification:
            data["text"] = notification
        payload = json.dumps(data)
        client = RedHttpClient().exchange()
        client.request_start(
            b"POST",
            self.kw["slack_uri"].encode("utf-8"),
            [(b"content-type", b"application/json")],
        )
        client.request_body(payload.encode("utf-8"))
        client.request_done([])

    @staticmethod
    def markdown_block(content: str) -> Dict:
        return {
            "type": "section",
            "text": {"type": "mrkdwn", "text": content},
        }

    def format_headers(self, response: HttpResponse) -> List:
        status_line = (
            f"HTTP/{response.version} {response.status_code} {response.status_phrase}\n"
        )
        headers = NL.join([f"{name}:{value}" for (name, value) in response.headers])
        return [self.markdown_block(f"```{status_line}{headers}```")]

    def format_recommendations(self, resource: HttpResource) -> List:
        out = []
        for category in self.note_categories:
            rec = self.format_recommendation(resource, category)
            if rec:
                out.append(rec)
        return out

    def format_recommendation(
        self, resource: HttpResource, category: categories
    ) -> Union[Dict, None]:
        notes = [note for note in resource.notes if note.category == category]
        if not notes:
            return None
        out = []
        if list(notes):
            out.append(f"*{category.value}*")
        for thing in notes:
            out.append(
                f" {self.emoji.get(thing.level, '•')} {thing.show_summary('en')}"
            )
        out.append(NL)
        return self.markdown_block(NL.join(out))

    def link_saved(self) -> List:
        test_id = self.kw.get("test_id", None)
        if test_id:
            saved_link = f"{self.config['ui_uri']}?id={test_id}"
            return [self.markdown_block(f"_See more detail <{saved_link}|here>._")]
        return []
