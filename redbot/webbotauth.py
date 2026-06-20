"""
Web Bot Auth support for REDbot.

Web Bot Auth lets an automated client prove its identity to an origin by
attaching an HTTP Message Signature (RFC 9421) to its requests, signed with an
Ed25519 key whose public half is published in a directory at a well-known
location.

This module implements the IETF drafts
(draft-meunier-web-bot-auth-architecture and
draft-meunier-http-message-signatures-directory) and is not specific to any
particular verifier.

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

import http_sf
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

# Default lifetime of a request signature, in seconds. Web Bot Auth allows up to
# 24h; we keep it short to limit the window for replay.
DEFAULT_VALIDITY = 300
# Lifetime of the directory response signature. The directory is cacheable for a
# day (see DIRECTORY_MAX_AGE), so its signature must stay valid at least that
# long, or a verifier re-checking a cached copy would see it expired.
DIRECTORY_VALIDITY = 86400
# Cache lifetime advertised for the directory, in seconds.
DIRECTORY_MAX_AGE = 86400
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

    ``key_pem`` is an Ed25519 private key in PEM (PKCS#8) form. ``directory`` is
    the HTTPS origin that hosts this bot's key directory; it becomes the
    Signature-Agent header value, and verifiers append the well-known directory
    path to it. ``validity`` is the signature lifetime in seconds.
    """

    def __init__(
        self,
        key_pem: bytes,
        directory: str,
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
        self.directory = directory.strip().strip('"')
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
        components: List[Tuple[str, str]],
        tag: str,
        validity: int,
    ) -> Tuple[str, str]:
        """
        Construct the RFC 9421 signature base over ``components`` (each an
        ordered (component-name, component-value) pair), sign it, and return the
        Signature-Input and Signature dictionary-member values for SIG_LABEL.
        ``validity`` is the signature lifetime in seconds.

        Structured-field values are serialized with ``http_sf`` so the
        @signature-params line in the base and the Signature-Input header are
        produced identically.
        """
        created = int(time.time())
        params: http_sf.types.ParamsType = {
            "created": created,
            "expires": created + validity,
            "keyid": self.keyid,
            "alg": "ed25519",
            "nonce": base64.b64encode(secrets.token_bytes(32)).decode("ascii"),
            "tag": tag,
        }
        covered: List[http_sf.types.ItemType] = [name for name, _ in components]
        inner_list: http_sf.types.InnerListType = (covered, params)

        base_lines = [f"{http_sf.ser(name)}: {value}" for name, value in components]
        base_lines.append(f'{http_sf.ser("@signature-params")}: {http_sf.ser([inner_list])}')
        signature = self._key.sign("\n".join(base_lines).encode("utf-8"))

        return http_sf.ser({SIG_LABEL: inner_list}), http_sf.ser({SIG_LABEL: signature})

    def sign_request(self, uri: str) -> List[Tuple[bytes, bytes]]:
        "Return the Web Bot Auth headers to add to a request for ``uri``."
        agent_field = http_sf.ser(self.directory)  # Signature-Agent value (an sf-string)
        sig_input, sig = self._build_signature(
            [("@authority", self.authority(uri)), ("signature-agent", agent_field)],
            REQUEST_TAG,
            self.validity,
        )
        return [
            (b"Signature-Agent", agent_field.encode("ascii")),
            (b"Signature-Input", sig_input.encode("ascii")),
            (b"Signature", sig.encode("ascii")),
        ]

    def sign_directory(self, authority: str) -> List[Tuple[bytes, bytes]]:
        "Return the signature headers for a directory response served at ``authority``."
        sig_input, sig = self._build_signature(
            [("@authority", authority)], DIRECTORY_TAG, DIRECTORY_VALIDITY
        )
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


def _ui_uri_origin(config: SectionProxy) -> str:
    "The scheme://host[:port] origin of ui_uri, or '' if it isn't a usable URL."
    parts = urlsplit(config.get("ui_uri", "").strip())
    if not parts.scheme or not parts.netloc:
        return ""
    return f"{parts.scheme}://{parts.netloc}"


def load_signer(config: SectionProxy) -> Optional[WebBotAuthSigner]:
    """
    Build a ``WebBotAuthSigner`` from REDbot configuration, or return None if
    Web Bot Auth is not configured. Raises ``WebBotAuthError`` on misconfiguration
    so problems surface at startup rather than mid-request. Successful signers are
    cached, keyed by key path, directory, validity, and the key file's mtime.

    The key directory location is ``web_bot_auth_directory``; if unset, it
    defaults to the origin of ``ui_uri`` (so enabling signing requires ``ui_uri``
    to be set correctly to this instance's public origin).
    """
    key_path = config.get("web_bot_auth_key", "").strip()
    directory = config.get("web_bot_auth_directory", "").strip()
    if not key_path:
        if directory:
            raise WebBotAuthError("web_bot_auth_directory is set but web_bot_auth_key is not.")
        return None
    if not directory:
        directory = _ui_uri_origin(config)
        if not directory:
            raise WebBotAuthError(
                "Web Bot Auth needs a key directory location: set web_bot_auth_directory, "
                "or (for the daemon) set ui_uri to this instance's public origin."
            )
    validity = config.getint("web_bot_auth_validity", fallback=DEFAULT_VALIDITY)

    try:
        mtime = os.path.getmtime(key_path)
    except OSError as why:
        raise WebBotAuthError(f"Can't read Web Bot Auth key '{key_path}': {why}") from why

    cache_key = "\0".join([key_path, directory, str(validity), str(mtime)])
    if cache_key not in _SIGNER_CACHE:
        try:
            with open(key_path, "rb") as fh:
                key_pem = fh.read()
        except OSError as why:
            raise WebBotAuthError(f"Can't read Web Bot Auth key '{key_path}': {why}") from why
        _SIGNER_CACHE[cache_key] = WebBotAuthSigner(
            key_pem, directory, validity, key_created=int(mtime)
        )
    return _SIGNER_CACHE[cache_key]
