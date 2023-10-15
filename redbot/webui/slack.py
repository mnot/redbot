import hmac
import json
import time
from typing import TYPE_CHECKING

import thor
from thor.http import get_header

from redbot.formatter import slack
from redbot.resource import HttpResource
from redbot.resource.fetch import RedHttpClient
from redbot.webui.ratelimit import ratelimiter
from redbot.webui.saved_tests import init_save_file, save_test

if TYPE_CHECKING:
    from redbot.webui import RedWebUi  # pylint: disable=cyclic-import,unused-import


def slack_run(webui: "RedWebUi") -> None:
    """Handle a slack request."""
    webui.test_uri = webui.body_args.get("text", [""])[0].strip()
    webui.test_id = init_save_file(webui)
    slack_response_uri = webui.body_args.get("response_url", [""])[0].strip()
    formatter = slack.SlackFormatter(
        webui.config,
        None,
        webui.output,
        slack_uri=slack_response_uri,
        test_id=webui.test_id,
    )

    webui.exchange.response_start(
        b"200",
        b"OK",
        [
            (b"Content-Type", formatter.content_type()),
            (b"Cache-Control", b"max-age=300"),
        ],
    )

    # enforce rate limits
    try:
        ratelimiter.process_slack(webui)
    except ValueError as msg:
        webui.output(
            json.dumps(
                {
                    "response_type": "ephemeral",
                    "text": str(msg),
                }
            )
        )
        webui.exchange.response_done([])
        return  # over limit, don't continue.

    webui.output(
        json.dumps(
            {
                "response_type": "ephemeral",
                "text": f"_Checking_ {webui.test_uri} _..._",
            }
        )
    )
    webui.exchange.response_done([])

    top_resource = HttpResource(webui.config)
    top_resource.set_request(webui.test_uri, headers=webui.req_hdrs)
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
    webui.timeout = thor.schedule(
        webui.config.getint("max_runtime", fallback=60), formatter.timeout
    )

    @thor.events.on(formatter)
    def formatter_done() -> None:
        if webui.timeout:
            webui.timeout.delete()
            webui.timeout = None
        save_test(webui, top_resource)

    top_resource.check()


def verify_slack_secret(webui: "RedWebUi") -> bool:
    """Verify the slack secret."""
    slack_signing_secret = webui.config.get("slack_signing_secret", fallback="").encode(
        "utf-8"
    )
    timestamps = get_header(webui.req_headers, b"x-slack-request-timestamp")
    if not timestamps or not timestamps[0].isdigit():
        return False
    timestamp = timestamps[0]
    if abs(time.time() - int(timestamp)) > 60 * 5:
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


def slack_auth(webui: "RedWebUi") -> None:
    webui.error_log("Slack Auth Redirect received.")
    args = [
        ("code", webui.query_string.get("code", [""])[0]),
        ("client_id", webui.config.get("slack_client_id", fallback="")),
        ("client_secret", webui.config.get("slack_client_secret", fallback="")),
    ]
    payload = "&".join([f"{arg[0]}={arg[1]}" for arg in args])
    client = RedHttpClient().exchange()
    client.request_start(
        b"POST",
        b"https://slack.com/api/oauth.v2.access",
        [(b"content-type", b"application/x-www-form-urlencoded")],
    )
    client.request_body(payload.encode("utf-8"))
    client.request_done([])
    webui.exchange.response_start(b"200", b"OK", [])
    webui.output("Response sent to Slack; your app should be installed.")
    webui.exchange.response_done([])
