"""One-time pickup credentials (§69, §70).

Physical handoff is where a group purchase actually succeeds or quietly falls apart,
so the confirmation mechanism is a real security object rather than a checkbox.

Design
------
* Each buyer allocation gets its own credential, bound server-side to one pool and
  one buyer. Nothing identifying is encoded in it — no payment details, no phone
  number, no email. It is an opaque random value (§70).
* Two forms of the same credential are issued: a long token for the QR code, and a
  short human-readable code for when scanning is inconvenient (§69).
* **Only hashes are stored.** The plaintext exists exactly once, in the response that
  issued it. A database dump therefore cannot be replayed into a free collection, and
  re-issuing invalidates the previous pair.
* Verification is constant-time and server-side. A host cannot mark a pickup complete
  by asserting it; they present evidence the server checks (§76).

The short code alphabet excludes I, L, O, U, and 0/1 so a code read aloud at a pickup
table cannot be mistyped into someone else's allocation.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"
CODE_LENGTH = 8
TOKEN_BYTES = 24


class PickupTokenError(ValueError):
    """Raised when a pickup credential cannot be issued or accepted."""


@dataclass(frozen=True)
class IssuedCredential:
    """The plaintext pair, returned exactly once at issue time."""

    token: str
    code: str
    token_hash: str
    code_hash: str


def _hash(value: str) -> str:
    return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()


def normalise_code(code: str) -> str:
    """Upper-case and strip separators so a code read aloud still matches."""
    return "".join(ch for ch in code.upper() if ch in CODE_ALPHABET)


def hash_token(token: str) -> str:
    return _hash(token)


def hash_code(code: str) -> str:
    return _hash(normalise_code(code))


def issue_credential() -> IssuedCredential:
    """Mint a fresh, unguessable one-time credential pair."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
    return IssuedCredential(
        token=token, code=code, token_hash=_hash(token), code_hash=_hash(normalise_code(code))
    )


def matches_token(presented: str, stored_hash: str) -> bool:
    """Constant-time comparison — a timing side channel is still a side channel."""
    if not presented or not stored_hash:
        return False
    return hmac.compare_digest(_hash(presented), stored_hash)


def matches_code(presented: str, stored_hash: str) -> bool:
    if not presented or not stored_hash:
        return False
    return hmac.compare_digest(_hash(normalise_code(presented)), stored_hash)
