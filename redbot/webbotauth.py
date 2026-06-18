"""
Web Bot Auth support for REDbot.

Web Bot Auth lets an automated client prove its identity to an origin (for
example, one behind Cloudflare) by attaching an HTTP Message Signature
(RFC 9421) to its requests, signed with an Ed25519 key whose public half is
published in a directory at a well-known location.

This module is deliberately generic: it implements the IETF drafts
(draft-meunier-web-bot-auth-architecture and
draft-meunier-http-message-signatures-directory) rather than anything
Cloudflare-specific.

It provides:

* ``WebBotAuthSigner`` - signs outgoing requests and the directory response.
* ``load_signer`` - builds (and caches) a signer from REDbot configuration.
"""

import base64
import hashlib
import json
import os
import secrets
import time
from configparser import SectionProxy
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# The tag identifying the purpose of a signature (draft-meunier-web-bot-auth).
REQUEST_TAG = "web-bot-auth"
# The tag for a signature over the directory response itself.
DIRECTORY_TAG = "http-message-signatures-directory"
# Where the key directory is served, relative to the origin root.
DIRECTORY_PATH = "/.well-known/http-message-signatures-directory"
# Media type for the key directory.
DIRECTORY_CONTENT_TYPE = "application/http-message-signatures-directory+json"

# Default lifetime of a signature, in seconds. Web Bot Auth allows up to 24h;
# we keep it short to limit the window for replay.
DEFAULT_VALIDITY = 300
# The label tying together the Signature-Input and Signature dictionary members.
SIG_LABEL = "sig1"


class WebBotAuthError(Exception):
    "Raised when Web Bot Auth is misconfigured."


def _b64url(data: bytes) -> str:
    "base64url-encode without padding (RFC 7515 / RFC 8037)."
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


class WebBotAuthSigner:
    """
    Signs requests and directory responses for Web Bot Auth.

    ``key_pem`` is an Ed25519 private key in PEM (PKCS#8) form. ``agent`` is the
    value of the Signature-Agent header: an HTTPS URL identifying where the key
    directory is hosted (verifiers append the well-known directory path to its
    origin). ``validity`` is the signature lifetime in seconds.
    """

    def __init__(
        self,
        key_pem: bytes,
        agent: str,
        validity: int = DEFAULT_VALIDITY,
        key_created: Optional[int] = None,
    ) -> None:
        try:
            key = serialization.load_pem_private_key(key_pem, password=None)
        except (ValueError, TypeError) as why:
            raise WebBotAuthError(f"Couldn't load Web Bot Auth key: {why}") from why
        if not isinstance(key, Ed25519PrivateKey):
            raise WebBotAuthError("Web Bot Auth key must be an Ed25519 private key.")
        self._key = key
        self.agent = agent.strip().strip('"')
        self.validity = validity
        self.key_created = key_created

        raw_public = key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        self.public_x = _b64url(raw_public)
        # RFC 8037 Appendix A.3 / RFC 7638: thumbprint over the canonical JWK
        # (members lexicographically ordered, no whitespace).
        thumb_input = json.dumps(
            {"crv": "Ed25519", "kty": "OKP", "x": self.public_x},
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        self.keyid = _b64url(hashlib.sha256(thumb_input).digest())

    @staticmethod
    def authority(uri: str) -> str:
        "The RFC 9421 @authority derived component for a target URI."
        parts = urlsplit(uri)
        host = (parts.hostname or "").lower()
        default = {"http": 80, "https": 443}.get(parts.scheme.lower())
        try:
            port = parts.port
        except ValueError:
            port = None
        if port is not None and port != default:
            return f"{host}:{port}"
        return host

    def _build_signature(
        self,
        authority: str,
        include_agent: bool,
        tag: str,
    ) -> Tuple[str, str]:
        """
        Construct the RFC 9421 signature base, sign it, and return the
        Signature-Input and Signature dictionary-member values for SIG_LABEL.
        """
        created = int(time.time())
        expires = created + self.validity
        nonce = base64.b64encode(secrets.token_bytes(32)).decode("ascii")

        components = ['"@authority"']
        base_lines = [f'"@authority": {authority}']
        if include_agent:
            components.append('"signature-agent"')
            base_lines.append(f'"signature-agent": "{self.agent}"')

        params = (
            f'({" ".join(components)});created={created};expires={expires}'
            f';keyid="{self.keyid}";alg="ed25519";nonce="{nonce}";tag="{tag}"'
        )
        base_lines.append(f'"@signature-params": {params}')
        base = "\n".join(base_lines).encode("utf-8")

        signature = self._key.sign(base)
        sig_input_value = f"{SIG_LABEL}={params}"
        sig_value = f"{SIG_LABEL}=:{base64.b64encode(signature).decode('ascii')}:"
        return sig_input_value, sig_value

    def sign_request(self, uri: str) -> List[Tuple[bytes, bytes]]:
        "Return the Web Bot Auth headers to add to a request for ``uri``."
        sig_input, sig = self._build_signature(
            self.authority(uri), include_agent=True, tag=REQUEST_TAG
        )
        return [
            (b"Signature-Agent", f'"{self.agent}"'.encode("ascii")),
            (b"Signature-Input", sig_input.encode("ascii")),
            (b"Signature", sig.encode("ascii")),
        ]

    def sign_directory(self, authority: str) -> List[Tuple[bytes, bytes]]:
        "Return the signature headers for a directory response served at ``authority``."
        sig_input, sig = self._build_signature(authority, include_agent=False, tag=DIRECTORY_TAG)
        return [
            (b"Signature-Input", sig_input.encode("ascii")),
            (b"Signature", sig.encode("ascii")),
        ]

    def directory_json(self) -> bytes:
        "The key directory body: a JWKS containing the public key."
        key: Dict[str, object] = {
            "kty": "OKP",
            "crv": "Ed25519",
            "x": self.public_x,
            "kid": self.keyid,
            "use": "sig",
        }
        if self.key_created is not None:
            key["nbf"] = self.key_created
        return json.dumps({"keys": [key]}, separators=(",", ":")).encode("utf-8")


_SIGNER_CACHE: Dict[str, WebBotAuthSigner] = {}


def load_signer(config: SectionProxy) -> Optional[WebBotAuthSigner]:
    """
    Build a ``WebBotAuthSigner`` from REDbot configuration, or return None if
    Web Bot Auth is not configured. Raises ``WebBotAuthError`` on misconfiguration
    so problems surface at startup rather than mid-request. Successful signers are
    cached, keyed by key path, agent, validity, and the key file's mtime.
    """
    key_path = config.get("web_bot_auth_key", "").strip()
    agent = config.get("web_bot_auth_agent", "").strip()
    if not key_path and not agent:
        return None
    if not key_path:
        raise WebBotAuthError("web_bot_auth_agent is set but web_bot_auth_key is not.")
    if not agent:
        raise WebBotAuthError("web_bot_auth_key is set but web_bot_auth_agent is not.")
    validity = config.getint("web_bot_auth_validity", fallback=DEFAULT_VALIDITY)

    try:
        mtime = os.path.getmtime(key_path)
    except OSError as why:
        raise WebBotAuthError(f"Can't read Web Bot Auth key '{key_path}': {why}") from why

    cache_key = "\0".join([key_path, agent, str(validity), str(mtime)])
    if cache_key not in _SIGNER_CACHE:
        try:
            with open(key_path, "rb") as fh:
                key_pem = fh.read()
        except OSError as why:
            raise WebBotAuthError(f"Can't read Web Bot Auth key '{key_path}': {why}") from why
        _SIGNER_CACHE[cache_key] = WebBotAuthSigner(
            key_pem, agent, validity, key_created=int(mtime)
        )
    return _SIGNER_CACHE[cache_key]
