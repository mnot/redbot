"""
The CSP script nonce must come from a cryptographically secure source
(mnot/redbot#446) and be a valid CSP nonce token.
"""

import base64
import re
import unittest
from unittest.mock import MagicMock, patch

from redbot.webui import RedWebUi

# CSP3 base64-value: base64 or base64url characters with optional padding.
BASE64_VALUE = re.compile(r"^[A-Za-z0-9+/\-_]+={0,2}$")


def make_ui() -> RedWebUi:
    config = MagicMock()
    config.get.return_value = "utf-8"
    return RedWebUi(config, "GET", b"", b"", [], b"", MagicMock(), "127.0.0.1")


class TestNonce(unittest.TestCase):
    def test_format(self) -> None:
        nonce = make_ui().nonce
        self.assertRegex(nonce, BASE64_VALUE)
        self.assertEqual(len(base64.b64decode(nonce, validate=True)), 16)

    def test_unique(self) -> None:
        nonces = {make_ui().nonce for _ in range(100)}
        self.assertEqual(len(nonces), 100)

    def test_uses_secrets(self) -> None:
        raw = bytes(range(16))
        with patch("redbot.webui.secrets.token_bytes", return_value=raw) as token_bytes:
            nonce = make_ui().nonce
        token_bytes.assert_called_once_with(16)
        self.assertEqual(base64.b64decode(nonce), raw)


if __name__ == "__main__":
    unittest.main()
