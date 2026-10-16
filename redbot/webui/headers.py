"""
Security headers for REDbot's HTML responses.
"""

from redbot.type import RawHeaderListType


def security_headers(nonce: str) -> RawHeaderListType:
    "Headers that every HTML response carrying the given script nonce should send."
    policy = (
        f"script-src 'strict-dynamic' 'nonce-{nonce}'; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    )
    return [
        (b"Content-Security-Policy", policy.encode("ascii")),
        (b"X-Content-Type-Options", b"nosniff"),
    ]
