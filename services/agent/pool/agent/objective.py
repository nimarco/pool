"""What one coordination run was asked to answer, derived from stored state.

Pool has two genuinely different triggers, and they were the same trigger for most of
this build — which is how a member could declare coffee, press **Run Pool now**, and
watch the coordinator form a whey order for ten other students. Nothing about that run
was dishonest; it answered a *community* question because that was the only question the
system knew how to ask.

    **member** — somebody pressed a button in their own product. The question is
    "can Pool do anything useful with the things I have told it I buy?"

    **community** — the pool-day scan, scheduled or operator-initiated. The question is
    "is there anything in this Community worth coordinating, for anyone?"

One coordinator, one tool surface, one set of deterministic services. The objective is
the only difference, and it sets the run's *objective*, never its *answer*: a member
objective decides which declarations get investigated, and the same evaluator then
decides on its own facts whether any of them is worth acting on. "No worthwhile pool
yet" is a successful outcome of a member-triggered run.

Two properties are load-bearing, and both are why this is built here rather than sent:

**The browser cannot steer it.** A trigger name from a server allowlist is the entire
client input. The subject household, the declarations, the products and the prompt are
all read from the workspace by :func:`for_trigger`, inside the coordinator — so the
local API, the AgentCore runtime and the test suite derive the identical objective from
the identical payload (AGENTS.md §4).

**No personal detail reaches the model.** The objective carries need ids, product ids
and product names. It carries no name, no address, no contact detail and no household
id in the prompt — the model never needs to know *who* asked in order to evaluate what
they declared (AGENTS.md §4, §5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..domain.models import LEFT_PARTICIPATION_STATES
from ..services import coordination as coord
from ..services.context import PoolContext

MEMBER = "member"
COMMUNITY = "community"

#: How many of one member's declarations a single run will take on. A member with
#: fifteen standing needs must not turn one button press into fifteen costed
#: evaluations, so the run takes the most pressing few and the report says plainly that
#: the rest were not investigated (AGENTS.md §3.1).
#:
#: Three, not more, because of the iteration bound rather than taste: one listing,
#: one evaluation each, one pool, one host offer and one closing turn is seven model
#: calls against a cap of eight (``config.AgentBounds``). A fourth would sit exactly
#: on the bound, and a safety net that fires in normal operation is not one.
MAX_MEMBER_NEEDS = 3

#: Triggers that mean "a member pressed a button in their own product". Everything else
#: is a community-wide scan. Stated once, so the API, the runtime entrypoint and the
#: coordinator cannot disagree about which is which.
MEMBER_TRIGGERS = frozenset({"member_scan"})


@dataclass(frozen=True)
class NeedObjective:
    """One standing declaration this run was asked about, and what could serve it."""

    need_id: str
    product_id: str
    product_name: str
    quantity: int
    unit: str
    #: Products a pool could actually buy *and* this member's own substitution rules
    #: authorise — the declared product first, then any permitted substitute Pool holds
    #: a bulk offer for. When neither exists this is just the declared product, so the
    #: run still reaches a deterministic ``no_bulk_offer`` verdict rather than skipping
    #: it and leaving the declaration unexplained.
    target_product_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "need_id": self.need_id,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "quantity": self.quantity,
            "unit": self.unit,
            "target_product_ids": list(self.target_product_ids),
        }


@dataclass(frozen=True)
class RunObjective:
    """The bounded question one run is answering."""

    kind: str = COMMUNITY
    household_id: str = ""
    needs: tuple[NeedObjective, ...] = ()
    #: Declarations this member holds that the run did *not* take on, because the
    #: per-run cap was reached. Recorded so the report can say so instead of inventing a
    #: reason for their absence.
    deferred_need_ids: tuple[str, ...] = ()
    #: Declarations already inside a live pool. Not investigated, and not a refusal.
    served_need_ids: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_member(self) -> bool:
        return self.kind == MEMBER

    @property
    def product_ids(self) -> tuple[str, ...]:
        seen: list[str] = []
        for need in self.needs:
            for pid in need.target_product_ids:
                if pid not in seen:
                    seen.append(pid)
        return tuple(seen)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "household_id": self.household_id,
            "needs": [n.to_dict() for n in self.needs],
            "deferred_need_ids": list(self.deferred_need_ids),
            "served_need_ids": list(self.served_need_ids),
        }


def _served_need_ids(ctx: PoolContext, household_id: str) -> set[str]:
    """Declarations already inside a live pool. Their answer is the pool, not a run."""
    out: set[str] = set()
    for pool in ctx.repo.list_pools(ctx.ws):
        membership = ctx.repo.get_membership(ctx.ws, pool.id, household_id)
        if membership is not None and membership.state not in LEFT_PARTICIPATION_STATES:
            out.add(membership.need_id)
    return out


def build_member_objective(
    ctx: PoolContext, community_id: str, household_id: str
) -> RunObjective:
    """The bounded question a member's own **Run Pool now** asks.

    Their active declarations in this Community that no live pool is already serving,
    soonest-needed first, capped at :data:`MAX_MEMBER_NEEDS`. Read-only.
    """
    if not household_id:
        return RunObjective(kind=MEMBER)
    served = _served_need_ids(ctx, household_id)
    mine = [
        n
        for n in ctx.repo.list_needs(ctx.ws)
        if n.household_id == household_id and n.active and n.community_id == community_id
    ]
    # Soonest needed first. The tie-break is the product, not the need id: ids are
    # random, so two declarations due on the same day would otherwise be investigated
    # in a different order on every run — and which one a run acts on would move with
    # them.
    mine.sort(key=lambda n: (n.expected_next_need_date, n.product_id, n.id))
    unserved = [n for n in mine if n.id not in served]

    objectives: list[NeedObjective] = []
    for need in unserved[:MAX_MEMBER_NEEDS]:
        product = ctx.repo.get_product(ctx.ws, need.product_id)
        targets = tuple(coord.sourceable_targets_for_need(ctx, need)) or (need.product_id,)
        objectives.append(
            NeedObjective(
                need_id=need.id,
                product_id=need.product_id,
                product_name=product.name if product else need.product_id,
                quantity=need.quantity,
                unit=product.unit if product else "unit",
                target_product_ids=targets,
            )
        )
    return RunObjective(
        kind=MEMBER,
        household_id=household_id,
        needs=tuple(objectives),
        deferred_need_ids=tuple(n.id for n in unserved[MAX_MEMBER_NEEDS:]),
        served_need_ids=tuple(n.id for n in mine if n.id in served),
    )


def for_trigger(ctx: PoolContext, community_id: str, trigger: str) -> RunObjective:
    """Derive this run's objective from its trigger and the workspace.

    The subject of a member-triggered run is resolved here, from stored state, and never
    supplied by a caller. This build has no account authentication
    (``docs/PILOT_READINESS.md``), so "the member" is the one household a real person
    uses — the same server-owned resolution ``/api/onboarding/payment-method`` relies on.
    A caller therefore cannot point a run at somebody else's declarations, because there
    is no field in which to name them.
    """
    if trigger not in MEMBER_TRIGGERS:
        return RunObjective(kind=COMMUNITY)
    from ..services import onboarding

    member = onboarding.consumer_household(ctx)
    return build_member_objective(ctx, community_id, member.id if member else "")


# ------------------------------------------------------------------- prompts


COMMUNITY_PROMPT = (
    "Run a background scan of this community. Find the most worthwhile bulk "
    "buying opportunity among unserved recurring needs and form a candidate "
    "pool if one is genuinely worth forming."
)

NO_DECLARATIONS_PROMPT = (
    "A member asked Pool to look at what they buy, but they hold no standing "
    "declaration that is not already being coordinated. There is nothing to "
    "investigate: call record_no_action saying exactly that, and stop."
)


#: How much of a product name may reach the run instruction. A catalogue name is short;
#: this bounds the one field on this path a *member* authors.
MAX_PROMPT_PRODUCT_NAME = 60


def _prompt_safe(name: str) -> str:
    """A product name, reduced to something that can only ever read as a product name.

    Almost every name here comes from the bundled catalogue. One does not:
    ``/api/products/custom`` lets a member record something Pool has never heard of, and
    that string would otherwise be interpolated straight into the run instruction — which
    is the one place this build promises the browser cannot write (§4). Newlines are the
    part that matters: a name spanning lines can be shaped like a new instruction, and a
    name that cannot contain one cannot be.

    Not a security boundary on its own, and not treated as one. The model reaches the
    world only through typed tools bound to this caller's own workspace, no tool takes a
    workspace argument, and the run is bounded either way. This keeps the *claim* true
    rather than nearly true.
    """
    flattened = " ".join(str(name).split())
    return flattened[:MAX_PROMPT_PRODUCT_NAME] or "an unnamed product"


def prompt_for(objective: RunObjective) -> str:
    """The run instruction, built by the server from the objective.

    Names products, never people. The member's own identity is not a fact the model
    needs in order to cost a bulk order, so it is not in here (AGENTS.md §4).
    """
    if not objective.is_member:
        return COMMUNITY_PROMPT
    if not objective.needs:
        return NO_DECLARATIONS_PROMPT
    listed = "; ".join(
        f"{n.quantity} × {_prompt_safe(n.product_name)}" for n in objective.needs
    )
    return (
        "A member of this community has asked Pool to look at what they buy. They "
        f"have declared: {listed}. Investigate those declarations and nothing else.\n"
        "Call list_latent_demand first — the opportunities marked for_member are "
        "theirs, already in priority order, and each names the declaration behind it. "
        "Call evaluate_pool_economics on every one of them before you act, so each "
        "declaration gets a real verdict rather than being skipped.\n"
        "Then form at most one candidate pool, for the best genuinely viable one. If "
        "none of them is worth forming, that is the correct answer: call "
        "record_no_action and say why. Do not investigate products this member has "
        "not declared."
    )
