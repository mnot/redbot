#!/usr/bin/env python3

# pylint: disable=consider-using-with

import hmac
import http.server
import os
import socket
import subprocess
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from configparser import ConfigParser
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import ANY, MagicMock, patch

import thor.events
from thor.http.error import HttpError, ReadTimeoutError

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

    def _stale_cookie_handler(self, token: Optional[str]):
        "A handler whose request carries cookies the server no longer accepts."
        human_time = str(int(time.time()) - 10)  # expired
        human_hmac = hmac.new(self.secret.encode(), human_time.encode(), "sha512").hexdigest()
        handler, continued, errors = self._handler(
            [f"human_time={human_time}; human_hmac={human_hmac}".encode()]
        )
        if token is not None:
            handler.webui.req_headers.append(
                (b"content-type", b"application/x-www-form-urlencoded")
            )
            handler.webui.req_body = f"captcha_token={token}".encode()
        handler.verify_captcha = MagicMock()  # type: ignore[method-assign]
        return handler, continued, errors

    def test_stale_cookie_does_not_block_a_solved_captcha(self) -> None:
        handler, continued, errors = self._stale_cookie_handler("solved")
        handler.run()
        handler.verify_captcha.assert_called_once_with("solved")  # type: ignore[attr-defined]
        self.assertEqual((continued, errors), ([], []))

    def test_stale_cookie_without_a_token_is_cleared(self) -> None:
        handler, continued, errors = self._stale_cookie_handler(None)
        handler.run()
        handler.verify_captcha.assert_not_called()  # type: ignore[attr-defined]
        self.assertEqual(continued, [])
        self.assertEqual(errors[0][0], b"403")
        cleared = [value for name, value in errors[0][4] if name == b"Set-Cookie"]
        self.assertEqual(len(cleared), 2)
        for value in cleared:
            self.assertIn(b"Max-Age=0", value)
        self.assertEqual({v.split(b"=")[0] for v in cleared}, {b"human_time", b"human_hmac"})

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


SHOWN_ERROR = "Captcha server response error"
UNKNOWN = "Captcha errors: unknown error"
PADDED = b'{"success": true, "pad": "' + b"x" * MAX_REPLY_SIZE + b'"}'
CODES = b",".join([b'"' + b"x" * 500 + b'"'] * 100)  # capped on the page
# 200 replies: body and what the page shows (a 500 for SHOWN_ERROR, otherwise a 403)
BAD_REPLIES = [
    (b"null", SHOWN_ERROR),
    (b'"x"', SHOWN_ERROR),
    (b"not json", SHOWN_ERROR),
    (b'{"a": "\xff"}', SHOWN_ERROR),
    (b"[" * 50000, SHOWN_ERROR),  # RecursionError
    (PADDED, SHOWN_ERROR),
    (b'{"success": false}', UNKNOWN),
    (b'{"error-codes": null}', UNKNOWN),
    (b'{"success": "true"}', UNKNOWN),
    (b'{"success": 1}', UNKNOWN),
    (b'{"error-codes": [1, null, ["a"]]}', "Captcha errors: 1, None, ['a']"),
    (b'{"error-codes": ["\\u001b[31m\\u202e", "<b>"]}', "Captcha errors: \\x1b[31m\\u202e, <b>"),
    (b'{"error-codes": [' + CODES + b"]}", "Captcha errors: " + ", ".join(["x" * 64] * 10)),
]
# Other statuses are never a success, whatever the body; the codes are logged but not shown.
BAD_STATUSES = [
    (b"302", b'{"success": true}', "Captcha server returned 302 status code", None),
    (b"\xff\x1b[31m", b"{}", "Captcha server returned \ufffd\\x1b[31m status code", None),
    (
        b"400",
        b'{"error-codes": ["bad-request", "\\u001b[31m"]}',
        "Captcha server returned 400 status code",
        "Captcha server returned 400 status code (bad-request, \\x1b[31m)",
    ),
]


class TestCaptchaVerifyReply(unittest.TestCase):
    """
    #486: the callbacks on the provider exchange run from thor's loop, so anything they raise
    stops the daemon. Whatever the provider sends must end in continue_test or error_response.
    """

    def verify(
        self, chunks: List[bytes], status: bytes = b"200", error: Optional[HttpError] = None
    ) -> Tuple[List[Any], List[Any], Any]:
        parser = ConfigParser()
        parser.read_string("[redbot]\ncaptcha_provider = hcaptcha\ncaptcha_secret = s3cret\n")
        webui: Any = SimpleNamespace(config=parser["redbot"], get_client_ip=lambda: "192.0.2.1")
        continued: List[Any] = []
        errors: List[Any] = []
        handler = CaptchaHandler(webui, lambda *a: continued.append(a), lambda *a: errors.append(a))
        exchange: Any = thor.events.EventEmitter()
        exchange.conn = MagicMock()
        exchange.request_start = exchange.request_body = exchange.request_done = MagicMock()
        with patch("redbot.webui.captcha.token_client") as client:
            client.exchange.return_value = exchange
            handler.verify_captcha("token")
        if error:
            exchange.emit("error", error)
        exchange.emit("response_start", status, b"phrase", [])
        for chunk in chunks:
            exchange.emit("response_body", chunk)
        exchange.emit("response_done", [])
        return continued, errors, exchange.conn.tcp_conn.abort

    def assert_rejected(
        self, body: bytes, status: bytes, code: bytes, shown: str, logged: Optional[str]
    ) -> None:
        continued, errors, _ = self.verify([body], status)
        self.assertEqual(continued, [])
        self.assertEqual([e[:4] for e in errors], [(code, ANY, shown, logged or shown)])

    def test_bad_replies(self) -> None:
        for body, shown in BAD_REPLIES:
            with self.subTest(body=body[:40]):
                code = b"500" if shown == SHOWN_ERROR else b"403"
                self.assert_rejected(body, b"200", code, shown, None)
        for status, body, shown, logged in BAD_STATUSES:
            with self.subTest(status=status):
                self.assert_rejected(body, status, b"500", shown, logged)

    def test_success(self) -> None:
        head = b'{"success": true, "pad": "'
        at_limit = head + b"x" * (MAX_REPLY_SIZE - len(head) - 2) + b'"}'
        for body in [b'{"success": true}', at_limit]:
            continued, errors, abort = self.verify([body])
            self.assertEqual((len(continued), errors, abort.called), (1, [], False))

    def test_oversized_reply_is_aborted(self) -> None:
        chunks = [PADDED[i : i + 4096] for i in range(0, len(PADDED), 4096)]
        continued, errors, abort = self.verify(chunks)
        self.assertEqual((continued, len(errors), abort.called), ([], 1, True))

    def test_connection_errors(self) -> None:
        # thor puts peer-supplied text in some details
        escaped = HttpError("\x1b[31m" + chr(0x202E) + "\n")
        for error, log in [
            (ReadTimeoutError("read"), "Captcha error: Read Timeout (read)."),
            (ReadTimeoutError(), "Captcha error: Read Timeout."),
            (escaped, "Captcha error: Unknown Error (\\x1b[31m\\u202e\\x0a)."),
        ]:
            with self.subTest(log=log):
                _, errors, _ = self.verify([b'{"success": true}'], error=error)
                self.assertEqual([(e[0], e[3]) for e in errors], [(b"403", log)])
                self.assertIn("problem with the captcha server", errors[0][2])


class Provider(http.server.BaseHTTPRequestHandler):
    "A stand-in captcha provider; the class attribute holds what it replies with next."

    reply: Dict[str, Any] = {}
    dropped = threading.Event()

    def do_POST(self) -> None:  # pylint: disable=invalid-name
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        body = self.reply["body"]
        if body is None:
            self.close_connection = True  # no response at all
            return
        self.send_response(self.reply["status"])
        self.send_header("Content-Length", str(len(body) if body != b"trickle" else 10_000_000))
        self.end_headers()
        try:
            if body != b"trickle":
                self.wfile.write(body)
                return
            # more than the daemon will buffer, then on until it hangs up
            self.wfile.write(b" " * (MAX_REPLY_SIZE + 1))
            for _ in range(100):
                time.sleep(0.2)
                self.wfile.write(b" ")
        except OSError:
            Provider.dropped.set()

    def log_message(self, *args: Any) -> None:  # pylint: disable=arguments-differ
        pass


# Only ever points the daemon at a local stub; nothing here contacts a real provider.
LAUNCHER = """
import sys
from configparser import ConfigParser
from redbot.daemon import RedBotServer
from redbot.webui import captcha
url, port = sys.argv[1:]
assert url.startswith("http://127.0.0.1:"), url
captcha.CAPTCHA_PROVIDERS["hcaptcha"]["verify_url"] = url.encode()
conf = ConfigParser()
conf.read_string(
    f"[redbot]\\nhost = 127.0.0.1\\nport = {port}\\nstatic_root = static\\n"
    "captcha_provider = hcaptcha\\ncaptcha_secret = placeholder\\ncaptcha_sitekey = placeholder\\n"
)
RedBotServer(conf["redbot"]).run()
"""


class TestDaemonSurvivesBadCaptchaReplies(unittest.TestCase):
    "#486: a real daemon, with the provider replaced by a local stub."

    def setUp(self) -> None:
        provider = http.server.HTTPServer(("127.0.0.1", 0), Provider)
        threading.Thread(target=provider.serve_forever, daemon=True).start()
        self.addCleanup(provider.server_close)
        self.addCleanup(provider.shutdown)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        url = f"http://127.0.0.1:{provider.server_address[1]}/siteverify"
        self.daemon = subprocess.Popen(
            [sys.executable, "-c", LAUNCHER, url, str(self.port)],
            cwd=ROOT,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(self.daemon.__exit__, None, None, None)
        self.addCleanup(self.daemon.terminate)
        for _ in range(200):
            self.assertIsNone(self.daemon.poll(), "daemon exited during startup")
            try:
                socket.create_connection(("127.0.0.1", self.port), timeout=1).close()
                return
            except OSError:
                time.sleep(0.1)
        self.fail("daemon did not start")

    def check(self, body: Optional[bytes], status: int = 200) -> Tuple[int, str]:
        Provider.reply = {"status": status, "body": body}
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/check?uri=http://127.0.0.1:1/",
            data=b"captcha_token=abc",
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, response.read().decode("utf-8")
        except urllib.error.HTTPError as err:
            return err.code, err.read().decode("utf-8")

    def test_bad_replies(self) -> None:
        cases = [
            (b"null", 200, 500),
            (b'{"error-codes": [1, "<script>alert(1)</script>", "\\u001b[31m"]}', 200, 403),
            (b'{"success": true}', 500, 500),
            (None, 200, 403),
        ]
        for body, status, expected in cases:
            with self.subTest(body=body, status=status):
                got, page = self.check(body, status)
                self.assertEqual(got, expected)
                self.assertIn("</html>", page)
                self.assertNotIn("<script>alert(1)", page)
                self.assertIsNone(self.daemon.poll(), "daemon exited")
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/", timeout=10) as response:
            self.assertEqual(response.status, 200)
        self.daemon.terminate()
        stderr = self.daemon.communicate()[1]
        self.assertNotIn("Traceback", stderr)
        self.assertIn("Captcha error: ", stderr)
        self.assertNotIn("Captcha error: .", stderr)
        self.assertIn("\\x1b[31m", stderr)
        self.assertNotIn("\x1b", stderr)

    def test_oversized_reply_is_cut_off(self) -> None:
        Provider.dropped.clear()
        start = time.time()
        self.assertEqual(self.check(b"trickle")[0], 500)
        self.assertLess(time.time() - start, 8)
        self.assertTrue(Provider.dropped.wait(10), "the provider was never hung up on")
        self.assertIsNone(self.daemon.poll(), "daemon exited")


if __name__ == "__main__":
    unittest.main()
