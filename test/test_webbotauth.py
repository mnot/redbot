#!/usr/bin/env python3

import base64
import json
import os
import re
import tempfile
import unittest
from configparser import ConfigParser

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization

from redbot.webbotauth import (
    DEFAULT_VALIDITY,
    DIRECTORY_TAG,
    DIRECTORY_VALIDITY,
    REQUEST_TAG,
    WebBotAuthError,
    WebBotAuthSigner,
    load_signer,
)

# Ed25519 test key from RFC 9421 Appendix B.1.4. Its JWK thumbprint is a known
# value used throughout the Web Bot Auth drafts.
RFC9421_ED25519_KEY = b"""\
-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIJ+DYvh6SEqVTm50DFtMDoQikTmiCqirVv9mWG9qfSnF
-----END PRIVATE KEY-----
"""
EXPECTED_KEYID = "poqkLGiymh_W0uP6PZFw-dvez3QJT5SolqXBCW38r0U"
EXPECTED_X = "JrQLj5P_89iXES9-vFgrIy29clF9CC_oPPsw3c5D0bs"

AGENT = "https://signature-agent.test"


def _headers_dict(headers):
    return {name.lower(): value for name, value in headers}


def _verify(public_key, base_lines, sig_header_value):
    "Verify a Signature header value (label sig1) over the given base lines."
    base = "\n".join(base_lines).encode("utf-8")
    assert sig_header_value.startswith("sig1=:") and sig_header_value.endswith(":")
    sig = base64.b64decode(sig_header_value[len("sig1=:") : -1])
    public_key.verify(sig, base)  # raises InvalidSignature on failure


class TestWebBotAuthSigner(unittest.TestCase):
    def setUp(self):
        self.signer = WebBotAuthSigner(RFC9421_ED25519_KEY, AGENT)
        priv = serialization.load_pem_private_key(RFC9421_ED25519_KEY, password=None)
        self.public_key = priv.public_key()

    def test_thumbprint_known_answer(self):
        self.assertEqual(self.signer.keyid, EXPECTED_KEYID)
        self.assertEqual(self.signer.public_x, EXPECTED_X)

    def test_rejects_non_ed25519(self):
        with self.assertRaises(WebBotAuthError):
            WebBotAuthSigner(b"not a key", AGENT)

    def test_authority(self):
        self.assertEqual(WebBotAuthSigner.authority("https://Example.COM/foo"), "example.com")
        self.assertEqual(WebBotAuthSigner.authority("https://example.com:443/"), "example.com")
        self.assertEqual(WebBotAuthSigner.authority("http://example.com:80/"), "example.com")
        self.assertEqual(
            WebBotAuthSigner.authority("https://example.com:8443/"), "example.com:8443"
        )

    def test_sign_request_headers_present(self):
        headers = _headers_dict(self.signer.sign_request("https://example.com/path"))
        self.assertEqual(headers[b"signature-agent"], f'"{AGENT}"'.encode("ascii"))
        sig_input = headers[b"signature-input"].decode("ascii")
        self.assertTrue(sig_input.startswith('sig1=("@authority" "signature-agent")'))
        self.assertIn(f';tag="{REQUEST_TAG}"', sig_input)
        self.assertIn(f';keyid="{EXPECTED_KEYID}"', sig_input)
        self.assertIn(";created=", sig_input)
        self.assertIn(";expires=", sig_input)

    def test_sign_request_signature_verifies(self):
        headers = _headers_dict(self.signer.sign_request("https://example.com/path"))
        sig_input = headers[b"signature-input"].decode("ascii")
        params = sig_input[len("sig1=") :]
        base_lines = [
            '"@authority": example.com',
            f'"signature-agent": "{AGENT}"',
            f'"@signature-params": {params}',
        ]
        _verify(self.public_key, base_lines, headers[b"signature"].decode("ascii"))

    def test_tampered_signature_fails(self):
        headers = _headers_dict(self.signer.sign_request("https://example.com/path"))
        sig_input = headers[b"signature-input"].decode("ascii")
        params = sig_input[len("sig1=") :]
        base_lines = [
            '"@authority": evil.example',  # wrong authority
            f'"signature-agent": "{AGENT}"',
            f'"@signature-params": {params}',
        ]
        with self.assertRaises(InvalidSignature):
            _verify(self.public_key, base_lines, headers[b"signature"].decode("ascii"))

    def test_sign_directory_verifies(self):
        headers = _headers_dict(self.signer.sign_directory("redbot.example"))
        self.assertNotIn(b"signature-agent", headers)
        sig_input = headers[b"signature-input"].decode("ascii")
        self.assertTrue(sig_input.startswith('sig1=("@authority")'))
        self.assertIn(f';tag="{DIRECTORY_TAG}"', sig_input)
        params = sig_input[len("sig1=") :]
        base_lines = [
            '"@authority": redbot.example',
            f'"@signature-params": {params}',
        ]
        _verify(self.public_key, base_lines, headers[b"signature"].decode("ascii"))

    def test_directory_json(self):
        directory = json.loads(self.signer.directory_json())
        self.assertEqual(len(directory["keys"]), 1)
        key = directory["keys"][0]
        self.assertEqual(key["kty"], "OKP")
        self.assertEqual(key["crv"], "Ed25519")
        self.assertEqual(key["x"], EXPECTED_X)
        self.assertEqual(key["kid"], EXPECTED_KEYID)
        self.assertEqual(key["use"], "sig")

    def test_signature_validity_windows(self):
        def span(headers):
            sig_input = _headers_dict(headers)[b"signature-input"].decode("ascii")
            created = int(re.search(r";created=(\d+)", sig_input).group(1))
            expires = int(re.search(r";expires=(\d+)", sig_input).group(1))
            return expires - created

        # Request signatures are short-lived; the directory signature must outlast
        # the directory's 24h cache lifetime.
        self.assertEqual(span(self.signer.sign_request("https://example.com/")), DEFAULT_VALIDITY)
        self.assertEqual(span(self.signer.sign_directory("example.com")), DIRECTORY_VALIDITY)

    def test_unique_nonce_per_signature(self):
        a = _headers_dict(self.signer.sign_request("https://example.com/"))
        b = _headers_dict(self.signer.sign_request("https://example.com/"))
        self.assertNotEqual(a[b"signature-input"], b[b"signature-input"])


class TestLoadSigner(unittest.TestCase):
    def _config(self, **values):
        parser = ConfigParser()
        parser.read_dict({"redbot": {k: v for k, v in values.items()}})
        return parser["redbot"]

    def test_disabled_returns_none(self):
        self.assertIsNone(load_signer(self._config()))

    def test_key_without_directory_or_ui_uri_raises(self):
        with self.assertRaises(WebBotAuthError):
            load_signer(self._config(web_bot_auth_key="/tmp/nope.pem"))

    def test_directory_without_key_raises(self):
        with self.assertRaises(WebBotAuthError):
            load_signer(self._config(web_bot_auth_directory=AGENT))

    def test_missing_key_file_raises(self):
        with self.assertRaises(WebBotAuthError):
            load_signer(
                self._config(
                    web_bot_auth_key="/nonexistent/web-bot-auth.pem",
                    web_bot_auth_directory=AGENT,
                )
            )

    def test_directory_defaults_to_ui_uri_origin(self):
        fd, path = tempfile.mkstemp(suffix=".pem")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(RFC9421_ED25519_KEY)
            # ui_uri can carry a path; only its origin is used.
            config = self._config(web_bot_auth_key=path, ui_uri="https://red.example/app/")
            signer = load_signer(config)
            self.assertIsNotNone(signer)
            self.assertEqual(signer.directory, "https://red.example")
        finally:
            os.unlink(path)

    def test_explicit_directory_overrides_ui_uri(self):
        fd, path = tempfile.mkstemp(suffix=".pem")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(RFC9421_ED25519_KEY)
            config = self._config(
                web_bot_auth_key=path,
                web_bot_auth_directory="https://bot.example",
                ui_uri="https://red.example/",
            )
            self.assertEqual(load_signer(config).directory, "https://bot.example")
        finally:
            os.unlink(path)

    def test_loads_and_caches(self):
        fd, path = tempfile.mkstemp(suffix=".pem")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(RFC9421_ED25519_KEY)
            config = self._config(web_bot_auth_key=path, web_bot_auth_directory=AGENT)
            signer = load_signer(config)
            self.assertIsNotNone(signer)
            self.assertEqual(signer.keyid, EXPECTED_KEYID)
            self.assertIs(load_signer(config), signer)  # cached
        finally:
            os.unlink(path)


class _MockConn:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _MockExchange:
    "Minimal stand-in for thor's HttpClientExchange."

    def __init__(self):
        self.callbacks = {}
        self.res_version = b"1.1"
        self.conn = _MockConn()
        self.requests = []
        self.input_transfer_length = 0
        self.input_header_length = 0

    def on(self, event, cb):
        self.callbacks[event] = cb

    def once(self, event, cb):
        self.callbacks[event] = cb

    def remove_listeners(self, *events):
        for event in events:
            self.callbacks.pop(event, None)

    def request_start(self, method, uri, hdrs):
        self.requests.append((method, uri, hdrs))

    def request_body(self, chunk):
        pass

    def request_done(self, trailers):
        pass

    def fire(self, event, *args):
        self.callbacks[event](*args)


class _MockClient:
    def __init__(self, exchanges):
        self._exchanges = list(exchanges)
        self.check_ip = None

    def exchange(self):
        return self._exchanges.pop(0)


class TestChallengeRetry(unittest.TestCase):
    def setUp(self):
        from configparser import ConfigParser

        fd, self.key_path = tempfile.mkstemp(suffix=".pem")
        with os.fdopen(fd, "wb") as fh:
            fh.write(RFC9421_ED25519_KEY)
        parser = ConfigParser()
        parser.read_dict(
            {
                "redbot": {
                    "enable_local_access": "True",
                    "web_bot_auth_key": self.key_path,
                    "web_bot_auth_directory": AGENT,
                }
            }
        )
        self.config = parser["redbot"]

    def tearDown(self):
        os.unlink(self.key_path)

    def _fetcher(self, exchanges):
        from redbot.resource.fetch import RedFetcher

        fetcher = RedFetcher(self.config)
        fetcher.client = _MockClient(exchanges)
        fetcher.set_request("http://example.com/")
        return fetcher

    @staticmethod
    def _sig_headers(req_hdrs):
        names = {name.lower() for name, _ in req_hdrs}
        return names

    def test_retries_signed_on_challenge(self):
        ex1, ex2 = _MockExchange(), _MockExchange()
        fetcher = self._fetcher([ex1, ex2])
        fetcher.check()

        # First request is unsigned.
        self.assertEqual(len(ex1.requests), 1)
        self.assertNotIn(b"signature-input", self._sig_headers(ex1.requests[0][2]))

        # Origin challenges.
        ex1.fire(
            "response_start",
            b"403",
            b"Forbidden",
            [(b"Accept-Signature", b'sig1=("@authority" "signature-agent");tag="web-bot-auth"')],
        )

        # The challenged exchange is aborted and a signed retry is sent.
        self.assertTrue(ex1.conn.closed)
        self.assertTrue(fetcher._wba_retried)
        self.assertEqual(len(ex2.requests), 1)
        retry_headers = self._sig_headers(ex2.requests[0][2])
        self.assertIn(b"signature-input", retry_headers)
        self.assertIn(b"signature", retry_headers)
        self.assertIn(b"signature-agent", retry_headers)

        # The retry's response is what gets linted.
        ex2.fire("response_start", b"200", b"OK", [(b"Content-Type", b"text/plain")])
        ex2.fire("response_done", [])
        self.assertEqual(fetcher.response.status_code, 200)

    def test_no_retry_without_accept_signature(self):
        ex1 = _MockExchange()
        fetcher = self._fetcher([ex1])
        fetcher.check()
        ex1.fire("response_start", b"403", b"Forbidden", [(b"Content-Type", b"text/plain")])
        ex1.fire("response_done", [])
        self.assertFalse(fetcher._wba_retried)
        self.assertEqual(fetcher.response.status_code, 403)

    def test_no_retry_on_success_with_accept_signature(self):
        # A 200 that merely advertises Accept-Signature must not trigger a refetch.
        ex1 = _MockExchange()
        fetcher = self._fetcher([ex1])
        fetcher.check()
        ex1.fire(
            "response_start",
            b"200",
            b"OK",
            [(b"Content-Type", b"text/plain"), (b"Accept-Signature", b'sig1=("@authority")')],
        )
        ex1.fire("response_done", [])
        self.assertFalse(fetcher._wba_retried)
        self.assertEqual(fetcher.response.status_code, 200)

    def test_unsigned_when_key_breaks_midrun(self):
        # If the key becomes unreadable/invalid after startup, a challenge must
        # not crash the fetch -- it proceeds unsigned.
        ex1 = _MockExchange()
        fetcher = self._fetcher([ex1])
        fetcher.check()
        with open(self.key_path, "wb") as fh:
            fh.write(b"not a valid key anymore")
        ex1.fire("response_start", b"403", b"Forbidden", [(b"Accept-Signature", b'sig1=("@authority")')])
        ex1.fire("response_done", [])
        self.assertFalse(fetcher._wba_retried)
        self.assertEqual(fetcher.response.status_code, 403)

    def test_no_double_retry(self):
        # If the signed retry is also challenged, we do not loop.
        ex1, ex2 = _MockExchange(), _MockExchange()
        fetcher = self._fetcher([ex1, ex2])
        fetcher.check()
        challenge = [(b"Accept-Signature", b'sig1=("@authority")')]
        ex1.fire("response_start", b"403", b"Forbidden", challenge)
        ex2.fire("response_start", b"403", b"Forbidden", challenge)
        ex2.fire("response_done", [])
        self.assertEqual(fetcher.response.status_code, 403)


class TestNoSignerNoRetry(unittest.TestCase):
    def test_unconfigured_does_not_retry(self):
        from configparser import ConfigParser

        from redbot.resource.fetch import RedFetcher

        parser = ConfigParser()
        parser.read_dict({"redbot": {"enable_local_access": "True"}})
        fetcher = RedFetcher(parser["redbot"])
        ex1 = _MockExchange()
        fetcher.client = _MockClient([ex1])
        fetcher.set_request("http://example.com/")
        fetcher.check()
        ex1.fire("response_start", b"403", b"Forbidden", [(b"Accept-Signature", b'sig1=("@authority")')])
        ex1.fire("response_done", [])
        self.assertFalse(fetcher._wba_retried)
        self.assertEqual(fetcher.response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
