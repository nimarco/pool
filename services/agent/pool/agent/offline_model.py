"""An offline, deterministic stand-in for the Bedrock model.

**What this replaces:** the LLM, and only the LLM.

Everything else in the run is the real thing — the real Strands event loop, the real
tool implementations, the real deterministic domain math, the real state machine, the
real Smart Join policy engine, the real payment provider, and the real human-in-the-loop
boundary. The planner below chooses the next tool from structured tool results exactly
where the model would, using the same tool schemas.

**Why it exists:** the whole test suite and the local demo can then exercise the true
orchestration path at zero token cost (AGENTS.md §3.3, §3.6). Cheap tests are tests
that actually get run, and a demo that cannot be rehearsed for free will not be
rehearsed.

**What it is not:** it is not a substitute for evidence that Bedrock works, and it must
never be presented as one. Any run using it is labelled ``model_provider="offline"`` in
the run record and in the UI, so a demo can always show which runs were model-driven.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterable
from typing import Any

from strands.models import Model

MAX_PRODUCTS_TO_INVESTIGATE = 4

#: How many of a member's own objectives one member-triggered run evaluates. Matches
#: ``agent.objective.MAX_MEMBER_NEEDS`` and is bounded by the same iteration cap.
MAX_MEMBER_OBJECTIVES = 3

#: How many times one run may re-read the work queue. Two is enough to act, observe the
#: consequence, and act once more; more than that is polling.
MAX_LISTINGS = 2

#: Fallback when a listing has not yet reported the remaining budget. The tools
#: enforce the real bound; this only stops the planner asking for an evaluation it
#: already knows will be refused.
MAX_STRATEGY_EVALUATIONS = 3

#: Fallback when a listing has not reported the plan cap. The tools enforce the real
#: bound; this only stops the planner proposing one it knows would be refused.
MAX_CLARIFICATION_QUESTIONS = 3


def _tool_event(name: str, payload: dict[str, Any]) -> list[dict]:
    """Build the Bedrock-shaped stream events for a single tool call."""
    tool_use_id = f"tooluse_{uuid.uuid4().hex[:16]}"
    return [
        {"messageStart": {"role": "assistant"}},
        {"contentBlockStart": {"start": {"toolUse": {"toolUseId": tool_use_id, "name": name}}}},
        {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(payload)}}}},
        {"contentBlockStop": {}},
        {"messageStop": {"stopReason": "tool_use"}},
    ]


def _text_event(text: str) -> list[dict]:
    return [
        {"messageStart": {"role": "assistant"}},
        {"contentBlockDelta": {"delta": {"text": text}}},
        {"contentBlockStop": {}},
        {"messageStop": {"stopReason": "end_turn"}},
    ]


def _metadata_event() -> dict:
    # Explicitly zero: no tokens were purchased to produce this turn.
    return {
        "metadata": {
            "usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0},
            "metrics": {"latencyMs": 0},
        }
    }


class TranscriptView:
    """Reads the conversation the way the planner needs it: tools called, results seen."""

    def __init__(self, messages: list[dict]) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.results: list[dict] = []
        self.user_text = ""

        for message in messages:
            role = message.get("role")
            for block in message.get("content", []) or []:
                if not isinstance(block, dict):
                    continue
                if role == "user" and "text" in block and not self.user_text:
                    self.user_text = str(block["text"])
                if "toolUse" in block:
                    tu = block["toolUse"]
                    self.calls.append((str(tu.get("name", "")), tu.get("input") or {}))
                if "toolResult" in block:
                    parsed = self._parse_result(block["toolResult"])
                    if parsed is not None:
                        self.results.append(parsed)

    @staticmethod
    def _parse_result(tool_result: dict) -> dict | None:
        for block in tool_result.get("content", []) or []:
            if isinstance(block, dict) and "text" in block:
                try:
                    return json.loads(block["text"])
                except (TypeError, ValueError):
                    return {"_raw": block["text"]}
        return None

    def called(self, name: str) -> bool:
        return any(c[0] == name for c in self.calls)

    def count(self, name: str) -> int:
        return sum(1 for c in self.calls if c[0] == name)

    def last_result_of(self, name: str) -> dict | None:
        """The result of the most recent call to ``name`` (results run parallel to calls)."""
        for i in range(len(self.calls) - 1, -1, -1):
            if self.calls[i][0] == name and i < len(self.results):
                return self.results[i]
        return None

    def results_of(self, name: str) -> list[dict]:
        out = []
        for i, (call_name, _) in enumerate(self.calls):
            if call_name == name and i < len(self.results):
                out.append(self.results[i])
        return out

    def args_of(self, name: str) -> list[dict]:
        return [args for call_name, args in self.calls if call_name == name]


class DeterministicPlannerModel(Model):
    """Chooses the next tool from structured state. No network, no tokens, no cost."""

    provider_name = "offline"

    def __init__(self) -> None:
        self._config: dict[str, Any] = {"model_id": "offline-deterministic-planner"}
        #: Which tools this run was given. Set per turn by :meth:`stream`.
        self._available_tools: set[str] = set()

    # -- Model interface ---------------------------------------------------

    def get_config(self) -> dict[str, Any]:
        return dict(self._config)

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        raise NotImplementedError("the offline planner does not produce structured output")

    async def stream(
        self,
        messages: list[dict],
        tool_specs: list[dict] | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[dict]:
        view = TranscriptView(messages)
        # Recorded on the instance rather than passed down, because ``_decide(view)`` is
        # the extension point three test doubles already override, and widening a seam
        # other people build on to carry one more argument is a worse trade than one
        # attribute. A planner is constructed per run and its turns are sequential, so
        # there is nothing here for a second run to observe.
        self._available_tools = {
            str((spec or {}).get("name", "")) for spec in (tool_specs or []) if spec
        }
        for event in self._decide(view):
            yield event
        yield _metadata_event()

    # -- planning ----------------------------------------------------------

    def _decide(self, view: TranscriptView) -> list[dict]:
        # Which surface this run was given, not which words its instruction contains.
        # The strategy tools are offered only for a declaration event
        # (``objective.searches_strategies``), so their presence *is* the branch — and a
        # planner that sniffed the prompt for "coffee" would be a fixture-specific rule
        # pretending to be a policy.
        available = getattr(self, "_available_tools", frozenset())
        if "list_preference_question_candidates" in available:
            return self._plan_clarification(view)
        if "list_cohort_strategies" in available:
            return self._plan_strategy_search(view)
        text = view.user_text.lower()
        if "recover" in text or "withdrew" in text or "failed" in text:
            return self._plan_attention(view)
        if "advance" in text or "host" in text or "lock" in text:
            return self._plan_attention(view)
        return self._plan_scan(view)

    # -- targeted questions ------------------------------------------------

    def _plan_clarification(self, view: TranscriptView) -> list[dict]:
        """Choose which approved questions are worth asking, from the counts alone.

        **Not evidence that a model can do this.** A deterministic policy over the same
        projection, so the tool contracts, the validation and the bounds are exercised at
        zero token cost. Whether Bedrock chooses well is a question only a Bedrock run
        answers.

        The policy is generic and contains no product id, no attribute name and no
        fixture knowledge. It asks about a dimension only when the answer would reach a
        *different* world — when keeping the product's own value excludes something Pool
        could otherwise source — and orders by how much it excludes, largest first,
        because that is the question whose answer changes most. A dimension the sourceable
        products do not vary on is dropped: the member's answer could not change their
        cohort, so asking is a question bought for nothing.
        """
        if view.called("record_no_action"):
            return _text_event("Nothing further to ask about this product.")

        if not view.called("list_preference_question_candidates"):
            return _tool_event("list_preference_question_candidates", {})

        listing = view.last_result_of("list_preference_question_candidates") or {}
        questions = listing.get("questions", []) or []
        if not questions:
            return _tool_event(
                "record_no_action",
                {"reason": "this product has no confirmed facts that can be clarified"},
            )

        if view.called("set_preference_question_plan"):
            planned = view.last_result_of("set_preference_question_plan") or {}
            if planned.get("planned"):
                return _text_event(
                    f"Asked about {len(planned.get('question_ids', []))} of "
                    f"{len(questions)} available dimensions."
                )
            return _tool_event(
                "record_no_action",
                {"reason": str(planned.get("reason", "the plan was refused"))[:200]},
            )

        def swing(question: dict) -> int:
            answers = question.get("answers") or {}
            keep = (answers.get("keep") or {}).get("sourceable_products", 0)
            widest = max(
                ((a or {}).get("sourceable_products", 0) for a in answers.values()),
                default=0,
            )
            return max(0, widest - keep)

        worth_asking = [
            q for q in questions if q.get("varies_among_sourceable") and swing(q) > 0
        ]
        # Stable: by how much the answer changes what is reachable, then by the order the
        # listing gave, which is the schema's and is itself deterministic.
        order = {q.get("question_id"): i for i, q in enumerate(questions)}
        worth_asking.sort(key=lambda q: (-swing(q), order.get(q.get("question_id"), 0)))
        cap = int(listing.get("max_questions_in_a_plan", MAX_CLARIFICATION_QUESTIONS))

        if not worth_asking:
            return _tool_event(
                "record_no_action",
                {
                    "reason": "every answer here reaches the same products, so none of "
                    "them would change what Pool can do"
                },
            )
        return _tool_event(
            "set_preference_question_plan",
            {"question_ids": [q["question_id"] for q in worth_asking[:cap]]},
        )

    # -- strategy search ---------------------------------------------------

    def _plan_strategy_search(self, view: TranscriptView) -> list[dict]:
        """Investigate options one at a time, and adapt to what each answer says.

        **This is not evidence that a model can do this.** It is a deterministic policy
        over the same projections a model would read, so the tool contracts, the bounds
        and the authoritative evaluators are exercised at zero token cost. What it proves
        is that the *architecture* supports investigate → inspect → adapt; whether Bedrock
        chooses well is a question only a Bedrock run can answer.

        The policy contains no product id, no brand and no fixture knowledge. It takes
        the listing's order, evaluates the first option it has not tried, and on a refusal
        moves to the next — stopping the moment one is confirmed viable, because the
        budget is smaller than the option set and sweeping it would defeat the point.
        """
        if view.called("record_no_action"):
            return _text_event("Nothing worth acting on for this declaration.")

        if not view.called("list_cohort_strategies"):
            return _tool_event("list_cohort_strategies", {})

        listing = view.last_result_of("list_cohort_strategies") or {}
        options = listing.get("strategies", []) or []
        if not options:
            return _tool_event(
                "record_no_action",
                {"reason": "no supplier and no compatible demand could serve this declaration"},
            )

        # A viable answer already in hand: form it, once.
        evaluations = view.results_of("evaluate_cohort_strategy")
        viable = next((e for e in evaluations if e.get("viable")), None)
        if viable is not None:
            if not view.called("create_candidate_pool_from_strategy"):
                return _tool_event(
                    "create_candidate_pool_from_strategy",
                    {
                        "strategy_id": viable["strategy_id"],
                        "evaluation_id": viable["evaluation_id"],
                    },
                )
            created = view.last_result_of("create_candidate_pool_from_strategy") or {}
            if created.get("created"):
                return _text_event(
                    "Formed a candidate pool from the option the evaluator confirmed."
                )
            return _tool_event(
                "record_no_action",
                {
                    "reason": (
                        "the verified option could not be formed: "
                        f"{created.get('refusal_reason', 'refused')}"
                    )[:400]
                },
            )

        # Otherwise investigate the next option in the listing's own order.
        tried = {a.get("strategy_id") for a in view.args_of("evaluate_cohort_strategy")}
        remaining = (
            evaluations[-1].get("evaluations_remaining") if evaluations else MAX_STRATEGY_EVALUATIONS
        )
        if remaining is None:
            remaining = MAX_STRATEGY_EVALUATIONS
        if remaining > 0:
            for option in options:
                if option.get("strategy_id") in tried:
                    continue
                return _tool_event(
                    "evaluate_cohort_strategy", {"strategy_id": option["strategy_id"]}
                )

        refusals = "; ".join(
            f"{e.get('product', 'option')}: {e.get('blocker_code', 'refused')}"
            for e in evaluations
            if not e.get("viable")
        )
        return _tool_event(
            "record_no_action",
            {
                "reason": (
                    f"investigated {len(evaluations)} of {len(options)} option(s); "
                    f"none was worth forming. {refusals}"
                )[:400]
            },
        )

    # -- discovery ---------------------------------------------------------

    def _plan_scan(self, view: TranscriptView) -> list[dict]:
        """Find the overlap worth acting on, and form at most one candidate pool.

        Two shapes, chosen by what the listing says this run was asked (``objective``):

        * **member** — every one of that member's own objectives is evaluated before
          anything is formed, because the run owes each of their declarations a real
          verdict. Acting on the first viable one and stopping would leave the rest
          indistinguishable from "not worth it".
        * **community** — the scheduled scan owes only the best available action, so it
          acts as soon as it finds something viable rather than costing the whole queue.
        """
        # record_no_action is terminal. Without this the planner re-issues it forever;
        # the run-level bound caught exactly that during development, which is what the
        # bound is for — but a planner that needs the safety net every run is a bug.
        if view.called("record_no_action"):
            return _text_event("Nothing worth acting on this cycle.")

        if not view.called("list_latent_demand"):
            return _tool_event("list_latent_demand", {})

        demand = view.last_result_of("list_latent_demand") or {}
        opportunities = demand.get("opportunities", [])
        member_run = (demand.get("objective") or {}).get("kind") == "member"
        if member_run:
            queue = [o for o in opportunities if o.get("for_member")][:MAX_MEMBER_OBJECTIVES]
        else:
            queue = opportunities[:MAX_PRODUCTS_TO_INVESTIGATE]

        evaluated_products = {a.get("product_id") for a in view.args_of("evaluate_pool_economics")}
        assessments = view.results_of("evaluate_pool_economics")

        # A community scan acts on the first viable assessment it sees.
        if not member_run and assessments:
            latest = assessments[-1]
            if latest.get("viable") and not view.called("create_candidate_pool"):
                return _tool_event(
                    "create_candidate_pool",
                    {
                        "product_id": latest["product_id"],
                        "pickup_site_id": latest["pickup_site_id"],
                    },
                )

        if view.called("create_candidate_pool"):
            created = view.last_result_of("create_candidate_pool") or {}
            if not created.get("created"):
                return _text_event("An equivalent pool already existed; no duplicate was created.")
            pool_id = created.get("pool_id", "")
            # A candidate pool with no fulfilment is not yet a transaction, so the
            # natural next step is recruiting — but only once.
            if pool_id and not view.called("request_host_acceptance"):
                return _tool_event("request_host_acceptance", {"pool_id": pool_id})
            return _text_event(
                f"Formed a candidate pool for {created.get('product_name', 'a product')} "
                f"with {created.get('member_count', 0)} members and offered the "
                "fulfilment job to the best-ranked host."
            )

        # Otherwise investigate the next unexplored product in the queue.
        for opp in queue:
            if opp.get("product_id") in evaluated_products:
                continue
            if not opp.get("suggested_pickup_site_id"):
                continue
            return _tool_event(
                "evaluate_pool_economics",
                {
                    "product_id": opp["product_id"],
                    "pickup_site_id": opp["suggested_pickup_site_id"],
                    "include_future_demand": True,
                },
            )

        # Everything asked about has been costed. A member run acts now, on the first
        # viable objective in the member's own priority order — soonest needed first.
        # The order is the listing's; no arithmetic happens here, because a planner that
        # compares prices is a planner deciding money (AGENTS.md §5).
        if member_run:
            by_product = {a.get("product_id"): a for a in assessments}
            ordered = [
                found
                for opp in queue
                if (found := by_product.get(opp.get("product_id"))) and found.get("viable")
            ]
            # An order this member is actually in comes first. Both are legitimate — case
            # fitting can genuinely leave somebody out — but forming the one they are in
            # is the better answer to their own button, and only one pool forms per run.
            chosen = next(
                (a for a in ordered if a.get("includes_member_declaration")),
                ordered[0] if ordered else None,
            )
            if chosen is not None:
                return _tool_event(
                    "create_candidate_pool",
                    {
                        "product_id": chosen["product_id"],
                        "pickup_site_id": chosen["pickup_site_id"],
                    },
                )

        reasons = [a.get("reason", "") for a in assessments if not a.get("viable")]
        if not queue and member_run:
            return _tool_event(
                "record_no_action",
                {"reason": "this member holds no standing declaration to investigate"},
            )
        return _tool_event(
            "record_no_action",
            {
                "reason": (
                    "; ".join(r for r in reasons if r)[:400]
                    or "no product had compatible demand worth pooling"
                )
            },
        )

    # -- advancing and repairing ------------------------------------------

    def _plan_attention(self, view: TranscriptView) -> list[dict]:
        """Move every blocked pool one legitimate step forward.

        The order mirrors the canonical lifecycle: get a host, then price exactly, then
        recover funding, then lock, then purchase. Each pool is attempted once per step
        per run, which is what keeps the run bounded.
        """
        if view.called("record_no_action"):
            return _text_event("No pool needed attention.")

        mutating = (
            "request_host_acceptance",
            "issue_final_offer",
            "recover_pool",
            "lock_pool",
            "execute_purchase",
        )
        listings = view.count("list_pools_needing_attention")
        actions = sum(view.count(name) for name in mutating)

        # Re-read the queue after acting: a recovered pool becomes lockable, and
        # deciding from a stale listing would miss that. Capped at MAX_LISTINGS so the
        # alternation cannot become a poll — the duplicate-call bound would catch it
        # anyway, but a planner that needs the safety net every run is a bug.
        if listings == 0 or (actions >= listings and listings < MAX_LISTINGS):
            return _tool_event("list_pools_needing_attention", {})

        listing = view.last_result_of("list_pools_needing_attention") or {}
        pools = listing.get("pools", [])
        if not pools:
            return _tool_event(
                "record_no_action", {"reason": "no pool is currently blocked"}
            )

        tried = {name: {a.get("pool_id") for a in view.args_of(name)} for name in mutating}

        # 1. Anything ready to lock, locks. That is the highest-value action available.
        for pool in pools:
            if pool.get("ready_to_lock") and pool["pool_id"] not in tried["lock_pool"]:
                return _tool_event("lock_pool", {"pool_id": pool["pool_id"]})

        # 2. A pool that has actually lost demand needs replacements before anything
        #    else. Buyers who simply have not answered yet are not a shortfall.
        for pool in pools:
            pid = pool["pool_id"]
            if pid in tried["recover_pool"]:
                continue
            if pool.get("lost_units", 0) > 0:
                return _tool_event("recover_pool", {"pool_id": pid})

        # 3. A pool with a host but no final offer needs exact economics.
        for pool in pools:
            pid = pool["pool_id"]
            if pid in tried["issue_final_offer"]:
                continue
            if pool.get("has_host") and not pool.get("has_final_offer"):
                return _tool_event("issue_final_offer", {"pool_id": pid})

        # 4. A pool with no host needs one.
        for pool in pools:
            pid = pool["pool_id"]
            if pid in tried["request_host_acceptance"]:
                continue
            if not pool.get("has_host"):
                return _tool_event("request_host_acceptance", {"pool_id": pid})

        # 5. A captured pool needs its order placed.
        for pool in pools:
            pid = pool["pool_id"]
            if pid in tried["execute_purchase"]:
                continue
            if pool.get("status") == "purchase_ready":
                return _tool_event("execute_purchase", {"pool_id": pid})

        # Nothing left that this run may legitimately do — usually because a pool is
        # waiting on a human, which is not something the agent can or should resolve.
        # Recording *why* matters: a run that ends silently looks identical to a run that
        # found nothing, and those are very different situations to a judge or an operator.
        blocked = "; ".join(
            f"{p['pool_id']}: {p['blocking_reason']}" for p in pools if p.get("blocking_reason")
        )
        return _tool_event(
            "record_no_action",
            {
                "reason": (
                    f"reviewed {len(pools)} pool(s); nothing further to do this run. "
                    f"{blocked}"[:400]
                )
            },
        )
