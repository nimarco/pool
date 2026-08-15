"""State persistence.

DynamoDB is the authoritative store for everything transactional — pool membership,
commitments, money, quantities, deadlines, and explicit policies. Agent memory is
never authoritative for any of it (AGENTS.md §6).

Two implementations behind one protocol:

* ``InMemoryRepository`` — used by every test and by local runs. Free.
* ``DynamoDBRepository`` — on-demand billing, single table, TTL on demo workspaces.

Table design (single table, on-demand):

    pk = "<workspace>#<TYPE>"     sk = "<entity id>"

Listing a type is one Query on ``pk``; memberships use a composite sort key
(``<pool_id>#<household_id>``) so a pool's members are a ``begins_with`` query rather
than a scan. Workspaces give each demo visitor an isolated dataset that a TTL sweeps
away, which keeps two judges from corrupting each other's demo.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from ..domain.models import (
    ActivityEvent,
    AgentRun,
    DecisionRequest,
    Household,
    Membership,
    NeedDeclaration,
    Offer,
    PickupSite,
    Pool,
    Product,
)

DEFAULT_WORKSPACE = "demo"
DEMO_TTL_SECONDS = 60 * 60 * 24  # ephemeral demo workspaces expire after a day


@dataclass
class Store:
    """The whole world for one workspace."""

    households: dict[str, Household] = field(default_factory=dict)
    products: dict[str, Product] = field(default_factory=dict)
    needs: dict[str, NeedDeclaration] = field(default_factory=dict)
    offers: dict[str, Offer] = field(default_factory=dict)
    sites: dict[str, PickupSite] = field(default_factory=dict)
    pools: dict[str, Pool] = field(default_factory=dict)
    memberships: dict[str, Membership] = field(default_factory=dict)  # "pool#household"
    decisions: dict[str, DecisionRequest] = field(default_factory=dict)
    activity: list[ActivityEvent] = field(default_factory=list)
    runs: dict[str, AgentRun] = field(default_factory=dict)


@runtime_checkable
class Repository(Protocol):
    def list_households(self, ws: str) -> list[Household]: ...
    def get_household(self, ws: str, hid: str) -> Household | None: ...
    def put_household(self, ws: str, h: Household) -> None: ...

    def list_products(self, ws: str) -> list[Product]: ...
    def get_product(self, ws: str, pid: str) -> Product | None: ...
    def put_product(self, ws: str, p: Product) -> None: ...

    def list_needs(self, ws: str) -> list[NeedDeclaration]: ...
    def get_need(self, ws: str, nid: str) -> NeedDeclaration | None: ...
    def put_need(self, ws: str, n: NeedDeclaration) -> None: ...

    def list_offers(self, ws: str) -> list[Offer]: ...
    def get_offer(self, ws: str, oid: str) -> Offer | None: ...
    def put_offer(self, ws: str, o: Offer) -> None: ...

    def list_sites(self, ws: str) -> list[PickupSite]: ...
    def get_site(self, ws: str, sid: str) -> PickupSite | None: ...
    def put_site(self, ws: str, s: PickupSite) -> None: ...

    def list_pools(self, ws: str) -> list[Pool]: ...
    def get_pool(self, ws: str, pid: str) -> Pool | None: ...
    def put_pool(self, ws: str, p: Pool) -> None: ...

    def list_memberships(self, ws: str, pool_id: str | None = None) -> list[Membership]: ...
    def get_membership(self, ws: str, pool_id: str, household_id: str) -> Membership | None: ...
    def put_membership(self, ws: str, m: Membership) -> None: ...

    def list_decisions(self, ws: str) -> list[DecisionRequest]: ...
    def get_decision(self, ws: str, did: str) -> DecisionRequest | None: ...
    def put_decision(self, ws: str, d: DecisionRequest) -> None: ...

    def append_activity(self, ws: str, e: ActivityEvent) -> None: ...
    def list_activity(self, ws: str, limit: int = 100) -> list[ActivityEvent]: ...

    def put_run(self, ws: str, r: AgentRun) -> None: ...
    def get_run(self, ws: str, rid: str) -> AgentRun | None: ...
    def list_runs(self, ws: str, limit: int = 25) -> list[AgentRun]: ...

    def reset(self, ws: str) -> None: ...


class InMemoryRepository:
    """Reference implementation. Also the fixture backend for the whole test suite."""

    def __init__(self) -> None:
        self._ws: dict[str, Store] = {}

    def store(self, ws: str) -> Store:
        return self._ws.setdefault(ws, Store())

    def workspaces(self) -> list[str]:
        return sorted(self._ws.keys())

    # ---- households
    def list_households(self, ws): return sorted(self.store(ws).households.values(), key=lambda h: h.id)
    def get_household(self, ws, hid): return self.store(ws).households.get(hid)
    def put_household(self, ws, h): self.store(ws).households[h.id] = h

    # ---- products
    def list_products(self, ws): return sorted(self.store(ws).products.values(), key=lambda p: p.id)
    def get_product(self, ws, pid): return self.store(ws).products.get(pid)
    def put_product(self, ws, p): self.store(ws).products[p.id] = p

    # ---- needs
    def list_needs(self, ws): return sorted(self.store(ws).needs.values(), key=lambda n: n.id)
    def get_need(self, ws, nid): return self.store(ws).needs.get(nid)
    def put_need(self, ws, n): self.store(ws).needs[n.id] = n

    # ---- offers
    def list_offers(self, ws): return sorted(self.store(ws).offers.values(), key=lambda o: o.id)
    def get_offer(self, ws, oid): return self.store(ws).offers.get(oid)
    def put_offer(self, ws, o): self.store(ws).offers[o.id] = o

    # ---- sites
    def list_sites(self, ws): return sorted(self.store(ws).sites.values(), key=lambda s: s.id)
    def get_site(self, ws, sid): return self.store(ws).sites.get(sid)
    def put_site(self, ws, s): self.store(ws).sites[s.id] = s

    # ---- pools
    def list_pools(self, ws): return sorted(self.store(ws).pools.values(), key=lambda p: p.created_at)
    def get_pool(self, ws, pid): return self.store(ws).pools.get(pid)
    def put_pool(self, ws, p): self.store(ws).pools[p.id] = p

    # ---- memberships
    def list_memberships(self, ws, pool_id=None):
        items = self.store(ws).memberships.values()
        if pool_id is not None:
            items = [m for m in items if m.pool_id == pool_id]
        return sorted(items, key=lambda m: (m.pool_id, m.household_id))

    def get_membership(self, ws, pool_id, household_id):
        return self.store(ws).memberships.get(f"{pool_id}#{household_id}")

    def put_membership(self, ws, m):
        self.store(ws).memberships[f"{m.pool_id}#{m.household_id}"] = m

    # ---- decisions
    def list_decisions(self, ws): return sorted(self.store(ws).decisions.values(), key=lambda d: d.created_at)
    def get_decision(self, ws, did): return self.store(ws).decisions.get(did)
    def put_decision(self, ws, d): self.store(ws).decisions[d.id] = d

    # ---- activity
    def append_activity(self, ws, e): self.store(ws).activity.append(e)

    def list_activity(self, ws, limit=100):
        return sorted(self.store(ws).activity, key=lambda e: e.at, reverse=True)[:limit]

    # ---- runs
    def put_run(self, ws, r): self.store(ws).runs[r.id] = r
    def get_run(self, ws, rid): return self.store(ws).runs.get(rid)

    def list_runs(self, ws, limit=25):
        return sorted(self.store(ws).runs.values(), key=lambda r: r.started_at, reverse=True)[:limit]

    def reset(self, ws): self._ws[ws] = Store()


# --------------------------------------------------------------------- DynamoDB


_TYPES = {
    "HOUSEHOLD": (Household, "households"),
    "PRODUCT": (Product, "products"),
    "NEED": (NeedDeclaration, "needs"),
    "OFFER": (Offer, "offers"),
    "SITE": (PickupSite, "sites"),
    "POOL": (Pool, "pools"),
    "MEMBERSHIP": (Membership, "memberships"),
    "DECISION": (DecisionRequest, "decisions"),
    "ACTIVITY": (ActivityEvent, "activity"),
    "RUN": (AgentRun, "runs"),
}


def _to_item(obj: Any) -> dict:
    """Serialise a domain object to a DynamoDB-safe dict.

    Floats are not natively storable by the resource API's default serialiser, so
    coordinates are stored as strings and restored on read. Money is already integer
    cents and stores exactly.
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


def _str_to_floats(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value.keys()) == {"__float__"}:
            return float(value["__float__"])
        return {k: _str_to_floats(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_str_to_floats(v) for v in value]
    return value


class DynamoDBRepository:
    """Single-table DynamoDB implementation of :class:`Repository`.

    Deliberately unverified against a live table at the time of writing — no AWS
    credentials were available. The item shapes and key schema are exercised by a
    fake-client test so the serialisation contract is at least pinned; the CDK stack
    in ``infra/`` provisions the matching table (on-demand billing, TTL on ``ttl``).
    """

    def __init__(self, table_name: str, region_name: str = "us-east-1", table=None) -> None:
        self.table_name = table_name
        self.region_name = region_name
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
        resp = self.table.get_item(Key={"pk": self._pk(ws, type_name), "sk": sk})
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
        while True:
            resp = self.table.query(**kwargs)
            out.extend(self._load(cls, it["data"]) for it in resp.get("Items", []))
            token = resp.get("LastEvaluatedKey")
            if not token:
                return out
            kwargs["ExclusiveStartKey"] = token

    @staticmethod
    def _load(cls, data: dict) -> Any:
        restored = _str_to_floats(data)
        if hasattr(cls, "from_dict"):
            return cls.from_dict(restored)
        return cls(**restored)

    # ---- entity methods
    def list_households(self, ws): return self._query(ws, "HOUSEHOLD", Household)
    def get_household(self, ws, hid): return self._get(ws, "HOUSEHOLD", hid, Household)
    def put_household(self, ws, h): self._put(ws, "HOUSEHOLD", h.id, h)

    def list_products(self, ws): return self._query(ws, "PRODUCT", Product)
    def get_product(self, ws, pid): return self._get(ws, "PRODUCT", pid, Product)
    def put_product(self, ws, p): self._put(ws, "PRODUCT", p.id, p)

    def list_needs(self, ws): return self._query(ws, "NEED", NeedDeclaration)
    def get_need(self, ws, nid): return self._get(ws, "NEED", nid, NeedDeclaration)
    def put_need(self, ws, n): self._put(ws, "NEED", n.id, n)

    def list_offers(self, ws): return self._query(ws, "OFFER", Offer)
    def get_offer(self, ws, oid): return self._get(ws, "OFFER", oid, Offer)
    def put_offer(self, ws, o): self._put(ws, "OFFER", o.id, o)

    def list_sites(self, ws): return self._query(ws, "SITE", PickupSite)
    def get_site(self, ws, sid): return self._get(ws, "SITE", sid, PickupSite)
    def put_site(self, ws, s): self._put(ws, "SITE", s.id, s)

    def list_pools(self, ws): return self._query(ws, "POOL", Pool)
    def get_pool(self, ws, pid): return self._get(ws, "POOL", pid, Pool)
    def put_pool(self, ws, p): self._put(ws, "POOL", p.id, p)

    def list_memberships(self, ws, pool_id=None):
        return self._query(ws, "MEMBERSHIP", Membership, f"{pool_id}#" if pool_id else None)

    def get_membership(self, ws, pool_id, household_id):
        return self._get(ws, "MEMBERSHIP", f"{pool_id}#{household_id}", Membership)

    def put_membership(self, ws, m):
        self._put(ws, "MEMBERSHIP", f"{m.pool_id}#{m.household_id}", m)

    def list_decisions(self, ws): return self._query(ws, "DECISION", DecisionRequest)
    def get_decision(self, ws, did): return self._get(ws, "DECISION", did, DecisionRequest)
    def put_decision(self, ws, d): self._put(ws, "DECISION", d.id, d)

    def append_activity(self, ws, e): self._put(ws, "ACTIVITY", f"{e.at}#{e.id}", e)

    def list_activity(self, ws, limit=100):
        items = self._query(ws, "ACTIVITY", ActivityEvent)
        return sorted(items, key=lambda e: e.at, reverse=True)[:limit]

    def put_run(self, ws, r): self._put(ws, "RUN", r.id, r)
    def get_run(self, ws, rid): return self._get(ws, "RUN", rid, AgentRun)

    def list_runs(self, ws, limit=25):
        items = self._query(ws, "RUN", AgentRun)
        return sorted(items, key=lambda r: r.started_at, reverse=True)[:limit]

    def reset(self, ws: str) -> None:
        """Delete every item in a workspace. Scoped by partition key — it can never
        reach another workspace, let alone another table (AGENTS.md §3.8)."""
        from boto3.dynamodb.conditions import Key

        for type_name in _TYPES:
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


def build_repository(kind: str, table_name: str, region_name: str) -> Repository:
    if kind == "memory":
        return InMemoryRepository()
    if kind == "dynamodb":
        return DynamoDBRepository(table_name=table_name, region_name=region_name)
    raise ValueError(f"unknown repository kind: {kind!r}")
