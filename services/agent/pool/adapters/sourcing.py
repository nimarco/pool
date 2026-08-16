"""Where supplier offers come from (§41, §44).

Pool's core logic must not depend on the source of a quote. A pool that only works
against a scraped price is a pool that stops working the day the page changes, and
scraping is not the interesting claim of this project anyway — aggregated,
pre-committed demand is (§46).

So sourcing is a narrow seam with two live implementations:

``SyntheticCatalogProvider``
    The deterministic demo catalogue. Every offer it returns is flagged
    ``OfferSource.SYNTHETIC`` and nothing downstream may present it as a real quote.
``ManualVerifiedOfferProvider``
    Offers an operator entered and verified by hand. This is the realistic cold-start
    path for a controlled pilot (§87): one person phones a wholesaler, records the
    terms, and marks the quote verified with a timestamp.

``SupplierPortalProvider`` and live retailer integrations are documented as future
work and deliberately not stubbed.

Refreshing a quote is a first-class operation because §43 forbids a final buyer offer
resting on a stale price. A provider that cannot re-verify says so; it never invents a
new ``verified_at`` for a price nobody checked.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..domain.models import Offer, OfferKind, OfferSource, iso, utcnow


class SourcingError(RuntimeError):
    """An offer could not be sourced or re-verified."""


@dataclass(frozen=True)
class RefreshResult:
    """The outcome of re-verifying one quote before a final offer is issued."""

    ok: bool
    offer: Offer | None
    changed: bool = False
    previous_unit_price_cents: int = 0
    reason: str = ""

    @property
    def materially_changed(self) -> bool:
        """True when the price moved, which invalidates any final economics built on it."""
        return self.changed

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "changed": self.changed,
            "previous_unit_price_cents": self.previous_unit_price_cents,
            "unit_price_cents": self.offer.unit_price_cents if self.offer else 0,
            "verified_at": self.offer.verified_at if self.offer else "",
            "reason": self.reason,
        }


@runtime_checkable
class SourcingProvider(Protocol):
    name: str

    def search(self, community_id: str, product_id: str) -> list[Offer]:
        """Bulk offers available for a product. Read-only and free."""
        ...

    def refresh(self, offer: Offer) -> RefreshResult:
        """Re-verify one quote, returning the current terms."""
        ...


@dataclass
class SyntheticCatalogProvider:
    """Serves the deterministic demo catalogue held in the repository.

    ``refresh`` re-stamps ``verified_at`` without changing the price, because a
    synthetic catalogue *is* its own source of truth — there is nothing else to go
    and check. Price drift is exercised by ``DriftingCatalogProvider`` instead, so
    the difference between "re-verified" and "re-priced" stays honest.
    """

    name: str = "synthetic_catalog"
    #: community_id -> product_id -> offers
    catalog: dict[str, dict[str, list[Offer]]] | None = None

    def search(self, community_id: str, product_id: str) -> list[Offer]:
        if self.catalog is None:
            return []
        return [
            o
            for o in self.catalog.get(community_id, {}).get(product_id, [])
            if o.active and o.kind == OfferKind.BULK
        ]

    def refresh(self, offer: Offer) -> RefreshResult:
        if not offer.active:
            return RefreshResult(ok=False, offer=offer, reason="offer has been disabled")
        if offer.is_expired():
            return RefreshResult(ok=False, offer=offer, reason="offer validity window has passed")
        refreshed = Offer.from_dict(offer.to_dict())
        refreshed.verified_at = iso(utcnow())
        return RefreshResult(ok=True, offer=refreshed, changed=False, reason="quote re-verified")


@dataclass
class DriftingCatalogProvider:
    """A synthetic provider whose price moves on refresh.

    Exists so the "supplier quote materially changed before lock" branch (§43) can be
    tested and demonstrated deterministically rather than waited for.
    """

    name: str = "drifting_catalog"
    delta_cents: int = 0
    inner: SourcingProvider | None = None

    def search(self, community_id: str, product_id: str) -> list[Offer]:
        return self.inner.search(community_id, product_id) if self.inner else []

    def refresh(self, offer: Offer) -> RefreshResult:
        if not offer.active:
            return RefreshResult(ok=False, offer=offer, reason="offer has been disabled")
        refreshed = Offer.from_dict(offer.to_dict())
        previous = refreshed.unit_price_cents
        refreshed.unit_price_cents = max(1, previous + self.delta_cents)
        refreshed.verified_at = iso(utcnow())
        return RefreshResult(
            ok=True,
            offer=refreshed,
            changed=refreshed.unit_price_cents != previous,
            previous_unit_price_cents=previous,
            reason="supplier re-quoted at a different price",
        )


@dataclass
class ManualVerifiedOfferProvider:
    """Operator-entered offers (§45).

    ``refresh`` deliberately refuses to re-verify by itself: a human confirmed this
    price once, and only a human can confirm it again. Returning ``ok=False`` with a
    reason routes the pool to operator review rather than pretending a stale quote is
    fresh.
    """

    name: str = "manual_verified"
    catalog: dict[str, dict[str, list[Offer]]] | None = None
    max_age_hours: int = 48

    def search(self, community_id: str, product_id: str) -> list[Offer]:
        if self.catalog is None:
            return []
        return [
            o
            for o in self.catalog.get(community_id, {}).get(product_id, [])
            if o.active and o.kind == OfferKind.BULK and o.source == OfferSource.MANUAL_VERIFIED
        ]

    def refresh(self, offer: Offer) -> RefreshResult:
        age = offer.age_hours()
        if age is not None and age <= self.max_age_hours and offer.active:
            return RefreshResult(
                ok=True, offer=offer, changed=False, reason="within the operator verification window"
            )
        return RefreshResult(
            ok=False,
            offer=offer,
            reason="a manually verified quote must be re-confirmed by an operator",
        )
