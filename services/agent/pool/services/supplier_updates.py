"""Recording a supplier quote Pool did not have before.

Pool's standing demand outlives any one run. A member declares what they buy, the
coordinator finds nothing worth doing, and the declaration stays — which is only a
promise worth making if the answer can actually change later. The thing that changes it
is rarely the demand. It is the world: a supplier who did not quote a product last month
quotes it this month, and the same people, with the same declarations, become a group
purchase that was impossible the day before.

This module is the smallest surface that makes that demonstrable in a demo.

What it is
----------
An **operator** action, not a consumer one. A member cannot conjure a wholesale quote,
and a screen that let them would be teaching the wrong thing about what Pool is. It
lives on Operations, next to the offer ledger it writes to.

What it writes
--------------
One :class:`~pool.domain.models.Offer` row. Not a simulation mode, not a scenario flag,
not a parallel state machine that the evaluator has to be taught about — the same kind
of row the seeded catalogue holds, read by the same ``offers_for`` every price in this
system already comes from. That is the whole mechanism, and it is why the verdict after
recording a quote is not scripted anywhere: the ordinary evaluator sees an ordinary
offer and reaches whatever conclusion the arithmetic supports.

Nothing else changes. No declaration is created, amended or retired; no household, no
membership, no pool, no autonomy policy, no retail baseline, and no record of a run that
already happened. ``test_supplier_updates.py`` snapshots the entire workspace around the
call and asserts the offer table is the only thing that moved.

Why the client sends a key and never a number
---------------------------------------------
The terms below are **server-owned**. A caller selects one of two keys; it cannot supply
a price, a minimum, a case size, a product, or a supplier. This is the same rule the
public demo already applies to run triggers (``api/public_demo.TRIGGER_PROMPTS``), for
the same reason: ``/api/operator/offers`` — the general offer-mutation route — is
deliberately outside the public allowlist, because a stranger who can set a price can
poison every figure the site derives from it.

It also matters for what the demo *proves*. A control that let the presenter type prices
until Pool said yes would demonstrate nothing except that Pool does arithmetic. Two fixed
quotes, decided in advance and written down here, mean the interesting question — does
this one work? — is genuinely being asked of the evaluator.

Provenance
----------
Both quotes are recorded as :data:`~pool.domain.models.OfferSource.SYNTHETIC`, which is
what they are, and what every other offer in this synthetic Community already is.

``MANUAL_VERIFIED`` would have been the closer match for the *act* — an operator did
enter these — and it is the wrong label for the *fact*. Operations renders that source
as a green "manual verified" chip meaning a human confirmed a real quote with a real
supplier. Riverbend Wholesale does not exist, these terms were invented for a demo, and
tagging them as verified would lend a real-looking provenance to an invented price:
precisely the confusion ``OfferSource`` and ``ProductSource`` are kept apart to prevent
(AGENTS.md §8, domain/models.py). The operator's act is recorded where it belongs — in
the offer id, the quote reference, and ``verified_at``, which genuinely is the moment it
was recorded.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.models import MoqKind, Offer, OfferKind, OfferSource, iso, utcnow
from .context import PoolContext


class SupplierUpdateError(ValueError):
    """A quote key that is not on the allowlist."""


@dataclass(frozen=True)
class SupplierQuote:
    """One predetermined supplier quote, with every economic term fixed here.

    A quote is *terms*, not an outcome. Nothing in this object says whether the order it
    enables is worth doing — there is no viability flag, no expected verdict, and no
    saving. Those are the evaluator's to compute, from these numbers, at the moment
    somebody asks.
    """

    key: str
    offer_id: str
    label: str
    #: What kind of supplier arrangement this is, in a sentence an operator would use.
    summary: str
    product_id: str
    supplier_id: str
    unit_price_cents: int
    case_units: int
    moq_amount: int
    supplier_reference: str
    moq_kind: MoqKind = MoqKind.UNITS

    @property
    def min_units(self) -> int:
        if self.moq_kind == MoqKind.CASES:
            return self.moq_amount * self.case_units
        return self.moq_amount

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "offer_id": self.offer_id,
            "label": self.label,
            "summary": self.summary,
            "product_id": self.product_id,
            "unit_price_cents": self.unit_price_cents,
            "case_units": self.case_units,
            "min_units": self.min_units,
            "supplier_reference": self.supplier_reference,
            # Said on every surface that renders this, rather than left to a caption
            # somebody might drop.
            "synthetic": True,
        }


#: The product these quotes concern. Seeded with a shelf price, six independent
#: declarations, and deliberately no bulk tier (``data/seed.py``).
PRODUCT_ID = "prod_rice_jasmine"

#: The two quotes, and the entire set a caller may choose from.
#:
#: They are the two shapes a wholesaler actually quotes a staple in, and they differ the
#: way real ones differ: the split-case programme asks for a smaller commitment and
#: charges for the handling, the full-case programme asks for more and prices better.
#: Whether either is *worth* it is not decided here.
QUOTES: dict[str, SupplierQuote] = {
    "rice_split_case": SupplierQuote(
        key="rice_split_case",
        offer_id="off_rice_bulk_split",
        label="Split-case quote",
        summary=(
            "Riverbend will break cases: four bags to a case, twelve bags minimum, "
            "with the handling priced into the unit rate."
        ),
        product_id=PRODUCT_ID,
        supplier_id="sup_riverbend",
        unit_price_cents=975,
        case_units=4,
        moq_amount=12,
        supplier_reference="QUOTE-RICE-SPLIT",
    ),
    "rice_case_program": SupplierQuote(
        key="rice_case_program",
        offer_id="off_rice_bulk_case",
        label="Case-programme quote",
        summary=(
            "Riverbend's standing programme rate: eight bags to a case, sixteen bags "
            "minimum, priced for a full-case order."
        ),
        product_id=PRODUCT_ID,
        supplier_id="sup_riverbend",
        unit_price_cents=625,
        case_units=8,
        moq_amount=16,
        supplier_reference="QUOTE-RICE-CASE",
    ),
}


def get(key: str) -> SupplierQuote:
    """The quote for ``key``, or a refusal. The allowlist, in one place."""
    quote = QUOTES.get(key)
    if quote is None:
        raise SupplierUpdateError(f"unknown supplier quote: {key}")
    return quote


def record(ctx: PoolContext, key: str) -> Offer:
    """Record one predetermined supplier quote against this workspace.

    Writes a single offer row and returns it. Idempotent by id: recording the same quote
    twice refreshes it rather than accumulating tiers, so a second press cannot quietly
    double the supply Pool believes it has.
    """
    quote = get(key)
    offer = Offer(
        id=quote.offer_id,
        supplier_id=quote.supplier_id,
        product_id=quote.product_id,
        kind=OfferKind.BULK,
        unit_price_cents=quote.unit_price_cents,
        case_units=quote.case_units,
        moq_kind=quote.moq_kind,
        moq_amount=quote.moq_amount,
        # Genuinely now: this is the moment the quote entered Pool's records, and
        # freshness is load-bearing downstream (§43).
        verified_at=iso(utcnow()),
        valid_until="",
        source=OfferSource.SYNTHETIC,
        supplier_reference=quote.supplier_reference,
    )
    ctx.repo.put_offer(ctx.ws, offer)
    return offer


def recorded_keys(ctx: PoolContext) -> set[str]:
    """Which of the quotes this workspace already holds."""
    held = {o.id for o in ctx.repo.list_offers(ctx.ws)}
    return {q.key for q in QUOTES.values() if q.offer_id in held}
