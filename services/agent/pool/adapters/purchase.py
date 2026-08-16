"""Who actually pays the supplier (§63).

The host does **not** front the purchase. That is the whole point of the model: a
student who agrees to collect thirty tubs of protein powder is being paid for
fulfilment labour, not being asked to underwrite four hundred dollars of inventory on
a debit card and hope everyone shows up.

So purchase execution is its own seam:

``SimulatedPurchaseExecutor``
    What this build uses. Produces a clearly-labelled synthetic purchase record. No
    money moves, no supplier is contacted, and every record it writes carries
    ``simulated=True`` so nothing downstream can mistake it for a real order.
``FutureOperatorPurchaseExecutor`` / ``FutureSupplierDirectPurchaseExecutor``
    Documented, not implemented. Both need a merchant-of-record decision that is a
    legal question, not a coding one — see ``docs/PILOT_READINESS.md`` (§64).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from ..domain.models import Offer, iso, utcnow


class PurchaseError(RuntimeError):
    """A purchase could not be executed."""


@dataclass(frozen=True)
class PurchaseOrder:
    """Everything needed to place one bulk order, and nothing else."""

    pool_id: str
    supplier_id: str
    offer: Offer
    units: int
    cases: int
    total_cents: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "pool_id": self.pool_id,
            "supplier_id": self.supplier_id,
            "offer_id": self.offer.id,
            "units": self.units,
            "cases": self.cases,
            "total_cents": self.total_cents,
        }


@dataclass(frozen=True)
class PurchaseResult:
    ok: bool
    supplier_reference: str = ""
    receipt_reference: str = ""
    lot_reference: str = ""
    executed_at: str = ""
    simulated: bool = True
    executor: str = "simulated"
    failure_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "supplier_reference": self.supplier_reference,
            "receipt_reference": self.receipt_reference,
            "lot_reference": self.lot_reference,
            "executed_at": self.executed_at,
            "simulated": self.simulated,
            "executor": self.executor,
            "failure_reason": self.failure_reason,
        }


@runtime_checkable
class PurchaseExecutor(Protocol):
    name: str
    simulated: bool

    def execute(self, order: PurchaseOrder) -> PurchaseResult: ...


#: A pool id containing this marker makes the simulated purchase fail, so the
#: bounded operator-review branch (§19) can be exercised deterministically.
PURCHASE_FAILURE_MARKER = "purchasefails"


class SimulatedPurchaseExecutor:
    """Deterministic, clearly-labelled simulated purchase.

    References are derived from the order rather than random, so replaying the same
    order produces the same reference and a retry cannot look like a second purchase.
    """

    name = "simulated"
    simulated = True

    def execute(self, order: PurchaseOrder) -> PurchaseResult:
        if order.units <= 0 or order.cases <= 0:
            raise PurchaseError("a purchase must be for a positive quantity")
        if PURCHASE_FAILURE_MARKER in order.pool_id:
            return PurchaseResult(
                ok=False,
                executor=self.name,
                failure_reason="simulated supplier rejection — routed to operator review",
            )
        digest = hashlib.sha256(
            f"{order.pool_id}:{order.offer.id}:{order.units}:{order.total_cents}".encode()
        ).hexdigest()
        return PurchaseResult(
            ok=True,
            supplier_reference=f"SIMULATED-ORDER-{digest[:12].upper()}",
            receipt_reference=f"SIMULATED-RECEIPT-{digest[12:22].upper()}",
            lot_reference=f"SIMULATED-LOT-{digest[22:30].upper()}",
            executed_at=iso(utcnow()),
            simulated=True,
            executor=self.name,
        )


def build_purchase_executor(kind: str) -> PurchaseExecutor:
    if kind in {"simulated", ""}:
        return SimulatedPurchaseExecutor()
    # Operator-placed and supplier-direct execution are deliberately absent rather
    # than stubbed: a stub that looks placeable is exactly the kind of thing that
    # gets called by accident.
    raise ValueError(
        f"unknown purchase executor: {kind!r} — only 'simulated' is implemented in this build"
    )
