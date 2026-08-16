"""Community membership verification (§10).

Account authentication and Community membership are different questions. Someone can
have a Pool account without being a verified member of any Community, and a verified
member of one Community is not thereby a member of another. This module handles only
the second question.

Non-negotiable
--------------
**Pool never asks anyone for their institution's password.** There is no provider
here that collects one, no scraping of an institutional login page, and no claim of
an official integration that does not exist. Proving control of an address on an
allowed domain is a claim about an email account; it is not, and is never presented
as, an endorsement by the institution.

Providers
---------
``DemoVerificationProvider``
    Admits anyone to a synthetic Community immediately. Judge Mode uses this (§91),
    and it can only ever apply to a Community whose configuration lists ``DEMO``.
``EmailDomainVerificationProvider``
    Issues a short-lived challenge to an address on an allowed domain and verifies the
    returned code. Only the *domain* is retained as evidence — never the address
    (AGENTS.md §4).
``FutureInstitutionalSSOProvider``
    Documented, not implemented. A real OIDC/SAML integration requires the
    institution's agreement, which is not a coding task.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from ..domain.models import (
    Community,
    CommunityMembership,
    MembershipStatus,
    VerificationMethod,
    iso,
    utcnow,
)


class VerificationError(RuntimeError):
    """Verification could not be attempted or completed."""


@dataclass(frozen=True)
class VerificationChallenge:
    """A pending proof request. The code is returned once and stored only as a hash."""

    community_id: str
    household_id: str
    method: VerificationMethod
    code: str = ""
    detail: str = ""


@dataclass(frozen=True)
class VerificationOutcome:
    ok: bool
    membership: CommunityMembership | None = None
    reason: str = ""


@runtime_checkable
class CommunityVerificationProvider(Protocol):
    method: VerificationMethod

    def start(self, community: Community, household_id: str, claim: str) -> VerificationChallenge:
        """Begin verification. ``claim`` is method-specific (an email address, etc.)."""
        ...

    def complete(
        self, community: Community, household_id: str, response: str
    ) -> VerificationOutcome: ...


def _verified(
    community_id: str, household_id: str, method: VerificationMethod, metadata: dict[str, Any]
) -> CommunityMembership:
    return CommunityMembership(
        community_id=community_id,
        household_id=household_id,
        status=MembershipStatus.VERIFIED,
        verification_method=method,
        verified_at=iso(utcnow()),
        verification_metadata=metadata,
    )


class DemoVerificationProvider:
    """Immediate membership of a synthetic Community. Never applies to a real one."""

    method = VerificationMethod.DEMO

    def start(self, community: Community, household_id: str, claim: str) -> VerificationChallenge:
        self._check(community)
        return VerificationChallenge(
            community_id=community.id,
            household_id=household_id,
            method=self.method,
            detail="demo Community — no verification required",
        )

    def complete(
        self, community: Community, household_id: str, response: str
    ) -> VerificationOutcome:
        self._check(community)
        return VerificationOutcome(
            ok=True,
            membership=_verified(
                community.id, household_id, self.method, {"demo": True, "synthetic": True}
            ),
        )

    @staticmethod
    def _check(community: Community) -> None:
        if VerificationMethod.DEMO not in community.verification_methods:
            raise VerificationError(
                f"{community.name} does not accept demo verification — it is not a demo Community"
            )


@dataclass
class EmailDomainVerificationProvider:
    """Proof of control of an address on a Community-approved domain.

    What is stored is the domain and a hash of the address, never the address itself:
    enough to show the check happened and to prevent one address verifying two
    accounts, without Pool holding a directory of everyone's institutional email.
    """

    method: VerificationMethod = VerificationMethod.EMAIL_DOMAIN
    #: "<community>#<household>" -> {"code_hash", "domain", "address_hash"}
    _pending: dict[str, dict[str, str]] = field(default_factory=dict)

    def start(self, community: Community, household_id: str, claim: str) -> VerificationChallenge:
        if VerificationMethod.EMAIL_DOMAIN not in community.verification_methods:
            raise VerificationError(f"{community.name} does not accept email-domain verification")
        address = (claim or "").strip().lower()
        if "@" not in address:
            raise VerificationError("a valid email address is required")
        domain = address.rpartition("@")[2]
        allowed = {d.lower().lstrip("@") for d in community.email_domains}
        if domain not in allowed:
            raise VerificationError(
                f"{domain} is not an approved domain for {community.name}"
            )

        code = f"{secrets.randbelow(1_000_000):06d}"
        self._pending[f"{community.id}#{household_id}"] = {
            "code_hash": hashlib.sha256(code.encode()).hexdigest(),
            "domain": domain,
            "address_hash": hashlib.sha256(address.encode()).hexdigest(),
        }
        # In a pilot the code is emailed. It is returned here so the deterministic
        # local flow can complete without a mail provider; the API never echoes it
        # back to a browser.
        return VerificationChallenge(
            community_id=community.id,
            household_id=household_id,
            method=self.method,
            code=code,
            detail=f"verification code issued for an address on {domain}",
        )

    def complete(
        self, community: Community, household_id: str, response: str
    ) -> VerificationOutcome:
        key = f"{community.id}#{household_id}"
        pending = self._pending.get(key)
        if pending is None:
            return VerificationOutcome(ok=False, reason="no verification is in progress")
        presented = hashlib.sha256((response or "").strip().encode()).hexdigest()
        if not hmac.compare_digest(presented, pending["code_hash"]):
            return VerificationOutcome(ok=False, reason="the verification code did not match")
        del self._pending[key]
        return VerificationOutcome(
            ok=True,
            membership=_verified(
                community.id,
                household_id,
                self.method,
                {"domain": pending["domain"], "address_hash": pending["address_hash"]},
            ),
        )


def build_verification_provider(
    method: VerificationMethod,
) -> CommunityVerificationProvider:
    if method == VerificationMethod.DEMO:
        return DemoVerificationProvider()
    if method == VerificationMethod.EMAIL_DOMAIN:
        return EmailDomainVerificationProvider()
    raise VerificationError(
        f"{method.value} verification is not implemented in this build — institutional "
        "SSO requires an agreement with the institution, not just code"
    )
