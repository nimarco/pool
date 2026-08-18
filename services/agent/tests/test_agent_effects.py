"""What each tool is *labelled* must match what it actually writes.

``find_host_candidates`` was published to the model, to the API, and to the Showcase as
a read for as long as it has existed, while opening host recruiting and persisting a
candidate record per evaluation. Nothing caught it because nothing checked: the label
lived in one tuple, the behaviour lived in another module, and every test asserted the
tuple against itself.

So this file does not read docstrings or trust ``TOOL_SURFACE``. It snapshots the entire
workspace, calls a tool, and snapshots it again. A tool that claims to read and writes
anything fails here, whatever its documentation says.
"""

from __future__ import annotations

import json

import pytest

from pool.adapters.repository import InMemoryRepository
from pool.agent.tools import (
    MUTATING_TOOL_KINDS,
    TOOL_KINDS,
    TOOL_SURFACE,
    ToolContext,
    build_tools,
)
from pool.data.seed import COMMUNITY_ID, seed
from pool.services import coordination as coord
from tests.conftest import WS

PRODUCT = "prod_whey_vanilla"
SITE = "site_union"

#: Arguments that make each tool do real work against the seeded community. A read tool
#: called with a bad id returns an error and writes nothing whatever its label, which
#: would make the check pass for the wrong reason.
READ_TOOL_ARGUMENTS: dict[str, dict] = {
    "list_latent_demand": {},
    "evaluate_pool_economics": {"product_id": PRODUCT, "pickup_site_id": SITE},
    "inspect_pool": {"pool_id": "<pool>"},
    "list_pools_needing_attention": {},
}


def _snapshot(repo: InMemoryRepository, ws: str) -> str:
    """Everything in a workspace, as a stable string.

    Compares the whole store rather than a chosen list of entities, so a tool that
    starts writing something nobody thought to check is still caught.
    """
    store = repo.store(ws)
    return json.dumps(
        {
            name: [
                item.to_dict() if hasattr(item, "to_dict") else str(item)
                for item in (value.values() if isinstance(value, dict) else value)
            ]
            for name, value in sorted(vars(store).items())
        },
        sort_keys=True,
        default=str,
    )


@pytest.fixture
def tool_ctx(seeded_ctx):
    return ToolContext(pool=seeded_ctx, community_id=COMMUNITY_ID)


@pytest.fixture
def tools(tool_ctx):
    return {t.tool_name: t for t in build_tools(tool_ctx)}


def _call(tool, **kwargs):
    """Invoke a Strands-decorated tool directly, bypassing the agent loop.

    ``@tool`` keeps the undecorated function on ``__wrapped__`` (functools' convention),
    which is what makes it callable here without a model, a session, or a token spend.
    """
    return tool.__wrapped__(**kwargs)


# --------------------------------------------------------------- the surface is coherent


def test_every_declared_kind_is_one_of_the_four():
    assert {kind for _, kind in TOOL_SURFACE} <= TOOL_KINDS


def test_the_surface_describes_exactly_the_tools_that_exist(tools):
    assert [name for name, _ in TOOL_SURFACE] == list(tools)


def test_mutating_kinds_are_the_complement_of_read():
    """One definition of "writes", so the effect test and the API cannot disagree."""
    assert TOOL_KINDS - {"read", "end"} == MUTATING_TOOL_KINDS


# ------------------------------------------------------- reads are proved, not asserted


@pytest.mark.parametrize(
    "name", [n for n, kind in TOOL_SURFACE if kind == "read"]
)
def test_a_read_tool_changes_nothing_at_all(name, tools, tool_ctx, seeded_ctx):
    """The invariant that would have caught the mislabelled host search."""
    pool, _ = _existing_pool(seeded_ctx)
    arguments = {
        k: (pool.id if v == "<pool>" else v)
        for k, v in READ_TOOL_ARGUMENTS[name].items()
    }

    before = _snapshot(seeded_ctx.repo, WS)
    result = _call(tools[name], **arguments)
    after = _snapshot(seeded_ctx.repo, WS)

    assert after == before, f"{name} is declared read-only but wrote to the workspace"
    # And it did real work rather than erroring out early, which would make the
    # comparison above true for the wrong reason.
    assert "error" not in json.loads(result)


def test_the_host_search_is_declared_for_what_it_does(tools, seeded_ctx):
    """The regression. It writes, so it must not be labelled a read.

    Left as a behavioural assertion rather than a label assertion: if the tool is ever
    made genuinely inert, this fails and asks for the label back.
    """
    assert dict(TOOL_SURFACE)["find_host_candidates"] in MUTATING_TOOL_KINDS

    pool, _ = _existing_pool(seeded_ctx)
    before = _snapshot(seeded_ctx.repo, WS)
    _call(tools["find_host_candidates"], pool_id=pool.id)
    after = _snapshot(seeded_ctx.repo, WS)

    assert after != before


def test_the_host_search_records_but_commits_nothing(tools, seeded_ctx):
    """`record` is a real distinction: it must not offer anybody the job."""
    pool, _ = _existing_pool(seeded_ctx)

    _call(tools["find_host_candidates"], pool_id=pool.id)

    assert seeded_ctx.repo.get_host_assignment(WS, pool.id) is None
    assert seeded_ctx.repo.list_decisions(WS) == []
    assert seeded_ctx.repo.list_payments(WS) == []
    assert all(
        c.state.value != "offered"
        for c in seeded_ctx.repo.list_host_candidates(WS, pool.id)
    )


def test_the_api_publishes_the_same_kinds_the_tools_carry():
    """The UI labels each door from this, so a drifting copy is a lie on the page."""
    from fastapi.testclient import TestClient

    from pool.api.app import app

    published = TestClient(app).get("/api/health").json()["agent_tools"]

    assert [(t["name"], t["kind"]) for t in published] == list(TOOL_SURFACE)


# --------------------------------------------------------------------------- helpers


def _existing_pool(ctx):
    assessment = coord.evaluate_opportunity(
        ctx=ctx, community_id=COMMUNITY_ID, product_id=PRODUCT, pickup_site_id=SITE
    )
    return coord.create_candidate_pool(
        ctx=ctx, assessment=assessment, idempotency_key="effects"
    )


@pytest.fixture(autouse=True)
def _seeded(repo):
    seed(repo, WS)
    return repo
