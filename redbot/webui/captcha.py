import hmac
from http import cookies
import json
import time
from typing import Callable, Dict, TYPE_CHECKING
from urllib.parse import urlencode

import thor
from thor.http import HttpClient, get_header
from thor.http.error import HttpError

from redbot.type import RawHeaderListType

token_client = HttpClient()
token_client.idle_timeout = 30
token_client.connect_timeout = 10
token_client.read_timeout = 10
token_client.max_server_conn = 30

if TYPE_CHECKING:
    from redbot.webui import RedWebUi  # pylint: disable=cyclic-import,unused-import

CAPTCHA_PROVIDERS: Dict[str, Dict[str, bytes]] = {
    "hcaptcha": {
        "verify_url": b"https://hcaptcha.com/siteverify",
        "script_url": b"https://hcaptcha.com/1/api.js?onload=loadDone&render=explicit",
    },
    "turnstile": {
        "verify_url": b"https://challenges.cloudflare.com/turnstile/v0/siteverify",
        "script_url": b"https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit",
    },
}


class CaptchaHandler:
    def __init__(
        self,
        webui: "RedWebUi",
        continue_test: Callable,
        error_response: Callable,
    ) -> None:
        self.webui = webui
        self.client_ip = webui.get_client_ip()
        self.continue_test = continue_test
        self.error_response = error_response
        self.provider = webui.config.get("captcha_provider", "")
        self.secret = webui.config.get("captcha_secret", "").encode("utf-8")
        self.token_lifetime = webui.config.getint("token_lifetime", fallback=300)

    def configured(self) -> bool:
        if (
            CAPTCHA_PROVIDERS.get(self.provider, "")
            and self.secret
            and self.webui.config.get("captcha_sitekey")
        ):
            return True
        return False

    def run(self) -> None:
        captcha_token = self.webui.body_args.get("captcha_token", [None])[0]
        cookie_str = b", ".join(get_header(self.webui.req_headers, b"cookie"))
        try:
            cookiejar: cookies.SimpleCookie = cookies.SimpleCookie(
                cookie_str.decode("utf-8", "replace")
            )
        except cookies.CookieError:
            self.error_response(
                b"400",
                b"Bad Request",
                "Sorry, your cookies appear corrupted. Please try again.",
                f"Cookie Parse Error: {cookie_str.decode('utf-8', 'replace')}",
            )
            return
        human_time = cookiejar.get("human_time", None)
        human_hmac = cookiejar.get("human_hmac", None)

        if human_time and human_time.value.isdigit() and human_hmac:
            if self.verify_human(int(human_time.value), human_hmac.value):
                self.continue_test()
            else:
                self.error_response(
                    b"403",
                    b"Forbidden",
                    "I need to double-check that you're human; please resubmit.",
                )
        elif captcha_token:
            self.verify_captcha(captcha_token)
        else:
            self.error_response(
                b"403",
                b"Forbidden",
                "I need to double-check that you're human; please resubmit.",
            )

    def verify_captcha(self, presented_token: str) -> None:
        exchange = token_client.exchange()

        @thor.events.on(exchange)
        def error(err_msg: HttpError) -> None:
            self.error_response(
                b"403",
                b"Forbidden",
                "There was a problem with the captcha server; please try again soon.",
                f"Captcha error: {err_msg}.",
            )

        @thor.events.on(exchange)
        def response_start(
            status: bytes, phrase: bytes, headers: RawHeaderListType
        ) -> None:
            exchange.tmp_status = status  # type: ignore[attr-defined]

        exchange.tmp_res_body = b""  # type: ignore[attr-defined]

        @thor.events.on(exchange)
        def response_body(chunk: bytes) -> None:
            exchange.tmp_res_body += chunk  # type: ignore[attr-defined]

        @thor.events.on(exchange)
        def response_done(_: RawHeaderListType) -> None:
            try:
                results = json.loads(exchange.tmp_res_body)  # type: ignore[attr-defined]
            except ValueError:
                if exchange.tmp_status != b"200":  # type: ignore[attr-defined]
                    status = exchange.tmp_status.decode("utf-8")  # type: ignore[attr-defined]
                    e_str = f"Captcha server returned {status} status code"
                else:
                    e_str = "Captcha server response error"
                self.error_response(
                    b"500",
                    b"Internal Server Error",
                    e_str,
                    e_str,
                )
                return
            if results.get("success", False):
                self.continue_test(self.issue_human())
            else:
                e_str = (
                    "Captcha errors:"
                    f"{', '.join(results.get('error-codes', ['unknown error']))}"
                )
                self.error_response(
                    b"403",
                    b"Forbidden",
                    e_str,
                    e_str,
                )

        request_form = {
            "secret": self.secret,
            "response": presented_token,
            "remoteip": self.client_ip,
        }
        exchange.request_start(
            b"POST",
            CAPTCHA_PROVIDERS[self.provider]["verify_url"],
            [(b"content-type", b"application/x-www-form-urlencoded")],
        )
        exchange.request_body(urlencode(request_form).encode("utf-8", "replace"))
        exchange.request_done([])

    def issue_human(self) -> RawHeaderListType:
        """
        Return cookie headers for later verification that this is a human.
        """
        human_time = str(int(time.time()) + self.token_lifetime)
        human_hmac = hmac.new(
            self.secret, bytes(human_time, "ascii"), "sha512"
        ).hexdigest()
        return [
            (
                b"Set-Cookie",
                f"human_time={human_time}; Max-Age={self.token_lifetime}; SameSite=Strict".encode(
                    "ascii"
                ),
            ),
            (
                b"Set-Cookie",
                f"human_hmac={human_hmac}; Max-Age={self.token_lifetime}; SameSite=Strict".encode(
                    "ascii"
                ),
            ),
        ]

    def verify_human(self, human_time: int, human_hmac: str) -> bool:
        """
        Check the user's human HMAC.
        """
        computed_hmac = hmac.new(self.secret, bytes(str(human_time), "ascii"), "sha512")
        is_valid = human_hmac == computed_hmac.hexdigest()
        return bool(is_valid and human_time >= time.time())
