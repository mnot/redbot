import json
from typing import Callable, TYPE_CHECKING
from urllib.parse import urlencode

import thor
from thor.http import HttpClient
from thor.http.error import HttpError

from redbot.resource import HttpResource
from redbot.type import RawHeaderListType

token_client = HttpClient()

if TYPE_CHECKING:
    from redbot.webui import RedWebUi  # pylint: disable=cyclic-import,unused-import


def handle_captcha(
    webui: "RedWebUi",
    client_id: str,
    continue_test: Callable[[], None],
    error_response: Callable,
) -> None:
    presented_token = webui.body_args.get("captcha_token", [None])[0]
    if not presented_token:
        error_response(
            b"403", b"Forbidden", "Catpcha token required.", "Captcha token required.",
        )
        return
    exchange = token_client.exchange()

    @thor.events.on(exchange)
    def error(err_msg: HttpError) -> None:
        error_response(
            b"403", b"Forbidden", "Catpcha error.", f"Captcha error: {err_msg}.",
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
                f"Captcha returned {exchange.tmp_status.decode('utf-8')} status code"
            )
            error_response(
                b"403", b"Forbidden", e_str, e_str,
            )
            return
        results = json.loads(exchange.tmp_res_body)
        if results["success"]:
            continue_test()
        else:
            e_str = f"Captcha errors: {', '.join(results['error-codes'])}"
            error_response(
                b"403", b"Forbidden", e_str, e_str,
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
