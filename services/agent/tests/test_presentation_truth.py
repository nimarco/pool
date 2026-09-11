"""Pin judge-visible architecture claims to the implementation they describe."""

from collections import Counter
from pathlib import Path

from pool.agent.tools import (
    CLARIFICATION_TOOL_SURFACE,
    STRATEGY_TOOL_SURFACE,
    TOOL_SURFACE,
)

ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_architecture_diagram_uses_current_counts_bounds_and_effect_kinds():
    svg = _read("docs/architecture.svg")
    effects = Counter(kind for _, kind in TOOL_SURFACE)

    assert "36 of 55 API paths reachable" in svg
    assert "45 s cooperative" in svg
    assert (
        f'{effects["read"]} read · {effects["record"]} record · '
        f'{effects["act"]} act · {effects["end"]} end'
    ) in svg
    assert "Deployed judge account: zero EventBridge rules" in svg
    assert "created_by_run proves causality" in svg

    for stale in (
        "14 of 45", "28 of 44", "29 of 45", "32 of 49", "23 allowlisted", "25 calls · 120 s",
        "Created disabled",
    ):
        assert stale not in svg


def test_the_strands_diagram_states_the_route_split_and_its_own_counts():
    """The second diagram (`docs/architecture-strands.svg`) is judge-visible too.

    Its whole reason for existing is that the first one drew the two routes as one chain,
    so a judge reading it would think the public demo calls Nova. The claims pinned here
    are the ones that make the split legible: which provider sits in the model position on
    each route, that the public route spends nothing and holds no model permission, and
    that the tool surface is selected per objective rather than handed over whole.

    Counts are derived from the code, never typed twice.
    """
    from pool.config import AgentBounds

    svg = _read("docs/architecture-strands.svg")
    effects = Counter(kind for _, kind in TOOL_SURFACE)
    bounds = AgentBounds()
    total_tools = (
        len(TOOL_SURFACE) + len(STRATEGY_TOOL_SURFACE) + len(CLARIFICATION_TOOL_SURFACE)
    )

    # The split itself, named on both sides.
    assert "ROUTE A · PUBLIC JUDGE DEMO" in svg
    assert "ROUTE B · DEPLOYED AGENTCORE" in svg
    assert "THE MODEL POSITION" in svg
    # Route A: the deterministic provider, in-process, free, and unable to reach a model.
    assert "DeterministicPlannerModel" in svg
    assert "strands.models.Model" in svg
    assert "in-process in the Lambda" in svg
    assert "0 model tokens" in svg
    assert "no bedrock:InvokeModel" in svg
    # Route B: the deployed runtime and the model it actually uses.
    assert "strands.models.BedrockModel" in svg
    assert "Amazon Nova Lite" in svg
    assert "AWS_IAM inbound" in svg
    assert "separate deployment" in svg
    # The judge path is Route A, said on the diagram rather than left to be inferred.
    assert "what a judge clicks" in svg
    # And the shared-core claim, which is the thing a judge must not misread.
    assert "Shared by both routes" in svg
    assert "SHARED BY BOTH ROUTES" in svg

    # The Strands surface claim, which is the Technical Implementation argument.
    assert f"@tool × {total_tools}" in svg
    assert "strands.hooks.HookProvider" in svg
    assert "four hook events" in svg

    # Every count and bound, derived.
    assert f"agent/tools.py — {total_tools} @tool" in svg
    assert (
        f'{len(TOOL_SURFACE)} lifecycle: {effects["read"]} read · '
        f'{effects["record"]} record · {effects["act"]} act · {effects["end"]} end'
    ) in svg
    assert (
        f"+ {len(STRATEGY_TOOL_SURFACE)} cohort-strategy "
        f"+ {len(CLARIFICATION_TOOL_SURFACE)} clarification"
    ) in svg
    assert (
        f"{bounds.max_iterations} iterations · {bounds.max_tool_calls} tool calls · "
        f"45 s · {bounds.max_duplicate_tool_calls} duplicate calls"
    ) in svg
    assert "36 of 55 API paths" in svg
    assert "Zero EventBridge rules exist in the deployed judge account" in svg

    # And it may not reintroduce the thing it was drawn to fix: a chain in which the
    # public edge leads into AgentCore.
    assert "CloudFront → Lambda → Strands + offline" not in svg


def test_the_strands_diagram_trace_band_matches_the_recorded_run():
    """The trace band is evidence, so it may not drift from the run it came from.

    Both are pinned to the same recorded run (`docs/AGENT_TRACE_EVIDENCE.md`): the tool
    names in the diagram must be tools that exist, must appear in the evidence file in the
    same order, and the beat the band exists to show — a refusal the agent absorbed and
    redirected around — must still be described as a refusal on both surfaces.

    A diagram claiming a sequence the evidence file does not record is the one failure
    mode that would turn this band from proof into decoration.
    """
    svg = _read("docs/architecture-strands.svg")
    evidence = _read("docs/AGENT_TRACE_EVIDENCE.md")

    # The exact run the band is attributed to, named identically on both surfaces.
    run_id = "run_8a7b91e6793c"
    assert run_id in svg
    assert run_id in evidence

    # The six steps, in the order the run made them.
    trace = [
        "list_cohort_strategies",
        "evaluate_cohort_strategy",
        "evaluate_cohort_strategy",
        "create_candidate_pool",  # wraps across two lines in the band
        "find_host_candidates",
        "record_no_action",
    ]
    # Every name in the band is a tool that actually exists on some surface.
    every_tool = {name for name, _ in TOOL_SURFACE} | {
        name for name, _ in STRATEGY_TOOL_SURFACE
    } | {name for name, _ in CLARIFICATION_TOOL_SURFACE}
    for name in trace:
        assert any(t.startswith(name) for t in every_tool), name

    # And they appear in the diagram in that order, left to right.
    cursor = 0
    for name in trace:
        found = svg.find(name, cursor)
        assert found != -1, f"{name} missing from the trace band, or out of order"
        cursor = found + 1

    # The beat the band is for: refused on economics, then redirected, then a mutation
    # gated on the evidence rather than on the model's assertion.
    assert "not_cheaper" in svg and "not_cheaper" in evidence
    assert "REDIRECTED" in svg
    assert "viable: false" in svg and "viable: true" in svg
    assert "evaluation_id" in svg
    # `eligible_count: 0` is the second deterministic refusal, and the reason the run
    # ended in `record_no_action` rather than a host offer.
    assert "eligible_count: 0" in svg

    # The band may never imply the refusal was a tool *error*. It was a successful call
    # returning a negative verdict, and the evidence file says so explicitly.
    assert "not a tool error" in evidence


def test_readme_describes_the_product_run_as_its_own_proof():
    """The proof explains the run that already happened; it never buys a second one.

    The phrasing moved when the judge path stopped being a button — there is no second
    invocation to decline now, because there was never a first one to press. What is
    pinned is the property rather than the old sentence: the proof is *of this run*, the
    lineage field is named, and the endpoint count is the measured one.
    """
    readme = _read("README.md")

    assert "Technical proof for this run" in readme
    assert "`created_by_run`" in readme
    assert "zero EventBridge rules" in readme
    # The count the allowlist guard measures, not a number that drifted away from it.
    # `test_public_demo.py` asserts the same pair against the running application.
    assert "36 of 55 API paths, allowlisted" in readme
    assert "36 of 55 endpoints exist" in readme


def test_the_readme_dates_every_cloud_claim_it_makes():
    """A live claim with no observation date behind it is the one that rots quietly.

    Every ``Verified`` row in the AWS table has to carry the date somebody observed it —
    *a* date, checked by shape rather than by value, because pinning the literal turns a
    guard about honesty into a guard about the calendar. This one was written pinned and
    failed the day the deployment was refreshed, which is the wrong reason to fail.

    The second half is the distinction the deployment actually has: the public judge
    surface runs the deterministic planner and holds no model permission, and a live model
    is reachable only through AgentCore. Blurring those two is the specific overclaim this
    page is most likely to drift into.
    """
    import re

    readme = _read("README.md")
    aws = readme[readme.index("## AWS") :]
    rows = [ln for ln in aws.splitlines() if ln.startswith("| ") and "Verified" in ln]
    assert rows, "the AWS table has no verified rows to check"
    for line in rows:
        assert re.search(r"\b20\d\d-\d\d-\d\d\b", line), line

    assert "no model permission" in aws
    assert "only path to a live model" in aws or "only when the live agent action" in aws
