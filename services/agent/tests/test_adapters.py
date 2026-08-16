"""Sourcing and Community-verification adapters.

Both exist to keep an honest boundary: a quote is only "fresh" if something actually
re-checked it, and a Community membership is only "verified" if a real check happened.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from pool.adapters.sourcing import (
    DriftingCatalogProvider,
    ManualVerifiedOfferProvider,
    SyntheticCatalogProvider,
)
from pool.adapters.verification import (
    DemoVerificationProvider,
    EmailDomainVerificationProvider,
    VerificationError,
    build_verification_provider,
)
from pool.domain.models import (
    MembershipStatus,
    OfferSource,
    VerificationMethod,
    iso,
    utcnow,
)
from tests.conftest import make_community

# --------------------------------------------------------------------------- sourcing


def test_synthetic_search_returns_only_active_bulk_offers(bulk_offer, retail_offer):
    provider = SyntheticCatalogProvider(
        catalog={"c1": {"p_protein": [bulk_offer, retail_offer]}}
    )
    results = provider.search("c1", "p_protein")
    assert [o.id for o in results] == [bulk_offer.id]


def test_search_in_an_empty_catalogue_is_not_an_error():
    assert SyntheticCatalogProvider().search("c1", "p") == []


def test_refreshing_re_stamps_the_verification_time(bulk_offer):
    bulk_offer.verified_at = iso(utcnow() - timedelta(hours=40))
    result = SyntheticCatalogProvider().refresh(bulk_offer)
    assert result.ok and not result.changed
    assert result.offer.verified_at > bulk_offer.verified_at


def test_a_disabled_offer_cannot_be_refreshed(bulk_offer):
    bulk_offer.active = False
    result = SyntheticCatalogProvider().refresh(bulk_offer)
    assert result.ok is False
    assert "disabled" in result.reason


def test_an_expired_offer_cannot_be_refreshed(bulk_offer):
    bulk_offer.valid_until = iso(utcnow() - timedelta(days=1))
    result = SyntheticCatalogProvider().refresh(bulk_offer)
    assert result.ok is False
    assert "validity" in result.reason


def test_a_moved_price_is_reported_as_changed(bulk_offer):
    provider = DriftingCatalogProvider(delta_cents=250)
    before = bulk_offer.unit_price_cents
    result = provider.refresh(bulk_offer)
    assert result.ok and result.changed and result.materially_changed
    assert result.previous_unit_price_cents == before
    assert result.offer.unit_price_cents == before + 250


def test_a_price_cannot_drift_below_a_cent(bulk_offer):
    result = DriftingCatalogProvider(delta_cents=-999_999).refresh(bulk_offer)
    assert result.offer.unit_price_cents >= 1


def test_a_manual_quote_inside_the_window_stays_valid(bulk_offer):
    bulk_offer.source = OfferSource.MANUAL_VERIFIED
    bulk_offer.verified_at = iso(utcnow() - timedelta(hours=2))
    result = ManualVerifiedOfferProvider(max_age_hours=48).refresh(bulk_offer)
    assert result.ok and not result.changed


def test_a_stale_manual_quote_needs_a_human_not_a_re_stamp(bulk_offer):
    """Only a person can re-confirm a price a person entered (§45)."""
    bulk_offer.source = OfferSource.MANUAL_VERIFIED
    bulk_offer.verified_at = iso(utcnow() - timedelta(hours=200))
    result = ManualVerifiedOfferProvider(max_age_hours=48).refresh(bulk_offer)
    assert result.ok is False
    assert "operator" in result.reason


def test_manual_search_only_returns_manually_verified_offers(bulk_offer):
    manual = type(bulk_offer).from_dict(bulk_offer.to_dict())
    manual.id = "off_manual"
    manual.source = OfferSource.MANUAL_VERIFIED
    provider = ManualVerifiedOfferProvider(
        catalog={"c1": {"p_protein": [bulk_offer, manual]}}
    )
    assert [o.id for o in provider.search("c1", "p_protein")] == ["off_manual"]


# ----------------------------------------------------------------------- verification


def test_demo_verification_admits_immediately():
    """Judge Mode must not make anyone verify against a university that does not exist."""
    community = make_community(verification_methods=[VerificationMethod.DEMO])
    provider = DemoVerificationProvider()
    provider.start(community, "m1", "")
    outcome = provider.complete(community, "m1", "")
    assert outcome.ok
    assert outcome.membership.status == MembershipStatus.VERIFIED
    assert outcome.membership.verification_metadata["synthetic"] is True


def test_demo_verification_refuses_a_community_that_did_not_offer_it():
    community = make_community(verification_methods=[VerificationMethod.EMAIL_DOMAIN])
    with pytest.raises(VerificationError):
        DemoVerificationProvider().complete(community, "m1", "")


def test_email_domain_verification_round_trip():
    community = make_community(
        verification_methods=[VerificationMethod.EMAIL_DOMAIN],
        email_domains=["example.edu"],
    )
    provider = EmailDomainVerificationProvider()
    challenge = provider.start(community, "m1", "Student@Example.edu")
    assert challenge.code
    outcome = provider.complete(community, "m1", challenge.code)
    assert outcome.ok
    assert outcome.membership.status == MembershipStatus.VERIFIED


def test_only_the_domain_is_retained_never_the_address():
    """Pool has no business holding a directory of everyone's institutional email."""
    community = make_community(
        verification_methods=[VerificationMethod.EMAIL_DOMAIN],
        email_domains=["example.edu"],
    )
    provider = EmailDomainVerificationProvider()
    challenge = provider.start(community, "m1", "student@example.edu")
    metadata = provider.complete(community, "m1", challenge.code).membership.verification_metadata
    assert metadata["domain"] == "example.edu"
    assert "student@example.edu" not in str(metadata)
    assert len(metadata["address_hash"]) == 64


def test_a_wrong_code_does_not_verify():
    community = make_community(
        verification_methods=[VerificationMethod.EMAIL_DOMAIN],
        email_domains=["example.edu"],
    )
    provider = EmailDomainVerificationProvider()
    provider.start(community, "m1", "student@example.edu")
    outcome = provider.complete(community, "m1", "000000")
    assert outcome.ok is False
    assert "did not match" in outcome.reason


def test_completing_without_starting_fails():
    community = make_community(
        verification_methods=[VerificationMethod.EMAIL_DOMAIN],
        email_domains=["example.edu"],
    )
    outcome = EmailDomainVerificationProvider().complete(community, "m1", "123456")
    assert outcome.ok is False


def test_a_disallowed_domain_is_refused():
    community = make_community(
        verification_methods=[VerificationMethod.EMAIL_DOMAIN],
        email_domains=["example.edu"],
    )
    with pytest.raises(VerificationError):
        EmailDomainVerificationProvider().start(community, "m1", "someone@gmail.com")


def test_a_malformed_address_is_refused():
    community = make_community(
        verification_methods=[VerificationMethod.EMAIL_DOMAIN],
        email_domains=["example.edu"],
    )
    with pytest.raises(VerificationError):
        EmailDomainVerificationProvider().start(community, "m1", "not-an-address")


def test_a_code_cannot_be_replayed():
    community = make_community(
        verification_methods=[VerificationMethod.EMAIL_DOMAIN],
        email_domains=["example.edu"],
    )
    provider = EmailDomainVerificationProvider()
    challenge = provider.start(community, "m1", "student@example.edu")
    assert provider.complete(community, "m1", challenge.code).ok
    assert provider.complete(community, "m1", challenge.code).ok is False


def test_institutional_sso_is_documented_not_pretended():
    """Claiming an integration that requires an agreement would be a lie (§10)."""
    with pytest.raises(VerificationError) as exc:
        build_verification_provider(VerificationMethod.INSTITUTIONAL_SSO)
    assert "not implemented" in str(exc.value)


def test_no_provider_ever_accepts_an_institutional_password():
    """The one thing Pool must never ask for (§10).

    Checked against the parsed module rather than its text, so the documentation is
    free to name the rule while the code has no way to receive such a value.
    """
    import ast
    import inspect

    from pool.adapters import verification

    tree = ast.parse(inspect.getsource(verification))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    assert not any("password" in n.lower() or "passwd" in n.lower() for n in names)


def test_the_builder_returns_the_right_provider():
    assert isinstance(
        build_verification_provider(VerificationMethod.DEMO), DemoVerificationProvider
    )
    assert isinstance(
        build_verification_provider(VerificationMethod.EMAIL_DOMAIN),
        EmailDomainVerificationProvider,
    )
