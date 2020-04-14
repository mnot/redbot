import hmac
import json
from typing import TYPE_CHECKING
from urllib.parse import parse_qs

import thor
from thor.http import get_header

from redbot.formatter import slack
from redbot.resource import HttpResource
from redbot.webui.saved_tests import save_test

if TYPE_CHECKING:
    from redbot.webui import RedWebUi  # pylint: disable=cyclic-import,unused-import


def run_slack(webui: "RedWebUi") -> None:
    """Handle a slack request."""
    body = parse_qs(webui.req_body.decode("utf-8"))
    slack_response_uri = body.get("response_url", [""])[0].strip()
    formatter = slack.SlackFormatter(
        webui.config, webui.output, slack_uri=slack_response_uri
    )
    webui.test_uri = body.get("text", [""])[0].strip()

    webui.response_start(
        b"200",
        b"OK",
        [
            (b"Content-Type", formatter.content_type()),
            (b"Cache-Control", b"max-age=300"),
        ],
    )
    webui.output(
        json.dumps(
            {
                "response_type": "ephemeral",
                "text": f"_Checking_ {webui.test_uri} _..._",
            }
        )
    )
    webui.response_done([])

    top_resource = HttpResource(webui.config)
    top_resource.set_request(webui.test_uri, req_hdrs=webui.req_hdrs)
    formatter.bind_resource(top_resource)
    if not verify_slack_secret(webui):
        webui.error_response(
            formatter,
            b"403",
            b"Forbidden",
            "Incorrect Slack Authentication.",
            "Bad slack token.",
        )
        return
    webui.timeout = thor.schedule(int(webui.config["max_runtime"]), webui.timeoutError)

    @thor.events.on(formatter)
    def formatter_done() -> None:
        save_test(webui, top_resource)

    top_resource.check()


def verify_slack_secret(webui: "RedWebUi") -> bool:
    """Verify the slack secret."""
    slack_signing_secret = webui.config.get("slack_signing_secret", fallback="").encode(
        "utf-8"
    )
    timestamp = get_header(webui.req_headers, b"x-slack-request-timestamp")
    if not timestamp or not timestamp[0].isdigit():
        return False
    timestamp = timestamp[0]
    if abs(thor.time() - int(timestamp)) > 60 * 5:
        return False
    sig_basestring = b"v0:" + timestamp + b":" + webui.req_body
    signature = (
        f"v0={hmac.new(slack_signing_secret, sig_basestring, 'sha256').hexdigest()}"
    )
    presented_signature = get_header(webui.req_headers, b"x-slack-signature")
    if not presented_signature:
        return False
    presented_sig = presented_signature[0].decode("utf-8")
    return hmac.compare_digest(signature, presented_sig)
