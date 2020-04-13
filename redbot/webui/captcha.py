import json
from typing import TYPE_CHECKING
from urllib.parse import urlencode

import thor
from thor.http import HttpClient
from thor.http.error import HttpError

from redbot.formatter import Formatter
from redbot.resource import HttpResource
from redbot.type import RawHeaderListType

token_client = HttpClient()

if TYPE_CHECKING:
    from redbot.webui import RedWebUi  # pylint: disable=cyclic-import,unused-import


def handle_captcha(
    webui: "RedWebUi",
    top_resource: HttpResource,
    formatter: Formatter,
    presented_token: str,
    client_id: str,
) -> None:
    if not presented_token:
        return webui.error_response(
            formatter,
            b"403",
            b"Forbidden",
            "hCatpcha token required.",
            "hCaptcha token required.",
        )
    exchange = token_client.exchange()

    @thor.events.on(exchange)
    def error(err_msg: HttpError) -> None:
        webui.error_response(
            formatter,
            b"403",
            b"Forbidden",
            "hCatpcha error.",
            f"hCaptcha error: {err_msg}.",
        )

    @thor.events.on(exchange)
    def response_start(
        status: bytes, phrase: bytes, headers: RawHeaderListType
    ) -> None:
        exchange.tmp_status = status

    exchange.tmp_res_body = b""

    @thor.events.on(exchange)
    def response_body(chunk: bytes) -> None:
        exchange.tmp_res_body += chunk

    @thor.events.on(exchange)
    def response_done(trailers: RawHeaderListType) -> None:
        if exchange.tmp_status != b"200":
            e_str = (
                f"hCaptcha returned {exchange.tmp_status.decode('utf-8')} status code"
            )
            return webui.error_response(formatter, b"403", b"Forbidden", e_str, e_str,)
        results = json.loads(exchange.tmp_res_body)
        if results["success"]:
            webui.continue_test(top_resource, formatter)
        else:
            e_str = f"hCaptcha errors: {', '.join([e for e in results['error-codes']])}"
            webui.error_response(
                formatter, b"403", b"Forbidden", e_str, e_str,
            )

    request_form = {
        "secret": webui.config["hcaptcha_secret"],
        "response": presented_token,
        "remoteip": client_id,
    }
    exchange.request_start(
        b"POST",
        b"https://hcaptcha.com/siteverify",
        [[b"content-type", b"application/x-www-form-urlencoded"]],
    )
    exchange.request_body(urlencode(request_form).encode("utf-8", "replace"))
    exchange.request_done({})
