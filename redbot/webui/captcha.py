import hmac
from http import cookies
import json
from typing import Callable, TYPE_CHECKING
from urllib.parse import urlencode

import thor
from thor.http import HttpClient, get_header
from thor.http.error import HttpError

from redbot.resource import HttpResource
from redbot.type import RawHeaderListType

token_client = HttpClient()

if TYPE_CHECKING:
    from redbot.webui import RedWebUi  # pylint: disable=cyclic-import,unused-import


class CaptchaHandler:
    def __init__(
        self,
        webui: "RedWebUi",
        client_id: str,
        continue_test: Callable,
        error_response: Callable,
    ) -> None:
        self.webui = webui
        self.client_id = client_id
        self.continue_test = continue_test
        self.error_response = error_response
        self.secret = webui.config.get("hcaptcha_secret", "").encode("utf-8")
        self.token_lifetime = webui.config.getint("token_lifetime", fallback=300)

    def run(self) -> None:
        captcha_token = self.webui.body_args.get("captcha_token", [None])[0]
        cookie_str = b", ".join(get_header(self.webui.req_headers, b"cookie"))
        try:
            cookiejar = cookies.SimpleCookie(
                cookie_str.decode("utf-8", "replace")
            )  # type: cookies.SimpleCookie
        except cookies.CookieError:
            self.error_response(
                b"400", b"Bad Request", "Cookie Parse Error", "Cookie Parse Error"
            )
            return
        human_time = cookiejar.get("human_time", None)
        human_hmac = cookiejar.get("human_hmac", None)

        import sys

        sys.stderr.write(f"- {cookiejar}\n")

        if human_time and human_time.value.isdigit() and human_hmac:
            if self.verify_human(int(human_time.value), human_hmac.value):
                self.continue_test()
            else:
                self.error_response(
                    b"403", b"Forbidden", "Please resubmit.", "Human token required.",
                )
        elif captcha_token:
            self.verify_captcha(captcha_token)
        else:
            self.error_response(
                b"403", b"Forbidden", "Please resubmit.", "Captcha token required.",
            )

    def verify_captcha(self, presented_token: str) -> None:
        exchange = token_client.exchange()

        @thor.events.on(exchange)
        def error(err_msg: HttpError) -> None:
            self.error_response(
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
            try:
                results = json.loads(exchange.tmp_res_body)
            except ValueError:
                if exchange.tmp_status != b"200":
                    e_str = f"Captcha returned {exchange.tmp_status.decode('utf-8')} status code"
                else:
                    e_str = f"Captcha response decoding error"
                self.error_response(
                    b"500", b"Internal Server Error", e_str, e_str,
                )
                return
            if results["success"]:
                self.continue_test(self.issue_human())
            else:
                e_str = f"Captcha errors: {', '.join(results.get('error-codes', ['unknown error']))}"
                self.error_response(
                    b"403", b"Forbidden", e_str, e_str,
                )

        request_form = {
            "secret": self.secret,
            "response": presented_token,
            "remoteip": self.client_id,
        }
        exchange.request_start(
            b"POST",
            b"https://hcaptcha.com/siteverify",
            [[b"content-type", b"application/x-www-form-urlencoded"]],
        )
        exchange.request_body(urlencode(request_form).encode("utf-8", "replace"))
        exchange.request_done({})

    def issue_human(self) -> RawHeaderListType:
        """
        Return cookie headers for later verification that this is a human.
        """
        human_time = str(int(thor.time()) + self.token_lifetime)
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
        if is_valid and human_time >= thor.time():
            return True
        else:
            return False
