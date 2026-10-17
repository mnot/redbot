#!/usr/bin/env python3

import hmac
import time
import unittest
from configparser import ConfigParser
from types import SimpleNamespace
from typing import Any, List, Tuple

from redbot.webui.captcha import CaptchaHandler


class TestCaptchaCookies(unittest.TestCase):
    secret = "s3cret"

    def _handler(
        self, cookie_lines: List[bytes], name: bytes = b"cookie"
    ) -> Tuple[CaptchaHandler, List[Any], List[Any]]:
        parser = ConfigParser()
        parser.read_dict(
            {
                "redbot": {
                    "captcha_provider": "hcaptcha",
                    "captcha_secret": self.secret,
                    "captcha_sitekey": "key",
                }
            }
        )
        webui = SimpleNamespace(
            config=parser["redbot"],
            req_headers=[(name, line) for line in cookie_lines],
            req_body=b"",
            charset="utf-8",
            get_client_ip=lambda: "192.0.2.1",
        )
        continued: List[Any] = []
        errors: List[Any] = []
        handler = CaptchaHandler(
            webui,
            lambda *a: continued.append(a),
            lambda *a: errors.append(a),
        )
        return handler, continued, errors

    def _token(self) -> Tuple[str, str]:
        human_time = str(int(time.time()) + 300)
        human_hmac = hmac.new(self.secret.encode(), human_time.encode(), "sha512").hexdigest()
        return human_time, human_hmac

    def test_single_cookie_line(self) -> None:
        human_time, human_hmac = self._token()
        handler, continued, errors = self._handler(
            [f"human_time={human_time}; human_hmac={human_hmac}".encode()]
        )
        handler.run()
        self.assertEqual(len(continued), 1)
        self.assertEqual(errors, [])

    def test_multiple_cookie_lines(self) -> None:
        human_time, human_hmac = self._token()
        handler, continued, errors = self._handler(
            [f"human_time={human_time}".encode(), f"human_hmac={human_hmac}".encode()]
        )
        handler.run()
        self.assertEqual(len(continued), 1)
        self.assertEqual(errors, [])

    def _assert_accepted(self, cookie_lines: List[bytes], name: bytes = b"cookie") -> None:
        handler, continued, errors = self._handler(cookie_lines, name)
        handler.run()
        self.assertEqual(len(continued), 1)
        self.assertEqual(errors, [])

    def test_trailing_semicolon(self) -> None:
        human_time, human_hmac = self._token()
        self._assert_accepted(
            [f"human_time={human_time};".encode(), f"human_hmac={human_hmac};".encode()]
        )

    def test_empty_cookie_line(self) -> None:
        human_time, human_hmac = self._token()
        self._assert_accepted(
            [f"human_time={human_time}".encode(), b"", f"human_hmac={human_hmac}".encode()]
        )

    def test_comma_in_value(self) -> None:
        human_time, human_hmac = self._token()
        self._assert_accepted(
            [b"foo=a,b", f"human_time={human_time}; human_hmac={human_hmac}".encode()]
        )

    def test_header_name_case(self) -> None:
        human_time, human_hmac = self._token()
        self._assert_accepted(
            [f"human_time={human_time}; human_hmac={human_hmac}".encode()], name=b"Cookie"
        )

    def test_malformed_earlier_line(self) -> None:
        human_time, human_hmac = self._token()
        self._assert_accepted(
            [b"a=b c", f"human_time={human_time}; human_hmac={human_hmac}".encode()]
        )

    def _assert_rejected(self, cookie_lines: List[bytes]) -> None:
        handler, continued, errors = self._handler(cookie_lines)
        handler.run()
        self.assertEqual(continued, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0][0], b"403")

    def test_non_ascii_hmac(self) -> None:
        # SimpleCookie unquotes the octal escape to "\xe9"
        self._assert_rejected([b'human_time=9999999999; human_hmac="\\351"'])

    def test_non_ascii_time(self) -> None:
        # "\xb2" passes str.isdigit() but not int()
        self._assert_rejected([b'human_time="\\262"; human_hmac=abc'])

    def test_non_ascii_both(self) -> None:
        self._assert_rejected([b'human_time="\\262"; human_hmac="\\351"'])

    def test_invalid_utf8(self) -> None:
        # Boundary: SimpleCookie already drops this, so it passes without the fix too.
        self._assert_rejected([b"human_time=9999999999; human_hmac=\xff\xfe"])

    def test_non_ascii_digits_in_time(self) -> None:
        # int() accepts these, so a valid token must not be accepted in this form
        human_time, human_hmac = self._token()
        arabic_indic = human_time.translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))
        self.assertEqual(int(arabic_indic), int(human_time))
        self._assert_rejected(
            [f'human_time="{arabic_indic}"; human_hmac={human_hmac}'.encode("utf-8")]
        )

    def test_overlong_time(self) -> None:
        # more digits than int() will convert
        self._assert_rejected([b"human_time=" + b"9" * 5000 + b"; human_hmac=abc"])

    def test_huge_time(self) -> None:
        # Boundary: under int()'s digit limit, so it passes without the fix too.
        self._assert_rejected([b"human_time=" + b"9" * 400 + b"; human_hmac=abc"])

    def test_negative_time(self) -> None:
        self._assert_rejected([b"human_time=-1; human_hmac=abc"])

    def test_empty_values(self) -> None:
        self._assert_rejected([b"human_time=; human_hmac="])

    def test_whitespace_values(self) -> None:
        self._assert_rejected([b'human_time=" "; human_hmac=" "'])

    def test_missing_hmac(self) -> None:
        self._assert_rejected([b"human_time=9999999999"])

    def test_wrong_hmac(self) -> None:
        self._assert_rejected([b"human_time=9999999999; human_hmac=abc"])

    def test_expired_token(self) -> None:
        human_time = str(int(time.time()) - 10)
        human_hmac = hmac.new(self.secret.encode(), human_time.encode(), "sha512").hexdigest()
        self._assert_rejected([f"human_time={human_time}; human_hmac={human_hmac}".encode()])


if __name__ == "__main__":
    unittest.main()
