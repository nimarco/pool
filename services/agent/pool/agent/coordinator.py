"""PoolCoordinator — the single Strands agent that runs Pool.

One agent, not a swarm. The deterministic domains (pricing, matching, routing, policy)
are tools, not agents, because they need to be *correct*, not *creative*. The agent's
contribution is adaptive orchestration: which opportunity to investigate, whether the
result is worth acting on, when a situation needs a human, and when to stop.

The run is bounded by :class:`~pool.agent.bounds.BoundedRun` and always terminates in a
recorded state — success, no-action, loop fault, or error. There is no path where it
simply spins (AGENTS.md §3.1).
"""

from __future__ import annotations

import logging
from typing import Any

from strands import Agent

from ..adapters.payments import PaymentProvider, build_payment_provider
from ..adapters.purchase import PurchaseExecutor, build_purchase_executor
from ..adapters.repository import Repository
from ..adapters.routing import RoutingService, build_routing
from ..adapters.sourcing import SourcingProvider, SyntheticCatalogProvider
from ..config import Settings, get_settings
from ..domain.models import ActivityEvent, AgentRun, RunOutcome, iso, new_id, utcnow
from ..services.context import PoolContext
from .bounds import BoundedRun, BoundExceeded, RunTelemetry
from .evidence import build as build_evidence
from .objective import for_trigger, prompt_for
from .tools import ToolContext, build_tools

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are Pool's coordinator for one local community.

Members have told Pool what they routinely buy. Nobody has created a buying group. \
Your job is to notice when several of them want the same thing, decide whether a bulk \
purchase is genuinely worth it, move a viable pool through its lifecycle, and stop \
cleanly when nothing is worth doing.

Every run is asked one of two questions, and the instruction says which. A community \
scan may investigate anything in the community. A member-triggered run is about one \
member's own standing declarations: investigate those, give each of them a verdict, and \
do not go looking for a better opportunity somebody else would benefit from.

The lifecycle, in order:
latent demand -> candidate pool -> host recruiting -> host accepts -> supplier quote \
refreshed -> exact landed price -> buyer authorisation -> funded -> lock -> purchase.

How to work:
- Call tools to learn facts. Never state a price, quantity, saving, distance, \
threshold, or eligibility that did not come from a tool result — the tools compute \
those, you do not.
- Investigate the most promising opportunity first. Not every product is worth pooling; \
concluding "nothing worthwhile" and calling record_no_action is a good outcome.
- Form at most one pool per run. Members should hear from Pool rarely, and only when \
there is a real decision for them.
- Never assume a member will accept something, and never assume a host will take a job. \
The tools apply each person's own rules and return the verdict.
- A pool cannot be priced exactly until a host has accepted, and cannot lock until the \
viability check passes. Do not try to skip a step; the tools will refuse.
- When you are done, stop. Do not repeat a tool call whose inputs have not changed."""


class PoolCoordinator:
    """Builds and runs the bounded Strands agent."""

    def __init__(
        self,
        repo: Repository,
        settings: Settings | None = None,
        routing: RoutingService | None = None,
        model: Any | None = None,
        payments: PaymentProvider | None = None,
        purchaser: PurchaseExecutor | None = None,
        sourcing: SourcingProvider | None = None,
    ) -> None:
        self.repo = repo
        self.settings = settings or get_settings()
        self.routing = routing or build_routing(
            self.settings.routing_provider,
            self.settings.aws_region,
            self.settings.max_route_matrix_cells,
        )
        self.payments = payments or build_payment_provider(
            self.settings.payment_provider, self.settings.stripe_api_key
        )
        self.purchaser = purchaser or build_purchase_executor(self.settings.purchase_executor)
        self.sourcing = sourcing or SyntheticCatalogProvider()
        self._model_override = model
        #: The tool context of the most recent run, carrying the complete authoritative
        #: results behind the compact projections the model was shown.
        self.last_tool_context: ToolContext | None = None

    # -- model -------------------------------------------------------------

    def _boto_session(self):
        """A boto3 session for the configured profile, or None for the default chain.

        Local development authenticates with a named profile; Lambda and AgentCore
        authenticate with an execution role and must use the default chain. Returning
        ``None`` when no profile is set keeps both true without a second code path.
        """
        if not self.settings.aws_profile:
            return None
        import boto3

        return boto3.Session(
            profile_name=self.settings.aws_profile, region_name=self.settings.aws_region
        )

    def _build_model(self) -> tuple[Any, str, str]:
        """Return ``(model, model_id, provider)``."""
        if self._model_override is not None:
            provider = getattr(self._model_override, "provider_name", "injected")
            config = {}
            if hasattr(self._model_override, "get_config"):
                try:
                    config = self._model_override.get_config() or {}
                except Exception:  # noqa: BLE001
                    config = {}
            return self._model_override, str(config.get("model_id", provider)), provider

        if self.settings.model_provider == "offline":
            from .offline_model import DeterministicPlannerModel

            model = DeterministicPlannerModel()
            return model, "offline-deterministic-planner", "offline"

        if self.settings.model_provider == "bedrock":
            from strands.models import BedrockModel

            # `BedrockModel` takes its configuration as **kwargs, not as a `model_config`
            # dict. Passing a dict silently lands in the config under a key nothing reads,
            # leaving `model_id` unset — so Strands falls back to *its* default model and
            # BEDROCK_MODEL_ID is quietly ignored. Found on the first real invocation;
            # there is no way to catch this offline, because the offline path never
            # constructs a BedrockModel.
            # `BedrockModel` rejects `region_name` and `boto_session` together, because a
            # session already carries a region. Pass whichever one applies.
            session = self._boto_session()
            location = (
                {"boto_session": session}
                if session is not None
                else {"region_name": self.settings.aws_region}
            )
            model = BedrockModel(
                model_id=self.settings.bedrock_model_id,
                max_tokens=self.settings.model_max_tokens,
                **location,
            )
            return model, self.settings.bedrock_model_id, "bedrock"

        raise ValueError(f"unknown model provider: {self.settings.model_provider!r}")

    # -- run ---------------------------------------------------------------

    def _record_evidence(self, ws: str, run_id: str, ctx: ToolContext, objective) -> None:
        """Persist what this run's deterministic evaluations established.

        Never allowed to fail the run: the coordination already happened and is already
        recorded, and losing the explanation is strictly better than losing the pool.
        The failure is logged rather than swallowed silently.
        """
        try:
            sites = [
                s
                for s in self.repo.list_sites(ws)
                if s.is_public and s.community_id == ctx.community_id
            ]
            for evaluation in build_evidence(
                run_id=run_id,
                community_id=ctx.community_id,
                full_results=ctx.full_results,
                objective=objective,
                pool_ids_by_product=_pool_ids_by_product(
                    self.repo, ws, ctx.created_pool_ids + ctx.advanced_pool_ids
                ),
                sites_considered=len(sites),
            ):
                self.repo.put_run_evaluation(ws, evaluation)
        except Exception:  # noqa: BLE001 - explanation is not worth failing a run over
            logger.exception("run %s: could not record evaluation evidence", run_id)

    def run(
        self,
        ws: str,
        trigger: str = "manual",
        instruction: str | None = None,
        community_id: str = "",
    ) -> AgentRun:
        """Execute one bounded coordination run and return its record.

        The same method serves the EventBridge schedule, the member's own **Run Pool
        now**, the AgentCore runtime, and the tests. There is no separate demo code path
        (AGENTS.md §8).

        ``trigger`` is the only discriminator, and the objective it implies is derived
        *here* from stored state (``agent/objective.py``) rather than supplied by the
        caller — so a browser, a Lambda and the deployed runtime all send the same tiny
        payload and get the same semantics.
        """
        model, model_id, provider = self._build_model()
        run_id = new_id("run")
        telemetry = RunTelemetry()
        bounded = BoundedRun(self.settings.bounds, telemetry)

        if not community_id:
            communities = self.repo.list_communities(ws)
            community_id = communities[0].id if communities else ""

        pool_ctx = PoolContext(
            repo=self.repo,
            ws=ws,
            routing=self.routing,
            payments=self.payments,
            purchaser=self.purchaser,
            sourcing=self.sourcing,
            run_id=run_id,
        )
        objective = for_trigger(pool_ctx, community_id, trigger)
        ctx = ToolContext(
            pool=pool_ctx,
            community_id=community_id,
            objective=objective,
        )
        # The model sees compact projections of the larger tool results; the complete
        # authoritative results stay on the context, reachable after the run for the
        # operator UI, auditing, and tests (AGENTS.md §6, §9).
        self.last_tool_context = ctx
        tools = build_tools(ctx)

        record = AgentRun(
            id=run_id,
            trigger=trigger,
            model_id=model_id,
            model_provider=provider,
            started_at=iso(utcnow()),
        )

        prompt = instruction or prompt_for(objective)

        try:
            agent = Agent(
                model=model,
                tools=tools,
                system_prompt=SYSTEM_PROMPT,
                hooks=[bounded],
                callback_handler=None,  # no console streaming; we record structured events
            )
            agent(prompt)
            record.outcome = ctx.outcome
            record.termination_reason = telemetry.termination_reason or "completed"
        except Exception as exc:  # noqa: BLE001 - classified and recorded, never swallowed
            # Strands wraps an exception raised inside a hook in EventLoopException, so
            # a bound never arrives as BoundExceeded at this level. Unwrap the chain
            # before deciding whether this was our safety net or a genuine failure —
            # misclassifying a fired bound as a crash would hide the thing we most
            # need to see.
            bound = _find_bound_exceeded(exc)
            if bound is not None:
                logger.warning("run %s hit bound %s: %s", run_id, bound.bound, bound.detail)
                record.outcome = RunOutcome.LOOP_FAULT
                record.termination_reason = f"bound:{bound.bound}"
                record.notes.append(bound.detail)
            else:
                logger.exception("run %s failed", run_id)
                record.outcome = RunOutcome.ERROR
                record.termination_reason = "error"
                record.notes.append(f"{type(exc).__name__}: {exc}")

        record.ended_at = iso(utcnow())
        record.iterations = telemetry.iterations
        record.tool_calls = telemetry.tool_calls
        record.input_tokens = telemetry.input_tokens
        record.output_tokens = telemetry.output_tokens
        record.hitl_decisions_created = ctx.decisions_created
        record.objective_kind = objective.kind
        record.objective_household_id = objective.household_id
        record.objective_need_ids = [n.need_id for n in objective.needs]
        record.deferred_need_ids = list(objective.deferred_need_ids)
        record.served_need_ids = list(objective.served_need_ids)
        if ctx.no_action_reason:
            record.notes.append(ctx.no_action_reason)

        self.repo.put_run(ws, record)
        # After the try/except on purpose: a run stopped by a safety bound still did
        # real work before it stopped, and what it established is exactly what somebody
        # will want to read afterwards. Written here rather than inside the tools so
        # `evaluate_pool_economics` stays provably side-effect-free — the member view
        # calls the same evaluator, and that view must change no row.
        self._record_evidence(ws, record.id, ctx, objective)
        self.repo.append_activity(
            ws,
            ActivityEvent(
                id=new_id("evt"),
                kind="agent_run",
                summary=_run_summary(record, ctx),
                facts={
                    "outcome": record.outcome.value,
                    "trigger": trigger,
                    "objective": objective.kind,
                    "objective_products": list(objective.product_ids),
                    "iterations": record.iterations,
                    "tool_calls": len(record.tool_calls),
                    "tools_used": [t.name for t in record.tool_calls],
                    "termination_reason": record.termination_reason,
                    "model_provider": provider,
                    "model_id": model_id,
                    "duration_ms": record.duration_ms,
                    "input_tokens": record.input_tokens,
                    "output_tokens": record.output_tokens,
                },
                run_id=run_id,
            ),
        )
        return record


def _pool_ids_by_product(repo, ws: str, pool_ids: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for pool_id in pool_ids:
        pool = repo.get_pool(ws, pool_id)
        if pool is not None:
            out.setdefault(pool.product_id, pool.id)
    return out


def _find_bound_exceeded(exc: BaseException) -> BoundExceeded | None:
    """Walk the exception chain looking for one of our bounds.

    Strands raises ``EventLoopException(original, ...)`` around anything a hook throws,
    so the bound is reachable via ``__cause__``/``__context__`` rather than directly.
    Bounded to a fixed depth so a cyclic chain cannot spin here.
    """
    seen: set[int] = set()
    current: BaseException | None = exc
    for _ in range(12):
        if current is None or id(current) in seen:
            return None
        if isinstance(current, BoundExceeded):
            return current
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return None


def _run_summary(record: AgentRun, ctx: ToolContext) -> str:
    if record.outcome == RunOutcome.POOL_CREATED:
        return (
            f"Pool scanned the community and formed {len(ctx.created_pool_ids)} "
            "candidate pool nobody had to organise"
        )
    if record.outcome == RunOutcome.POOL_RECOVERED:
        return f"Pool repaired {len(ctx.recovered_pool_ids)} pool after losing funded demand"
    if record.outcome == RunOutcome.POOL_ADVANCED:
        return f"Pool moved {len(ctx.advanced_pool_ids)} pool forward in its lifecycle"
    if record.outcome == RunOutcome.LOOP_FAULT:
        return f"Run stopped by a safety bound ({record.termination_reason})"
    if record.outcome == RunOutcome.ERROR:
        return "Run failed with an error"
    return "Pool ran a background scan and found nothing worth acting on"
