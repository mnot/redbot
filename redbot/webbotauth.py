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
import re
import secrets
import sys
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
# The longest request signature lifetime we'll configure: the 24h ceiling the drafts recommend.
MAX_VALIDITY = 86400
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


_HOST_LABEL = re.compile(r"[a-z0-9_]([a-z0-9_-]{0,61}[a-z0-9_])?")
_SCHEME_LIKE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:(?!\d+(?:[/?#]|$))")


def normalise_directory(directory: str) -> str:
    """
    The ASCII serialisation of the origin of the key directory: scheme and host (in ASCII form),
    plus the port unless it is the scheme's default. A scheme-less value is taken as https, and
    anything after the authority is dropped, because verifiers append the well-known path to the
    origin (draft-ietf-webbotauth-httpsig-protocol section 5.5).
    """
    invalid = WebBotAuthError(f"Invalid Web Bot Auth directory '{directory}'.")
    text = directory.strip().strip('"').strip()
    if "://" not in text:
        if "//" in text or _SCHEME_LIKE.match(text):  # a mistyped scheme, not a host
            raise invalid
        text = f"https://{text}"
    try:
        parts = urlsplit(text)
        host = parts.hostname
        port = parts.port
    except ValueError as why:
        raise invalid from why
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https") or not host:
        raise invalid
    if ":" in host:  # an IPv6 literal; urlsplit has stripped its brackets
        host = f"[{host}]"
    else:
        try:
            ascii_host = host.encode("idna").decode("ascii")
            # IDNA 2003 maps some characters (e.g. the sharp s) to others; refuse those.
            if ascii_host.encode("ascii").decode("idna") != host:
                raise invalid
        except UnicodeError as why:
            raise invalid from why
        if len(ascii_host) > 253 or not all(
            _HOST_LABEL.fullmatch(label) or label.startswith("xn--")
            for label in ascii_host.rstrip(".").split(".")
        ):
            raise invalid
        host = ascii_host
    default_port = 443 if scheme == "https" else 80
    origin = f"{scheme}://{host}"
    return origin if port is None or port == default_port else f"{origin}:{port}"


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
        self.directory = normalise_directory(directory)
        # Verifiers derive @authority from the directory URL they fetched.
        self.directory_authority = self.authority(self.directory)
        if validity < 1:
            raise WebBotAuthError("Web Bot Auth validity must be at least one second.")
        self.validity = validity
        self.key_created = key_created
        try:
            self._agent_field = http_sf.ser(self.directory)  # Signature-Agent value (an sf-string)
        except (ValueError, TypeError) as why:
            raise WebBotAuthError(f"Invalid Web Bot Auth directory '{directory}': {why}") from why

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
        if ":" in host:
            host = f"[{host}]"  # urlsplit strips the brackets from IPv6 literals
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
        components: List[Tuple[http_sf.types.ItemType, str]],
        tag: str,
        validity: int,
        created: Optional[int] = None,
        nonce: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Construct the RFC 9421 signature base over ``components`` (each an
        ordered (component-identifier, component-value) pair; an identifier is a
        structured-field item, so it can carry parameters such as ``req``), sign
        it, and return the Signature-Input and Signature dictionary-member values
        for SIG_LABEL. ``validity`` is the signature lifetime in seconds.

        Structured-field values are serialized with ``http_sf`` so the
        @signature-params line in the base and the Signature-Input header are
        produced identically. The parameters are in the order the drafts' test vectors use, because
        the order is part of what is signed.

        ``created`` and ``nonce`` default to the current time and a random value; tests can
        supply them to reproduce a known signature.
        """
        if created is None:
            created = int(time.time())
        if nonce is None:
            nonce = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
        params: http_sf.types.ParamsType = {
            "created": created,
            "keyid": self.keyid,
            "alg": "ed25519",
            "expires": created + validity,
            "nonce": nonce,
            "tag": tag,
        }
        covered = [identifier for identifier, _ in components]
        inner_list: http_sf.types.InnerListType = (covered, params)

        base_lines = [f"{http_sf.ser(identifier)}: {value}" for identifier, value in components]
        base_lines.append(f'{http_sf.ser("@signature-params")}: {http_sf.ser([inner_list])}')
        signature = self._key.sign("\n".join(base_lines).encode("utf-8"))

        return http_sf.ser({SIG_LABEL: inner_list}), http_sf.ser({SIG_LABEL: signature})

    def sign_request(
        self, uri: str, created: Optional[int] = None, nonce: Optional[str] = None
    ) -> List[Tuple[bytes, bytes]]:
        "Return the Web Bot Auth headers to add to a request for ``uri``."
        sig_input, sig = self._build_signature(
            [
                (("@authority", {}), self.authority(uri)),
                (("signature-agent", {}), self._agent_field),
            ],
            REQUEST_TAG,
            self.validity,
            created,
            nonce,
        )
        return [
            (b"Signature-Agent", self._agent_field.encode("ascii")),
            (b"Signature-Input", sig_input.encode("ascii")),
            (b"Signature", sig.encode("ascii")),
        ]

    def sign_directory(self) -> List[Tuple[bytes, bytes]]:
        """
        Return the Content-Digest and signature headers for the directory response, whose body is
        ``directory_json()``. draft-ietf-webbotauth-httpsig-protocol Appendix B.1 requires the
        signature to cover @authority with ``req`` (RFC 9421 section 2.4) and the content digest.
        """
        digest = http_sf.ser({"sha-256": hashlib.sha256(self.directory_json()).digest()})
        sig_input, sig = self._build_signature(
            [
                (("@authority", {"req": True}), self.directory_authority),
                (("content-digest", {}), digest),
            ],
            DIRECTORY_TAG,
            DIRECTORY_VALIDITY,
        )
        return [
            (b"Content-Digest", digest.encode("ascii")),
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


# The signer for the most recent configuration, with the key it was built from. One entry: a key
# file that is rewritten often (by a secrets agent, say) must not leave a trail of old signers.
_SIGNER_CACHE: Optional[Tuple[str, WebBotAuthSigner]] = None


def _ui_uri_origin(config: SectionProxy) -> str:
    "The scheme://host[:port] origin of ui_uri, or '' if it isn't a usable URL."
    try:
        parts = urlsplit(config.get("ui_uri", "").strip())
    except ValueError:
        return ""
    if not parts.scheme or not parts.netloc:
        return ""
    return f"{parts.scheme}://{parts.netloc}"


def load_signer(config: SectionProxy) -> Optional[WebBotAuthSigner]:
    """
    Build a ``WebBotAuthSigner`` from REDbot configuration, or return None if
    Web Bot Auth is not configured. Raises ``WebBotAuthError`` on misconfiguration
    so problems surface at startup rather than mid-request. The latest signer is cached, keyed
    by key path, directory, validity, key creation time and the key file's mtime.

    The key directory location is ``web_bot_auth_directory``; if unset, it
    defaults to the origin of ``ui_uri`` (so enabling signing requires ``ui_uri``
    to be set correctly to this instance's public origin).
    """
    pem_path = config.get("web_bot_auth_key", "").strip()
    directory = config.get("web_bot_auth_directory", "").strip()
    if not pem_path:
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
    try:
        validity = config.getint("web_bot_auth_validity", fallback=DEFAULT_VALIDITY)
    except ValueError as why:
        raise WebBotAuthError("web_bot_auth_validity must be a whole number of seconds.") from why
    if not 1 <= validity <= MAX_VALIDITY:
        raise WebBotAuthError(
            f"web_bot_auth_validity must be between 1 and {MAX_VALIDITY} seconds, not {validity}."
        )

    key_created: Optional[int] = None
    if config.get("web_bot_auth_key_created", "").strip():
        try:
            key_created = int(config.get("web_bot_auth_key_created", "").strip())
        except ValueError as why:
            raise WebBotAuthError(
                "web_bot_auth_key_created must be a Unix timestamp in whole seconds."
            ) from why
        if key_created < 0:
            raise WebBotAuthError("web_bot_auth_key_created can't be negative.")

    try:
        stat = os.stat(pem_path)
    except OSError as why:
        raise WebBotAuthError(f"Can't read Web Bot Auth key '{pem_path}': {why}") from why

    global _SIGNER_CACHE  # pylint: disable=global-statement
    cache_key = "\0".join(
        [pem_path, directory, str(validity), str(key_created), str(stat.st_mtime)]
    )
    if _SIGNER_CACHE is None or _SIGNER_CACHE[0] != cache_key:
        try:
            with open(pem_path, "rb") as fh:
                key_pem = fh.read()
                mode = os.fstat(fh.fileno()).st_mode
        except OSError as why:
            raise WebBotAuthError(f"Can't read Web Bot Auth key '{pem_path}': {why}") from why
        if os.name == "posix" and mode & 0o077:
            sys.stderr.write(
                f"WARNING: Web Bot Auth key '{pem_path}' is accessible to other users "
                f"(mode {mode & 0o777:03o}); it should be readable only by REDbot's user.\n"
            )
        _SIGNER_CACHE = (
            cache_key,
            WebBotAuthSigner(key_pem, directory, validity, key_created=key_created),
        )
    return _SIGNER_CACHE[1]
