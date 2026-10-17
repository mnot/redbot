#!/usr/bin/env python3

# pylint: disable=consider-using-with

import hmac
import http.server
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from configparser import ConfigParser
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import patch

import thor.events
from thor.http.error import HttpError

from redbot.webui.captcha import MAX_REPLY_SIZE, CaptchaHandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


class FakeExchange(thor.events.EventEmitter):
    "Stands in for the provider exchange, so tests can emit its events."

    def request_start(self, *args: Any) -> None:
        pass

    def request_body(self, *args: Any) -> None:
        pass

    def request_done(self, *args: Any) -> None:
        pass


class ReplyTestCase(unittest.TestCase):
    """
    #486: the callbacks on the provider exchange run from thor's loop, so anything they raise
    stops the daemon. Whatever the provider sends must end in continue_test or error_response.
    """

    def verify(
        self,
        body: bytes,
        status: bytes = b"200",
        chunks: Optional[List[bytes]] = None,
        error_first: bool = False,
        error_last: bool = False,
    ) -> Tuple[List[Any], List[Any]]:
        parser = ConfigParser()
        parser.read_dict(
            {
                "redbot": {
                    "captcha_provider": "hcaptcha",
                    "captcha_secret": "s3cret",
                    "captcha_sitekey": "key",
                }
            }
        )
        webui: Any = SimpleNamespace(config=parser["redbot"], get_client_ip=lambda: "192.0.2.1")
        continued: List[Any] = []
        errors: List[Any] = []
        handler = CaptchaHandler(
            webui,
            lambda *a: continued.append(a),
            lambda *a: errors.append(a),
        )
        exchange = FakeExchange()
        with patch("redbot.webui.captcha.token_client") as client:
            client.exchange.return_value = exchange
            handler.verify_captcha("token")
        if error_first:
            exchange.emit("error", HttpError("connect failed"))
        exchange.emit("response_start", status, b"phrase", [])
        for chunk in [body] if chunks is None else chunks:
            exchange.emit("response_body", chunk)
        exchange.emit("response_done", [])
        if error_last:
            exchange.emit("error", HttpError("late"))
        return continued, errors

    def assert_error(self, body: bytes, code: bytes, **kwargs: Any) -> str:
        continued, errors = self.verify(body, **kwargs)
        self.assertEqual(continued, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0][0], code)
        self.assertEqual(errors[0][2], errors[0][3])  # shown and logged alike
        return str(errors[0][2])


class TestCaptchaVerifyReply(ReplyTestCase):
    def test_success(self) -> None:
        continued, errors = self.verify(b'{"success": true}')
        self.assertEqual(len(continued), 1)
        self.assertEqual(errors, [])

    def test_failure_with_codes(self) -> None:
        message = self.assert_error(
            b'{"success": false, "error-codes": ["invalid-input-response", "timeout"]}', b"403"
        )
        self.assertIn("invalid-input-response, timeout", message)

    def test_failure_without_codes(self) -> None:
        self.assertIn("unknown error", self.assert_error(b'{"success": false}', b"403"))

    def test_reply_is_not_an_object(self) -> None:
        for body in [b"null", b"[]", b'"x"', b"1", b"true", b'[{"success": true}]']:
            with self.subTest(body=body):
                message = self.assert_error(body, b"500")
                self.assertEqual(message, "Captcha server response error")

    def test_bad_error_codes(self) -> None:
        for codes in ["null", "[]", "[1]", '"abc"', '{"a": 1}', "[null, [2], {}]", "1.5", "true"]:
            with self.subTest(codes=codes):
                body = f'{{"success": false, "error-codes": {codes}}}'.encode()
                message = self.assert_error(body, b"403")
                self.assertTrue(message.startswith("Captcha errors:"))

    def test_error_codes_are_coerced(self) -> None:
        body = b'{"success": false, "error-codes": [1, null, "x", [2]]}'
        message = self.assert_error(body, b"403")
        self.assertEqual(message, "Captcha errors:1, None, x, [2]")

    def test_success_must_be_true(self) -> None:
        for value in ['"true"', '"yes"', "1", '{"a": 1}', "[true]", "null", "false", "0", '""']:
            with self.subTest(success=value):
                self.assert_error(f'{{"success": {value}}}'.encode(), b"403")

    def test_non_200_is_never_success(self) -> None:
        for status in [b"500", b"403", b"302"]:
            with self.subTest(status=status):
                message = self.assert_error(b'{"success": true}', b"500", status=status)
                self.assertEqual(message, f"Captcha server returned {status.decode()} status code")

    def test_non_200_not_json(self) -> None:
        message = self.assert_error(b"<html>oops</html>", b"500", status=b"502")
        self.assertEqual(message, "Captcha server returned 502 status code")

    def test_odd_status_bytes(self) -> None:
        message = self.assert_error(b"{}", b"500", status=b"\xff\x1b[31m")
        self.assertNotIn("\x1b", message)

    def test_not_json(self) -> None:
        for body in [b"", b"not json", b"{", b"{'success': true}"]:
            with self.subTest(body=body):
                message = self.assert_error(body, b"500")
                self.assertEqual(message, "Captcha server response error")

    def test_invalid_utf8(self) -> None:
        for body in [b'{"success": true, "x": "\xff"}', b"\xff\xfe\x00", b"\xef\xbb\xbf\xff"]:
            with self.subTest(body=body):
                self.assert_error(body, b"500")


class TestCaptchaVerifyLimits(ReplyTestCase):
    def test_deeply_nested(self) -> None:
        # json.loads raises RecursionError, not ValueError, for this
        self.assert_error(b"[" * 50000, b"500")
        self.assert_error(b'{"success": false, "a": ' + b"[" * 50000, b"500")

    def test_oversized_reply(self) -> None:
        body = b'{"success": true, "pad": "' + b"x" * MAX_REPLY_SIZE + b'"}'
        self.assert_error(body, b"500")
        chunks = [body[i : i + 4096] for i in range(0, len(body), 4096)]
        self.assert_error(body, b"500", chunks=chunks)

    def test_reply_at_the_size_limit(self) -> None:
        head = b'{"success": true, "pad": "'
        body = head + b"x" * (MAX_REPLY_SIZE - len(head) - 2) + b'"}'
        self.assertEqual(len(body), MAX_REPLY_SIZE)
        continued, errors = self.verify(body)
        self.assertEqual(len(continued), 1)
        self.assertEqual(errors, [])

    def test_chunked_reply(self) -> None:
        continued, _ = self.verify(b"", chunks=[b'{"succ', b'ess": tr', b"ue}"])
        self.assertEqual(len(continued), 1)

    def test_controls_in_codes(self) -> None:
        body = b'{"success": false, "error-codes": ["\\u001b[31mred\\u202e\\u0007\\n\\u0085"]}'
        message = self.assert_error(body, b"403")
        for code in [0x1B, 0x202E, 0x07, 0x0A, 0x85]:
            self.assertNotIn(chr(code), message)
        self.assertIn("\\x1b[31mred", message)

    def test_error_codes_are_bounded(self) -> None:
        codes = b",".join([b'"' + b"x" * 500 + b'"'] * 100)
        message = self.assert_error(b'{"success": false, "error-codes": [' + codes + b"]}", b"403")
        self.assertLess(len(message), 1000)

    def test_connection_error(self) -> None:
        # a reply that follows an error must not produce a second response
        _, errors = self.verify(b'{"success": true}', error_first=True)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0][0], b"403")

    def test_late_error_is_ignored(self) -> None:
        continued, errors = self.verify(b'{"success": true}', error_last=True)
        self.assertEqual(len(continued), 1)
        self.assertEqual(errors, [])


class Provider(http.server.BaseHTTPRequestHandler):
    "A stand-in captcha provider; the class attribute holds what it replies with next."

    reply: Dict[str, Any] = {}

    def do_POST(self) -> None:  # pylint: disable=invalid-name
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if self.reply["body"] is None:
            self.close_connection = True  # no response at all
            return
        self.send_response(self.reply["status"])
        self.send_header("Content-Length", str(len(self.reply["body"])))
        self.end_headers()
        self.wfile.write(self.reply["body"])

    def log_message(self, *args: Any) -> None:  # pylint: disable=arguments-differ
        pass


class Target(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # pylint: disable=invalid-name
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args: Any) -> None:  # pylint: disable=arguments-differ
        pass


# Only ever points the daemon at a local stub; nothing here contacts a real provider.
LAUNCHER = """
import sys
from redbot.webui import captcha
url = sys.argv[1].encode()
assert url.startswith(b"http://127.0.0.1:"), url
captcha.CAPTCHA_PROVIDERS["hcaptcha"]["verify_url"] = url
from redbot.daemon import main
sys.argv = ["redbot", sys.argv[2]]
main()
"""


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


class TestDaemonSurvivesBadCaptchaReplies(unittest.TestCase):
    "#486: a real daemon, with the provider replaced by a local stub."

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        servers = []
        for handler in [Provider, Target]:
            server = http.server.HTTPServer(("127.0.0.1", 0), handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
            servers.append(server)
        provider_url = f"http://127.0.0.1:{servers[0].server_address[1]}/siteverify"
        self.target_port = servers[1].server_address[1]

        self.port = free_port()
        conf_file = os.path.join(tmp.name, "config.txt")
        with open(conf_file, "w", encoding="utf-8") as fh:
            fh.write(
                "[redbot]\nhost = 127.0.0.1\nstatic_root = static\nenable_local_access = True\n"
                f"port = {self.port}\ncaptcha_provider = hcaptcha\n"
                "captcha_secret = placeholder-secret\ncaptcha_sitekey = placeholder-sitekey\n"
            )
        self.daemon = subprocess.Popen(
            [sys.executable, "-c", LAUNCHER, provider_url, conf_file],
            cwd=ROOT,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.stderr = ""
        self.addCleanup(self.stop_daemon)
        deadline = time.time() + 20
        while time.time() < deadline:
            self.assertIsNone(self.daemon.poll(), "daemon exited during startup")
            try:
                socket.create_connection(("127.0.0.1", self.port), timeout=1).close()
                return
            except OSError:
                time.sleep(0.1)
        self.fail("daemon did not start")

    def stop_daemon(self) -> None:
        "Stop the daemon and collect its stderr; safe to call twice."
        if self.daemon.poll() is None:
            self.daemon.terminate()
        try:
            _, err = self.daemon.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            self.daemon.kill()
            _, err = self.daemon.communicate()
        self.stderr = self.stderr or err or ""

    def check(self, body: Optional[bytes], status: int = 200) -> Tuple[int, str]:
        Provider.reply = {"status": status, "body": body}
        uri = f"http://127.0.0.1:{self.target_port}/"
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/check?uri={uri}",
            data=b"captcha_token=abc",
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, response.read().decode("utf-8")
        except urllib.error.HTTPError as err:
            return err.code, err.read().decode("utf-8")

    def test_bad_replies(self) -> None:
        cases: List[Tuple[Optional[bytes], int, int]] = [
            (b"null", 200, 500),
            (b"[]", 200, 500),
            (b'"x"', 200, 500),
            (b'{"success": false, "error-codes": null}', 200, 403),
            (b'{"success": false, "error-codes": [1]}', 200, 403),
            (b'{"success": false, "error-codes": "bad"}', 200, 403),
            (b'{"success": "yes"}', 200, 403),
            (b"[" * 50000, 200, 500),
            (b"not json", 200, 500),
            (b"\xff\xfe", 200, 500),
            (b'{"success": true, "pad": "' + b"x" * 200000 + b'"}', 200, 500),
            (b'{"success": true}', 500, 500),
            (b"", 204, 500),
            (None, 200, 403),
        ]
        for body, status, expected in cases:
            with self.subTest(body=None if body is None else body[:40], status=status):
                got, page = self.check(body, status)
                self.assertEqual(got, expected)
                self.assertIn("</html>", page)
                self.assertIsNone(self.daemon.poll(), "daemon exited")

    def test_failure_text_is_escaped(self) -> None:
        got, page = self.check(
            b'{"success": false, "error-codes": ["<script>alert(1)</script>", "\\u001b[31m"]}'
        )
        self.assertEqual(got, 403)
        self.assertIn("&lt;script&gt;alert(1)", page)
        self.assertNotIn("<script>alert(1)", page)
        self.stop_daemon()
        self.assertNotIn("\x1b", self.stderr)
        self.assertIn("\\x1b[31m", self.stderr)

    def test_daemon_keeps_serving(self) -> None:
        self.check(b"null")
        self.check(b'{"success": false, "error-codes": [1]}')
        got, _ = self.check(b'{"success": true}')
        self.assertEqual(got, 200)
        self.assertIsNone(self.daemon.poll(), "daemon exited")
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/", timeout=10) as response:
            self.assertEqual(response.status, 200)
        self.stop_daemon()
        self.assertNotIn("Traceback", self.stderr)


if __name__ == "__main__":
    unittest.main()
