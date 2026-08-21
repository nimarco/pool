"""State persistence.

DynamoDB is the authoritative store for everything transactional — pool membership,
commitments, money, quantities, deadlines, and explicit policies. Agent memory is
never authoritative for any of it (AGENTS.md §6). Stripe remains authoritative for
provider payment facts; what we store is our mapping of them (§84).

Two implementations behind one protocol:

* ``InMemoryRepository`` — used by every test and by local runs. Free.
* ``DynamoDBRepository`` — on-demand billing, single table, TTL on demo workspaces.

Table design (single table, on-demand)::

    pk = "<workspace>#<TYPE>"     sk = "<entity id>"

Listing a type is one Query on ``pk``. Entities that belong to a parent use a
composite sort key (``"<pool_id>#<household_id>"``) so a pool's members, host
candidates, allocations, and tokens are each a ``begins_with`` query rather than a
scan. Workspaces give each demo visitor an isolated dataset that a TTL sweeps away,
which keeps two judges from corrupting each other's demo (§92).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from ..domain.models import (
    ActivityEvent,
    AgentRun,
    Announcement,
    CohortStrategy,
    Community,
    CommunityMembership,
    CoordinationEvent,
    DecisionRequest,
    FulfillmentRun,
    HostAssignment,
    HostCandidate,
    HostProfile,
    Household,
    IssueCase,
    Membership,
    Message,
    MessageThread,
    NeedDeclaration,
    Offer,
    PaymentRecord,
    PickupAllocation,
    PickupSite,
    PickupToken,
    Pool,
    Product,
    PurchaseRecord,
    RunEvaluation,
    StrategyEvaluation,
    Supplier,
)

DEFAULT_WORKSPACE = "demo"
DEMO_TTL_SECONDS = 60 * 60 * 24  # ephemeral demo workspaces expire after a day


@dataclass
class Store:
    """The whole world for one workspace."""

    communities: dict[str, Community] = field(default_factory=dict)
    community_memberships: dict[str, CommunityMembership] = field(default_factory=dict)
    households: dict[str, Household] = field(default_factory=dict)
    products: dict[str, Product] = field(default_factory=dict)
    needs: dict[str, NeedDeclaration] = field(default_factory=dict)
    suppliers: dict[str, Supplier] = field(default_factory=dict)
    offers: dict[str, Offer] = field(default_factory=dict)
    sites: dict[str, PickupSite] = field(default_factory=dict)
    pools: dict[str, Pool] = field(default_factory=dict)
    memberships: dict[str, Membership] = field(default_factory=dict)
    host_profiles: dict[str, HostProfile] = field(default_factory=dict)
    host_candidates: dict[str, HostCandidate] = field(default_factory=dict)
    host_assignments: dict[str, HostAssignment] = field(default_factory=dict)
    payments: dict[str, PaymentRecord] = field(default_factory=dict)
    purchases: dict[str, PurchaseRecord] = field(default_factory=dict)
    fulfillment_runs: dict[str, FulfillmentRun] = field(default_factory=dict)
    allocations: dict[str, PickupAllocation] = field(default_factory=dict)
    pickup_tokens: dict[str, PickupToken] = field(default_factory=dict)
    announcements: dict[str, Announcement] = field(default_factory=dict)
    threads: dict[str, MessageThread] = field(default_factory=dict)
    messages: dict[str, Message] = field(default_factory=dict)
    issues: dict[str, IssueCase] = field(default_factory=dict)
    coordination_events: dict[str, CoordinationEvent] = field(default_factory=dict)
    cohort_strategies: dict[str, CohortStrategy] = field(default_factory=dict)
    strategy_evaluations: dict[str, StrategyEvaluation] = field(default_factory=dict)
    decisions: dict[str, DecisionRequest] = field(default_factory=dict)
    activity: list[ActivityEvent] = field(default_factory=list)
    runs: dict[str, AgentRun] = field(default_factory=dict)
    run_evaluations: dict[str, RunEvaluation] = field(default_factory=dict)
    #: Idempotency key -> the pool id that owns it. See `claim_pool_idempotency`.
    pool_claims: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class Repository(Protocol):
    # -- community
    def list_communities(self, ws: str) -> list[Community]: ...
    def get_community(self, ws: str, cid: str) -> Community | None: ...
    def put_community(self, ws: str, c: Community) -> None: ...

    def list_community_memberships(
        self, ws: str, community_id: str | None = None
    ) -> list[CommunityMembership]: ...
    def get_community_membership(
        self, ws: str, community_id: str, household_id: str
    ) -> CommunityMembership | None: ...
    def put_community_membership(self, ws: str, m: CommunityMembership) -> None: ...

    # -- accounts and catalogue
    def list_households(self, ws: str) -> list[Household]: ...
    def get_household(self, ws: str, hid: str) -> Household | None: ...
    def put_household(self, ws: str, h: Household) -> None: ...

    def list_products(self, ws: str) -> list[Product]: ...
    def get_product(self, ws: str, pid: str) -> Product | None: ...
    def put_product(self, ws: str, p: Product) -> None: ...

    def list_needs(self, ws: str) -> list[NeedDeclaration]: ...
    def get_need(self, ws: str, nid: str) -> NeedDeclaration | None: ...
    def put_need(self, ws: str, n: NeedDeclaration) -> None: ...
    def list_coordination_events(self, ws: str) -> list[CoordinationEvent]: ...
    def get_coordination_event(self, ws: str, eid: str) -> CoordinationEvent | None: ...
    def put_coordination_event(self, ws: str, e: CoordinationEvent) -> None: ...
    def list_cohort_strategies(self, ws: str) -> list[CohortStrategy]: ...
    def get_cohort_strategy(self, ws: str, sid: str) -> CohortStrategy | None: ...
    def put_cohort_strategy(self, ws: str, s: CohortStrategy) -> None: ...
    def list_strategy_evaluations(
        self, ws: str, strategy_id: str | None = None
    ) -> list[StrategyEvaluation]: ...
    def get_strategy_evaluation(self, ws: str, eid: str) -> StrategyEvaluation | None: ...
    def put_strategy_evaluation(self, ws: str, e: StrategyEvaluation) -> None: ...

    def list_suppliers(self, ws: str) -> list[Supplier]: ...
    def get_supplier(self, ws: str, sid: str) -> Supplier | None: ...
    def put_supplier(self, ws: str, s: Supplier) -> None: ...

    def list_offers(self, ws: str) -> list[Offer]: ...
    def get_offer(self, ws: str, oid: str) -> Offer | None: ...
    def put_offer(self, ws: str, o: Offer) -> None: ...

    def list_sites(self, ws: str) -> list[PickupSite]: ...
    def get_site(self, ws: str, sid: str) -> PickupSite | None: ...
    def put_site(self, ws: str, s: PickupSite) -> None: ...

    # -- pools
    def list_pools(self, ws: str) -> list[Pool]: ...
    def get_pool(self, ws: str, pid: str) -> Pool | None: ...
    def put_pool(self, ws: str, p: Pool) -> None: ...
    def claim_pool_idempotency(self, ws: str, key: str, pool_id: str) -> str: ...

    def list_memberships(self, ws: str, pool_id: str | None = None) -> list[Membership]: ...
    def get_membership(self, ws: str, pool_id: str, household_id: str) -> Membership | None: ...
    def put_membership(self, ws: str, m: Membership) -> None: ...

    # -- hosting
    def list_host_profiles(self, ws: str, community_id: str | None = None) -> list[HostProfile]: ...
    def get_host_profile(
        self, ws: str, community_id: str, household_id: str
    ) -> HostProfile | None: ...
    def put_host_profile(self, ws: str, p: HostProfile) -> None: ...

    def list_host_candidates(self, ws: str, pool_id: str | None = None) -> list[HostCandidate]: ...
    def get_host_candidate(
        self, ws: str, pool_id: str, household_id: str
    ) -> HostCandidate | None: ...
    def put_host_candidate(self, ws: str, c: HostCandidate) -> None: ...

    def get_host_assignment(self, ws: str, pool_id: str) -> HostAssignment | None: ...
    def put_host_assignment(self, ws: str, a: HostAssignment) -> None: ...
    def list_host_assignments(self, ws: str) -> list[HostAssignment]: ...

    # -- money and goods
    def list_payments(self, ws: str, pool_id: str | None = None) -> list[PaymentRecord]: ...
    def get_payment(self, ws: str, payment_id: str) -> PaymentRecord | None: ...
    def put_payment(self, ws: str, p: PaymentRecord) -> None: ...

    def list_purchases(self, ws: str) -> list[PurchaseRecord]: ...
    def get_purchase_for_pool(self, ws: str, pool_id: str) -> PurchaseRecord | None: ...
    def put_purchase(self, ws: str, p: PurchaseRecord) -> None: ...

    def list_fulfillment_runs(self, ws: str) -> list[FulfillmentRun]: ...
    def put_fulfillment_run(self, ws: str, r: FulfillmentRun) -> None: ...

    def list_allocations(self, ws: str, pool_id: str | None = None) -> list[PickupAllocation]: ...
    def get_allocation(
        self, ws: str, pool_id: str, household_id: str
    ) -> PickupAllocation | None: ...
    def put_allocation(self, ws: str, a: PickupAllocation) -> None: ...

    def list_pickup_tokens(self, ws: str, pool_id: str | None = None) -> list[PickupToken]: ...
    def get_pickup_token(self, ws: str, pool_id: str, household_id: str) -> PickupToken | None: ...
    def put_pickup_token(self, ws: str, t: PickupToken) -> None: ...
    def claim_pickup_redemption(
        self, ws: str, pool_id: str, household_id: str, at: str
    ) -> bool: ...

    # -- communication
    def list_announcements(self, ws: str, pool_id: str | None = None) -> list[Announcement]: ...
    def put_announcement(self, ws: str, a: Announcement) -> None: ...

    def list_threads(self, ws: str, pool_id: str | None = None) -> list[MessageThread]: ...
    def get_thread(self, ws: str, thread_id: str) -> MessageThread | None: ...
    def get_thread_for(self, ws: str, pool_id: str, buyer_id: str) -> MessageThread | None: ...
    def put_thread(self, ws: str, t: MessageThread) -> None: ...

    def list_messages(self, ws: str, thread_id: str) -> list[Message]: ...
    def put_message(self, ws: str, m: Message) -> None: ...

    def list_issues(self, ws: str) -> list[IssueCase]: ...
    def get_issue(self, ws: str, issue_id: str) -> IssueCase | None: ...
    def put_issue(self, ws: str, i: IssueCase) -> None: ...

    # -- agent + audit
    def list_decisions(self, ws: str) -> list[DecisionRequest]: ...
    def get_decision(self, ws: str, did: str) -> DecisionRequest | None: ...
    def put_decision(self, ws: str, d: DecisionRequest) -> None: ...

    def append_activity(self, ws: str, e: ActivityEvent) -> None: ...
    def list_activity(self, ws: str, limit: int = 100) -> list[ActivityEvent]: ...

    def put_run(self, ws: str, r: AgentRun) -> None: ...
    def put_run_evaluation(self, ws: str, e: RunEvaluation) -> None: ...
    def list_run_evaluations(self, ws: str, run_id: str | None = None) -> list[RunEvaluation]: ...
    def get_run(self, ws: str, rid: str) -> AgentRun | None: ...
    def list_runs(self, ws: str, limit: int = 25) -> list[AgentRun]: ...

    def reset(self, ws: str) -> None: ...


class InMemoryRepository:
    """Reference implementation. Also the fixture backend for the whole test suite."""

    def __init__(self) -> None:
        self._ws: dict[str, Store] = {}
        #: Guards the one check-and-set this backend must perform atomically. Everything
        #: else here is a plain dict write, but single-use redemption is a guarantee
        #: rather than a convenience, and the DynamoDB backend enforces it with a
        #: condition — so the reference implementation has to mean the same thing.
        self._redemption_lock = threading.Lock()

    def store(self, ws: str) -> Store:
        return self._ws.setdefault(ws, Store())

    def workspaces(self) -> list[str]:
        return sorted(self._ws.keys())

    @staticmethod
    def _filtered(items, attr: str, value: str | None):
        return [i for i in items if value is None or getattr(i, attr) == value]

    # ---- community
    def list_communities(self, ws): return sorted(self.store(ws).communities.values(), key=lambda c: c.id)
    def get_community(self, ws, cid): return self.store(ws).communities.get(cid)
    def put_community(self, ws, c): self.store(ws).communities[c.id] = c

    def list_community_memberships(self, ws, community_id=None):
        items = self._filtered(self.store(ws).community_memberships.values(), "community_id", community_id)
        return sorted(items, key=lambda m: m.key)

    def get_community_membership(self, ws, community_id, household_id):
        return self.store(ws).community_memberships.get(f"{community_id}#{household_id}")

    def put_community_membership(self, ws, m): self.store(ws).community_memberships[m.key] = m

    # ---- accounts and catalogue
    def list_households(self, ws): return sorted(self.store(ws).households.values(), key=lambda h: h.id)
    def get_household(self, ws, hid): return self.store(ws).households.get(hid)
    def put_household(self, ws, h): self.store(ws).households[h.id] = h

    def list_products(self, ws): return sorted(self.store(ws).products.values(), key=lambda p: p.id)
    def get_product(self, ws, pid): return self.store(ws).products.get(pid)
    def put_product(self, ws, p): self.store(ws).products[p.id] = p

    def list_needs(self, ws): return sorted(self.store(ws).needs.values(), key=lambda n: n.id)
    def get_need(self, ws, nid): return self.store(ws).needs.get(nid)
    def put_need(self, ws, n): self.store(ws).needs[n.id] = n

    def list_coordination_events(self, ws):
        # Oldest first: the order work was owed in is the order a dispatcher takes it.
        return sorted(
            self.store(ws).coordination_events.values(), key=lambda e: (e.created_at, e.id)
        )

    def get_coordination_event(self, ws, eid):
        return self.store(ws).coordination_events.get(eid)

    def put_coordination_event(self, ws, e):
        self.store(ws).coordination_events[e.id] = e

    def list_cohort_strategies(self, ws):
        return sorted(self.store(ws).cohort_strategies.values(), key=lambda s: s.id)

    def get_cohort_strategy(self, ws, sid): return self.store(ws).cohort_strategies.get(sid)

    def put_cohort_strategy(self, ws, s): self.store(ws).cohort_strategies[s.id] = s

    def list_strategy_evaluations(self, ws, strategy_id=None):
        items = [
            e for e in self.store(ws).strategy_evaluations.values()
            if strategy_id is None or e.strategy_id == strategy_id
        ]
        # Newest last, so a caller reading the tail gets the most recent evidence and a
        # replay reads in the order the evaluations actually happened.
        return sorted(items, key=lambda e: (e.at, e.id))

    def get_strategy_evaluation(self, ws, eid):
        return next(
            (e for e in self.store(ws).strategy_evaluations.values() if e.id == eid), None
        )

    def put_strategy_evaluation(self, ws, e): self.store(ws).strategy_evaluations[e.key] = e

    def list_suppliers(self, ws): return sorted(self.store(ws).suppliers.values(), key=lambda s: s.id)
    def get_supplier(self, ws, sid): return self.store(ws).suppliers.get(sid)
    def put_supplier(self, ws, s): self.store(ws).suppliers[s.id] = s

    def list_offers(self, ws): return sorted(self.store(ws).offers.values(), key=lambda o: o.id)
    def get_offer(self, ws, oid): return self.store(ws).offers.get(oid)
    def put_offer(self, ws, o): self.store(ws).offers[o.id] = o

    def list_sites(self, ws): return sorted(self.store(ws).sites.values(), key=lambda s: s.id)
    def get_site(self, ws, sid): return self.store(ws).sites.get(sid)
    def put_site(self, ws, s): self.store(ws).sites[s.id] = s

    # ---- pools
    def list_pools(self, ws): return sorted(self.store(ws).pools.values(), key=lambda p: (p.created_at, p.id))
    def get_pool(self, ws, pid): return self.store(ws).pools.get(pid)
    def put_pool(self, ws, p): self.store(ws).pools[p.id] = p

    def claim_pool_idempotency(self, ws, key, pool_id):
        return self.store(ws).pool_claims.setdefault(key, pool_id)

    def list_memberships(self, ws, pool_id=None):
        items = self._filtered(self.store(ws).memberships.values(), "pool_id", pool_id)
        return sorted(items, key=lambda m: (m.pool_id, m.household_id))

    def get_membership(self, ws, pool_id, household_id):
        return self.store(ws).memberships.get(f"{pool_id}#{household_id}")

    def put_membership(self, ws, m): self.store(ws).memberships[m.key] = m

    # ---- hosting
    def list_host_profiles(self, ws, community_id=None):
        items = self._filtered(self.store(ws).host_profiles.values(), "community_id", community_id)
        return sorted(items, key=lambda p: p.household_id)

    def get_host_profile(self, ws, community_id, household_id):
        return self.store(ws).host_profiles.get(f"{community_id}#{household_id}")

    def put_host_profile(self, ws, p): self.store(ws).host_profiles[p.key] = p

    def list_host_candidates(self, ws, pool_id=None):
        items = self._filtered(self.store(ws).host_candidates.values(), "pool_id", pool_id)
        return sorted(items, key=lambda c: (c.pool_id, -c.score, c.household_id))

    def get_host_candidate(self, ws, pool_id, household_id):
        return self.store(ws).host_candidates.get(f"{pool_id}#{household_id}")

    def put_host_candidate(self, ws, c): self.store(ws).host_candidates[c.key] = c

    def get_host_assignment(self, ws, pool_id): return self.store(ws).host_assignments.get(pool_id)
    def put_host_assignment(self, ws, a): self.store(ws).host_assignments[a.pool_id] = a

    def list_host_assignments(self, ws):
        return sorted(self.store(ws).host_assignments.values(), key=lambda a: a.pool_id)

    # ---- money and goods
    def list_payments(self, ws, pool_id=None):
        items = self._filtered(self.store(ws).payments.values(), "pool_id", pool_id)
        return sorted(items, key=lambda p: p.id)

    def get_payment(self, ws, payment_id): return self.store(ws).payments.get(payment_id)
    def put_payment(self, ws, p): self.store(ws).payments[p.id] = p

    def list_purchases(self, ws): return sorted(self.store(ws).purchases.values(), key=lambda p: p.id)

    def get_purchase_for_pool(self, ws, pool_id):
        for p in self.store(ws).purchases.values():
            if p.pool_id == pool_id:
                return p
        return None

    def put_purchase(self, ws, p): self.store(ws).purchases[p.id] = p

    def list_fulfillment_runs(self, ws):
        return sorted(self.store(ws).fulfillment_runs.values(), key=lambda r: r.id)

    def put_fulfillment_run(self, ws, r): self.store(ws).fulfillment_runs[r.id] = r

    def list_allocations(self, ws, pool_id=None):
        items = self._filtered(self.store(ws).allocations.values(), "pool_id", pool_id)
        return sorted(items, key=lambda a: (a.pool_id, a.household_id))

    def get_allocation(self, ws, pool_id, household_id):
        return self.store(ws).allocations.get(f"{pool_id}#{household_id}")

    def put_allocation(self, ws, a): self.store(ws).allocations[a.key] = a

    def list_pickup_tokens(self, ws, pool_id=None):
        items = self._filtered(self.store(ws).pickup_tokens.values(), "pool_id", pool_id)
        return sorted(items, key=lambda t: t.key)

    def get_pickup_token(self, ws, pool_id, household_id):
        return self.store(ws).pickup_tokens.get(f"{pool_id}#{household_id}")

    def put_pickup_token(self, ws, t): self.store(ws).pickup_tokens[t.key] = t

    def claim_pickup_redemption(self, ws, pool_id, household_id, at):
        with self._redemption_lock:
            token = self.store(ws).pickup_tokens.get(f"{pool_id}#{household_id}")
            if token is None or token.redeemed_at:
                return False
            token.redeemed_at = at
            return True

    # ---- communication
    def list_announcements(self, ws, pool_id=None):
        items = self._filtered(self.store(ws).announcements.values(), "pool_id", pool_id)
        return sorted(items, key=lambda a: a.created_at, reverse=True)

    def put_announcement(self, ws, a): self.store(ws).announcements[a.id] = a

    def list_threads(self, ws, pool_id=None):
        items = self._filtered(self.store(ws).threads.values(), "pool_id", pool_id)
        return sorted(items, key=lambda t: t.created_at)

    def get_thread(self, ws, thread_id):
        for t in self.store(ws).threads.values():
            if t.id == thread_id:
                return t
        return None

    def get_thread_for(self, ws, pool_id, buyer_id):
        return self.store(ws).threads.get(f"{pool_id}#{buyer_id}")

    def put_thread(self, ws, t): self.store(ws).threads[t.key] = t

    def list_messages(self, ws, thread_id):
        return sorted(
            (m for m in self.store(ws).messages.values() if m.thread_id == thread_id),
            key=lambda m: m.at,
        )

    def put_message(self, ws, m): self.store(ws).messages[m.id] = m

    def list_issues(self, ws): return sorted(self.store(ws).issues.values(), key=lambda i: i.created_at)
    def get_issue(self, ws, issue_id): return self.store(ws).issues.get(issue_id)
    def put_issue(self, ws, i): self.store(ws).issues[i.id] = i

    # ---- agent + audit
    def list_decisions(self, ws):
        return sorted(self.store(ws).decisions.values(), key=lambda d: (d.created_at, d.id))

    def get_decision(self, ws, did): return self.store(ws).decisions.get(did)
    def put_decision(self, ws, d): self.store(ws).decisions[d.id] = d

    def append_activity(self, ws, e): self.store(ws).activity.append(e)

    def list_activity(self, ws, limit=100):
        # Newest first, with insertion order as the tiebreak so events written inside
        # the same millisecond still read in the order they actually happened.
        items = list(enumerate(self.store(ws).activity))
        items.sort(key=lambda pair: (pair[1].at, pair[0]), reverse=True)
        return [e for _, e in items[:limit]]

    def put_run(self, ws, r): self.store(ws).runs[r.id] = r

    def put_run_evaluation(self, ws, e): self.store(ws).run_evaluations[e.key] = e

    def list_run_evaluations(self, ws, run_id=None):
        items = [
            e for e in self.store(ws).run_evaluations.values()
            if run_id is None or e.run_id == run_id
        ]
        return sorted(items, key=lambda e: (e.at, e.id))
    def get_run(self, ws, rid): return self.store(ws).runs.get(rid)

    def list_runs(self, ws, limit=25):
        return sorted(self.store(ws).runs.values(), key=lambda r: r.started_at, reverse=True)[:limit]

    def reset(self, ws): self._ws[ws] = Store()


# --------------------------------------------------------------------- DynamoDB


#: type name -> domain class. Drives both persistence and workspace reset, so a new
#: entity cannot be added to one and forgotten in the other.
_TYPES: dict[str, Any] = {
    "COMMUNITY": Community,
    "COMMUNITY_MEMBERSHIP": CommunityMembership,
    "HOUSEHOLD": Household,
    "PRODUCT": Product,
    "NEED": NeedDeclaration,
    "SUPPLIER": Supplier,
    "OFFER": Offer,
    "SITE": PickupSite,
    "POOL": Pool,
    "MEMBERSHIP": Membership,
    "HOST_PROFILE": HostProfile,
    "HOST_CANDIDATE": HostCandidate,
    "HOST_ASSIGNMENT": HostAssignment,
    "PAYMENT": PaymentRecord,
    "PURCHASE": PurchaseRecord,
    "FULFILLMENT_RUN": FulfillmentRun,
    "ALLOCATION": PickupAllocation,
    "PICKUP_TOKEN": PickupToken,
    "ANNOUNCEMENT": Announcement,
    "THREAD": MessageThread,
    "MESSAGE": Message,
    "ISSUE": IssueCase,
    "DECISION": DecisionRequest,
    "ACTIVITY": ActivityEvent,
    "RUN": AgentRun,
    "RUN_EVALUATION": RunEvaluation,
    "COORDINATION_EVENT": CoordinationEvent,
    "COHORT_STRATEGY": CohortStrategy,
    "STRATEGY_EVALUATION": StrategyEvaluation,
}


def _to_item(obj: Any) -> dict:
    """Serialise a domain object to a DynamoDB-safe dict.

    Floats are not natively storable by the resource API's default serialiser, so
    coordinates are stored as tagged strings and restored on read. Money is already
    integer cents and stores exactly.
    """
    d = obj.to_dict() if hasattr(obj, "to_dict") else dict(obj.__dict__)
    return _floats_to_str(d)


def _floats_to_str(value: Any) -> Any:
    if isinstance(value, float):
        return {"__float__": repr(value)}
    if isinstance(value, dict):
        return {k: _floats_to_str(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_floats_to_str(v) for v in value]
    return value


def _from_item(value: Any) -> Any:
    """Restore a stored item to native Python types.

    Two conversions, and the second one cost a deployment.

    Tagged floats go back to ``float`` — the write side's own encoding.

    **Every DynamoDB number reads back as ``decimal.Decimal``**, whatever it was when
    written. Pool stores money as integer cents and stores coordinates as tagged
    strings, so every ``Decimal`` arriving here was an ``int`` on the way in — but
    nothing was converting it back. It survived arithmetic silently (``Decimal`` and
    ``int`` mix fine) and then failed at the display edge: ``format_cents`` does
    ``f"{cents % 100:02d}"``, and ``d`` is not a valid presentation type for
    ``Decimal``. The first real showcase run on a real table returned HTTP 500 with
    ``ValueError: invalid format string`` (#0024). A fake table that stores Python
    objects verbatim cannot reproduce this; only the type system can.
    """
    if isinstance(value, Decimal):
        # Integral by construction. `int()` on a non-integral Decimal would truncate
        # silently, so fall back to float rather than lose a fraction unnoticed.
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        if set(value.keys()) == {"__float__"}:
            return float(value["__float__"])
        return {k: _from_item(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_from_item(v) for v in value]
    return value


class DynamoDBRepository:
    """Single-table DynamoDB implementation of :class:`Repository`.

    Deliberately unverified against a live table at the time of writing — no AWS
    credentials were available. The item shapes and key schema are exercised by a
    fake-client test so the serialisation contract is at least pinned; the CDK stack
    in ``infra/`` provisions the matching table (on-demand billing, TTL on ``ttl``).

    ``consistent_reads`` asks DynamoDB for a strongly consistent read on every
    ``GetItem`` and ``Query``. It is off by default and on wherever **two compute
    environments write the same partition inside one user-visible action** — the demo
    Lambda and the AgentCore runtime now do exactly that. An eventually consistent read
    may be served by a replica that has not yet seen the runtime's writes, which would
    let the browser refresh after a live agent run and see the world as it was before
    it. That is a rare race and an unacceptable one here, because "the browser observes
    the state the deployed agent produced" is the claim the whole path exists to make.
    A strongly consistent read costs 1 RRU instead of 0.5 on a table billed per request
    (AGENTS.md §3.5): about $0.06 per million extra reads, against a demo that does
    thousands.
    """

    def __init__(
        self,
        table_name: str,
        region_name: str = "us-east-1",
        table=None,
        consistent_reads: bool = False,
    ) -> None:
        self.table_name = table_name
        self.region_name = region_name
        self.consistent_reads = consistent_reads
        self._table = table

    @property
    def table(self):
        if self._table is None:
            import boto3

            self._table = boto3.resource("dynamodb", region_name=self.region_name).Table(
                self.table_name
            )
        return self._table

    @staticmethod
    def _pk(ws: str, type_name: str) -> str:
        return f"{ws}#{type_name}"

    def _put(self, ws: str, type_name: str, sk: str, obj: Any) -> None:
        item = {"pk": self._pk(ws, type_name), "sk": sk, "data": _to_item(obj)}
        if ws != "primary":
            item["ttl"] = int(time.time()) + DEMO_TTL_SECONDS
        self.table.put_item(Item=item)

    def _get(self, ws: str, type_name: str, sk: str, cls) -> Any | None:
        # An empty id is a row that cannot exist, and the two backends disagreed about
        # how to say so. `InMemoryRepository` returns None, so a service that looks up a
        # caller-supplied id gets a clean "unknown member" 400. DynamoDB rejects an empty
        # key attribute at the API — `ValidationException: The AttributeValue for a key
        # attribute cannot contain an empty string value` — which nothing catches, so the
        # same request became a 500 on the deployed function while every local test stayed
        # green. Observed in production on `POST /api/needs` with `household_id: ""`.
        #
        # Answering None here rather than validating at each call site fixes the whole
        # class in the one place both backends have to agree, and it cannot hide a real
        # row: `_put` would have been rejected by the same rule, so no row with an empty
        # key was ever written.
        if not sk:
            return None
        kwargs: dict[str, Any] = {"Key": {"pk": self._pk(ws, type_name), "sk": sk}}
        if self.consistent_reads:
            kwargs["ConsistentRead"] = True
        resp = self.table.get_item(**kwargs)
        item = resp.get("Item")
        if not item:
            return None
        return self._load(cls, item["data"])

    def _query(self, ws: str, type_name: str, cls, sk_prefix: str | None = None) -> list[Any]:
        from boto3.dynamodb.conditions import Key

        cond = Key("pk").eq(self._pk(ws, type_name))
        if sk_prefix:
            cond = cond & Key("sk").begins_with(sk_prefix)
        out: list[Any] = []
        kwargs: dict[str, Any] = {"KeyConditionExpression": cond}
        if self.consistent_reads:
            kwargs["ConsistentRead"] = True
        while True:
            resp = self.table.query(**kwargs)
            out.extend(self._load(cls, it["data"]) for it in resp.get("Items", []))
            token = resp.get("LastEvaluatedKey")
            if not token:
                return out
            kwargs["ExclusiveStartKey"] = token

    @staticmethod
    def _load(cls, data: dict) -> Any:
        restored = _from_item(data)
        if hasattr(cls, "from_dict"):
            return cls.from_dict(restored)
        return cls(**restored)

    # ---- community
    def list_communities(self, ws): return self._query(ws, "COMMUNITY", Community)
    def get_community(self, ws, cid): return self._get(ws, "COMMUNITY", cid, Community)
    def put_community(self, ws, c): self._put(ws, "COMMUNITY", c.id, c)

    def list_community_memberships(self, ws, community_id=None):
        return self._query(
            ws, "COMMUNITY_MEMBERSHIP", CommunityMembership,
            f"{community_id}#" if community_id else None,
        )

    def get_community_membership(self, ws, community_id, household_id):
        return self._get(
            ws, "COMMUNITY_MEMBERSHIP", f"{community_id}#{household_id}", CommunityMembership
        )

    def put_community_membership(self, ws, m): self._put(ws, "COMMUNITY_MEMBERSHIP", m.key, m)

    # ---- accounts and catalogue
    def list_households(self, ws): return self._query(ws, "HOUSEHOLD", Household)
    def get_household(self, ws, hid): return self._get(ws, "HOUSEHOLD", hid, Household)
    def put_household(self, ws, h): self._put(ws, "HOUSEHOLD", h.id, h)

    def list_products(self, ws): return self._query(ws, "PRODUCT", Product)
    def get_product(self, ws, pid): return self._get(ws, "PRODUCT", pid, Product)
    def put_product(self, ws, p): self._put(ws, "PRODUCT", p.id, p)

    def list_needs(self, ws): return self._query(ws, "NEED", NeedDeclaration)
    def get_need(self, ws, nid): return self._get(ws, "NEED", nid, NeedDeclaration)
    def put_need(self, ws, n): self._put(ws, "NEED", n.id, n)

    def list_coordination_events(self, ws):
        return sorted(
            self._query(ws, "COORDINATION_EVENT", CoordinationEvent),
            key=lambda e: (e.created_at, e.id),
        )

    def get_coordination_event(self, ws, eid):
        return self._get(ws, "COORDINATION_EVENT", eid, CoordinationEvent)

    def put_coordination_event(self, ws, e):
        self._put(ws, "COORDINATION_EVENT", e.id, e)

    def list_cohort_strategies(self, ws):
        return sorted(self._query(ws, "COHORT_STRATEGY", CohortStrategy), key=lambda s: s.id)

    def get_cohort_strategy(self, ws, sid):
        return self._get(ws, "COHORT_STRATEGY", sid, CohortStrategy)

    def put_cohort_strategy(self, ws, s): self._put(ws, "COHORT_STRATEGY", s.id, s)

    def list_strategy_evaluations(self, ws, strategy_id=None):
        # `key` is "<strategy_id>#<evaluation id>", so one strategy's evidence is a
        # begins_with query rather than a scan of every evaluation in the workspace.
        items = self._query(
            ws, "STRATEGY_EVALUATION", StrategyEvaluation,
            f"{strategy_id}#" if strategy_id else None,
        )
        return sorted(items, key=lambda e: (e.at, e.id))

    def get_strategy_evaluation(self, ws, eid):
        return next(
            (
                e
                for e in self._query(ws, "STRATEGY_EVALUATION", StrategyEvaluation)
                if e.id == eid
            ),
            None,
        )

    def put_strategy_evaluation(self, ws, e):
        self._put(ws, "STRATEGY_EVALUATION", e.key, e)

    def list_suppliers(self, ws): return self._query(ws, "SUPPLIER", Supplier)
    def get_supplier(self, ws, sid): return self._get(ws, "SUPPLIER", sid, Supplier)
    def put_supplier(self, ws, s): self._put(ws, "SUPPLIER", s.id, s)

    def list_offers(self, ws): return self._query(ws, "OFFER", Offer)
    def get_offer(self, ws, oid): return self._get(ws, "OFFER", oid, Offer)
    def put_offer(self, ws, o): self._put(ws, "OFFER", o.id, o)

    def list_sites(self, ws): return self._query(ws, "SITE", PickupSite)
    def get_site(self, ws, sid): return self._get(ws, "SITE", sid, PickupSite)
    def put_site(self, ws, s): self._put(ws, "SITE", s.id, s)

    # ---- pools
    #
    # Several of the list methods below re-sort after querying. That is not
    # redundancy: a Query returns items in sort-key order, and where the sort key is a
    # random id, "sort-key order" is arbitrary. The in-memory repository defines the
    # ordering contract the application and the UI are written against — a Decision
    # Inbox is chronological, a run list is newest-first, host candidates are ranked —
    # so this adapter reproduces that contract explicitly rather than inheriting
    # whatever DynamoDB's key order happens to be.
    def list_pools(self, ws):
        return sorted(self._query(ws, "POOL", Pool), key=lambda p: (p.created_at, p.id))
    def get_pool(self, ws, pid): return self._get(ws, "POOL", pid, Pool)
    def put_pool(self, ws, p): self._put(ws, "POOL", p.id, p)

    def claim_pool_idempotency(self, ws, key, pool_id):
        """Atomically decide which pool id owns an idempotency key.

        The existing check — scan the pools, look for a matching key — is a read
        followed by a write, so two coordinators that both find nothing both create a
        pool. The workspace lease normally keeps them apart, but a lease is a
        best-effort coordination row and this is the write it is protecting, so the
        invariant is also enforced where it actually lives.

        The claim is written *before* the pool, carrying the id the caller intends to
        use, and the loser is told that id rather than being refused. That ordering is
        what makes a crash between the two writes recoverable: the next caller reads
        the claim, finds no pool under it, and creates that same agreed id — instead of
        a key nobody can ever use again.
        """
        item = {"pk": self._pk(ws, "POOL_CLAIM"), "sk": key, "data": {"pool_id": pool_id}}
        if ws != "primary":
            item["ttl"] = int(time.time()) + DEMO_TTL_SECONDS
        try:
            self.table.put_item(
                Item=item, ConditionExpression="attribute_not_exists(pk)"
            )
            return pool_id
        except Exception as exc:  # noqa: BLE001 - the conditional failure is the signal
            if type(exc).__name__ != "ConditionalCheckFailedException":
                raise
        resp = self.table.get_item(
            Key={"pk": self._pk(ws, "POOL_CLAIM"), "sk": key},
            **({"ConsistentRead": True} if self.consistent_reads else {}),
        )
        stored = (resp.get("Item") or {}).get("data") or {}
        return str(stored.get("pool_id") or pool_id)

    def list_memberships(self, ws, pool_id=None):
        return self._query(ws, "MEMBERSHIP", Membership, f"{pool_id}#" if pool_id else None)

    def get_membership(self, ws, pool_id, household_id):
        return self._get(ws, "MEMBERSHIP", f"{pool_id}#{household_id}", Membership)

    def put_membership(self, ws, m): self._put(ws, "MEMBERSHIP", m.key, m)

    # ---- hosting
    def list_host_profiles(self, ws, community_id=None):
        return self._query(
            ws, "HOST_PROFILE", HostProfile, f"{community_id}#" if community_id else None
        )

    def get_host_profile(self, ws, community_id, household_id):
        return self._get(ws, "HOST_PROFILE", f"{community_id}#{household_id}", HostProfile)

    def put_host_profile(self, ws, p): self._put(ws, "HOST_PROFILE", p.key, p)

    def list_host_candidates(self, ws, pool_id=None):
        # Ranked best-first. Host *selection* takes an explicit max() and does not
        # depend on this, but the operator and pool views render the list in order,
        # and an unranked ranking is a misleading one.
        items = self._query(
            ws, "HOST_CANDIDATE", HostCandidate, f"{pool_id}#" if pool_id else None
        )
        return sorted(items, key=lambda c: (c.pool_id, -c.score, c.household_id))

    def get_host_candidate(self, ws, pool_id, household_id):
        return self._get(ws, "HOST_CANDIDATE", f"{pool_id}#{household_id}", HostCandidate)

    def put_host_candidate(self, ws, c): self._put(ws, "HOST_CANDIDATE", c.key, c)

    def get_host_assignment(self, ws, pool_id):
        return self._get(ws, "HOST_ASSIGNMENT", pool_id, HostAssignment)

    def put_host_assignment(self, ws, a): self._put(ws, "HOST_ASSIGNMENT", a.pool_id, a)
    def list_host_assignments(self, ws): return self._query(ws, "HOST_ASSIGNMENT", HostAssignment)

    # ---- money and goods
    def list_payments(self, ws, pool_id=None):
        items = self._query(ws, "PAYMENT", PaymentRecord)
        return [p for p in items if pool_id is None or p.pool_id == pool_id]

    def get_payment(self, ws, payment_id): return self._get(ws, "PAYMENT", payment_id, PaymentRecord)
    def put_payment(self, ws, p): self._put(ws, "PAYMENT", p.id, p)

    def list_purchases(self, ws): return self._query(ws, "PURCHASE", PurchaseRecord)

    def get_purchase_for_pool(self, ws, pool_id):
        for p in self.list_purchases(ws):
            if p.pool_id == pool_id:
                return p
        return None

    def put_purchase(self, ws, p): self._put(ws, "PURCHASE", p.id, p)

    def list_fulfillment_runs(self, ws): return self._query(ws, "FULFILLMENT_RUN", FulfillmentRun)
    def put_fulfillment_run(self, ws, r): self._put(ws, "FULFILLMENT_RUN", r.id, r)

    def list_allocations(self, ws, pool_id=None):
        return self._query(ws, "ALLOCATION", PickupAllocation, f"{pool_id}#" if pool_id else None)

    def get_allocation(self, ws, pool_id, household_id):
        return self._get(ws, "ALLOCATION", f"{pool_id}#{household_id}", PickupAllocation)

    def put_allocation(self, ws, a): self._put(ws, "ALLOCATION", a.key, a)

    def list_pickup_tokens(self, ws, pool_id=None):
        return self._query(ws, "PICKUP_TOKEN", PickupToken, f"{pool_id}#" if pool_id else None)

    def get_pickup_token(self, ws, pool_id, household_id):
        return self._get(ws, "PICKUP_TOKEN", f"{pool_id}#{household_id}", PickupToken)

    def put_pickup_token(self, ws, t): self._put(ws, "PICKUP_TOKEN", t.key, t)

    def claim_pickup_redemption(self, ws, pool_id, household_id, at):
        """Mark one credential redeemed, once, atomically.

        Single use is the guarantee the whole pickup design rests on (canonical
        invariant 9), and it was enforced by reading ``redeemed_at`` and then writing
        it — two scans of one QR code arriving together both read empty and both
        completed the handoff. The condition makes the check and the write one
        operation, so the second scan loses and is told the credential is spent.

        ``redeemed_at`` defaults to an empty string rather than being absent, so the
        condition has to accept both shapes: a row written before this method existed
        carries the empty string.
        """
        try:
            self.table.update_item(
                Key={"pk": self._pk(ws, "PICKUP_TOKEN"), "sk": f"{pool_id}#{household_id}"},
                UpdateExpression="SET #data.#redeemed = :at",
                ConditionExpression=(
                    "attribute_exists(pk) AND "
                    "(attribute_not_exists(#data.#redeemed) OR #data.#redeemed = :empty)"
                ),
                ExpressionAttributeNames={"#data": "data", "#redeemed": "redeemed_at"},
                ExpressionAttributeValues={":at": at, ":empty": ""},
            )
            return True
        except Exception as exc:  # noqa: BLE001 - the conditional failure is the signal
            if type(exc).__name__ == "ConditionalCheckFailedException":
                return False
            raise

    # ---- communication
    def list_announcements(self, ws, pool_id=None):
        items = self._query(ws, "ANNOUNCEMENT", Announcement)
        items = [a for a in items if pool_id is None or a.pool_id == pool_id]
        return sorted(items, key=lambda a: a.created_at, reverse=True)

    def put_announcement(self, ws, a): self._put(ws, "ANNOUNCEMENT", a.id, a)

    def list_threads(self, ws, pool_id=None):
        items = self._query(ws, "THREAD", MessageThread, f"{pool_id}#" if pool_id else None)
        return sorted(items, key=lambda t: t.created_at)

    def get_thread(self, ws, thread_id):
        for t in self.list_threads(ws):
            if t.id == thread_id:
                return t
        return None

    def get_thread_for(self, ws, pool_id, buyer_id):
        return self._get(ws, "THREAD", f"{pool_id}#{buyer_id}", MessageThread)

    def put_thread(self, ws, t): self._put(ws, "THREAD", t.key, t)

    def list_messages(self, ws, thread_id):
        items = self._query(ws, "MESSAGE", Message, f"{thread_id}#")
        return sorted(items, key=lambda m: m.at)

    def put_message(self, ws, m): self._put(ws, "MESSAGE", f"{m.thread_id}#{m.at}#{m.id}", m)

    def list_issues(self, ws):
        return sorted(self._query(ws, "ISSUE", IssueCase), key=lambda i: i.created_at)
    def get_issue(self, ws, issue_id): return self._get(ws, "ISSUE", issue_id, IssueCase)
    def put_issue(self, ws, i): self._put(ws, "ISSUE", i.id, i)

    # ---- agent + audit
    def list_decisions(self, ws):
        # Oldest first: this is an inbox, and the sort key is a random decision id.
        items = self._query(ws, "DECISION", DecisionRequest)
        return sorted(items, key=lambda d: (d.created_at, d.id))
    def get_decision(self, ws, did): return self._get(ws, "DECISION", did, DecisionRequest)
    def put_decision(self, ws, d): self._put(ws, "DECISION", d.id, d)

    def append_activity(self, ws, e): self._put(ws, "ACTIVITY", f"{e.at}#{e.id}", e)

    def list_activity(self, ws, limit=100):
        items = self._query(ws, "ACTIVITY", ActivityEvent)
        return sorted(items, key=lambda e: e.at, reverse=True)[:limit]

    def put_run(self, ws, r): self._put(ws, "RUN", r.id, r)

    def put_run_evaluation(self, ws, e): self._put(ws, "RUN_EVALUATION", e.key, e)

    def list_run_evaluations(self, ws, run_id=None):
        items = self._query(
            ws, "RUN_EVALUATION", RunEvaluation, f"{run_id}#" if run_id else None
        )
        return sorted(items, key=lambda e: (e.at, e.id))
    def get_run(self, ws, rid): return self._get(ws, "RUN", rid, AgentRun)

    def list_runs(self, ws, limit=25):
        items = self._query(ws, "RUN", AgentRun)
        return sorted(items, key=lambda r: r.started_at, reverse=True)[:limit]

    def reset(self, ws: str) -> None:
        """Delete every item in a workspace. Scoped by partition key — it can never
        reach another workspace, let alone another table (AGENTS.md §3.8)."""
        from boto3.dynamodb.conditions import Key

        for type_name in (*_TYPES, "POOL_CLAIM"):
            kwargs: dict[str, Any] = {
                "KeyConditionExpression": Key("pk").eq(self._pk(ws, type_name)),
                "ProjectionExpression": "pk, sk",
            }
            while True:
                resp = self.table.query(**kwargs)
                with self.table.batch_writer() as batch:
                    for it in resp.get("Items", []):
                        batch.delete_item(Key={"pk": it["pk"], "sk": it["sk"]})
                token = resp.get("LastEvaluatedKey")
                if not token:
                    break
                kwargs["ExclusiveStartKey"] = token


def build_repository(
    kind: str, table_name: str, region_name: str, consistent_reads: bool = False
) -> Repository:
    if kind == "memory":
        return InMemoryRepository()
    if kind == "dynamodb":
        return DynamoDBRepository(
            table_name=table_name,
            region_name=region_name,
            consistent_reads=consistent_reads,
        )
    raise ValueError(f"unknown repository kind: {kind!r}")
