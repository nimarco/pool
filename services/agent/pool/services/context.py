"""The service context.

Every deterministic operation needs the same handful of collaborators: the
repository, the workspace, routing, sourcing, payments, and purchase execution.
Bundling them keeps the service signatures readable and — more importantly — makes
the set of things a service can touch explicit and injectable, so tests run entirely
offline and no service can quietly reach for a paid dependency it was not given.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..adapters.payments import LocalSimulatedPaymentProvider, PaymentProvider
from ..adapters.purchase import PurchaseExecutor, SimulatedPurchaseExecutor
from ..adapters.repository import Repository
from ..adapters.routing import RoutingService
from ..adapters.sourcing import SourcingProvider, SyntheticCatalogProvider
from ..data import product_facts
from ..domain.attributes import ProductFactSource
from ..domain.models import ActivityEvent, Community, new_id, utcnow


class CoordinationError(RuntimeError):
    """A coordination operation could not be completed."""


@dataclass
class PoolContext:
    """Everything a deterministic service is allowed to touch."""

    repo: Repository
    ws: str
    routing: RoutingService
    payments: PaymentProvider = field(default_factory=LocalSimulatedPaymentProvider)
    purchaser: PurchaseExecutor = field(default_factory=SimulatedPurchaseExecutor)
    sourcing: SourcingProvider = field(default_factory=SyntheticCatalogProvider)
    #: Where a compatibility decision reads authoritative product facts from. Injected
    #: like every other collaborator, and for the same reason: the set of things a
    #: service may treat as true should be visible at the seam rather than imported
    #: somewhere in the middle of the domain. Nothing writes to it at runtime — the
    #: curated set is committed to the repository, which is what makes "the model is
    #: never the source of a product fact" a property of the code and not a promise.
    product_facts: ProductFactSource = field(
        default_factory=lambda: product_facts.REGISTRY
    )
    run_id: str = ""
    #: Overridable clock so timing behaviour is testable without sleeping.
    now: datetime = field(default_factory=utcnow)

    def community(self, community_id: str) -> Community:
        c = self.repo.get_community(self.ws, community_id)
        if c is None:
            raise CoordinationError(f"unknown community: {community_id}")
        return c

    def log(
        self,
        kind: str,
        summary: str,
        facts: dict | None = None,
        *,
        pool_id: str | None = None,
        household_id: str | None = None,
    ) -> ActivityEvent:
        """Append a structured audit event. Never contains model reasoning text."""
        event = ActivityEvent(
            id=new_id("evt"),
            kind=kind,
            summary=summary,
            facts=facts or {},
            pool_id=pool_id,
            household_id=household_id,
            run_id=self.run_id or None,
        )
        self.repo.append_activity(self.ws, event)
        return event
