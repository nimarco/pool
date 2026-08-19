"""Pin judge-visible architecture claims to the implementation they describe."""

from collections import Counter
from pathlib import Path

from pool.agent.tools import TOOL_SURFACE

ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_architecture_diagram_uses_current_counts_bounds_and_effect_kinds():
    svg = _read("docs/architecture.svg")
    effects = Counter(kind for _, kind in TOOL_SURFACE)

    assert "32 of 49 API paths reachable" in svg
    assert "45 s cooperative" in svg
    assert (
        f'{effects["read"]} read · {effects["record"]} record · '
        f'{effects["act"]} act · {effects["end"]} end'
    ) in svg
    assert "Deployed judge account: zero EventBridge rules" in svg
    assert "created_by_run proves causality" in svg

    for stale in (
        "14 of 45", "28 of 44", "29 of 45", "23 allowlisted", "25 calls · 120 s",
        "Created disabled",
    ):
        assert stale not in svg


def test_the_rehearsal_bounds_its_live_invocations_and_reads_stored_proof():
    """The recording may press the button only as often as the script says, and the proof
    it opens afterwards must be a *stored* run rather than a fresh one.

    The bound used to be one invocation. It is two now — the run that refuses and the run
    that acts on the changed world — which is inside the deployed per-session cap of
    three. What has not changed is that the number is fixed, stated, and not something a
    presenter improvises when a take goes badly.
    """
    script = _read("docs/DEMO_SCRIPT.md")
    flat = " ".join(script.split())

    assert "Click `Run Pool now` exactly once" in script
    assert "Technical proof for this run" in script
    # The bound, stated as a continuity rule rather than left implicit.
    assert "two** live AgentCore invocations and no more" in flat
    # And the proof is read back, never re-run to produce it.
    assert "without invoking anything" in flat
    assert "Do not spend another invocation" in flat
    assert "Press **Run the deployed" not in script
    # A failed take may never be papered over with an extra call.
    assert "keep the honest failure visible" in flat


def test_the_rehearsal_opens_on_the_person_not_a_dashboard():
    """The opening is the whole fix, so it is pinned rather than left to a copy pass.

    A judge has to watch somebody set up their own account and say what they buy, *before*
    anything about members, needs or coordination appears. Two earlier openings failed
    this differently: one led with a table of thirty-three seeded rows, and the next led
    with a search box belonging to a persona the visitor had been silently cast as.
    """
    script = _read("docs/DEMO_SCRIPT.md")
    # Prose wraps, so match against a single-spaced copy rather than pinning line breaks.
    flat = " ".join(script.split())
    headings = [line for line in script.splitlines() if line.startswith("## 0:00")]
    assert headings, "the rehearsal has no opening beat"
    # It opens on who is using it, not on what the fixture contains.
    assert "who" in headings[0].lower(), headings[0]

    # The rehearsal must not depend on a memorised product name. It used to open by
    # telling the presenter to type `vanilla whey`, which was honest only because search
    # could not yet surface what Pool can source — typing the category was a dead end.
    # The instruction is gone, and the script names the *category* path instead.
    assert "Type a category" in flat
    assert "Pool can source this" in flat
    for magic in ("Type `vanilla whey`", "type `vanilla whey`"):
        assert magic not in flat, "the rehearsal still depends on a memorised phrase"
    # The quotes are the demonstration, so they may not be arranged beforehand.
    assert "Do **not** pre-record the supplier quotes" in flat
    # Setup, not a seeded account.
    assert "Pool knows nothing about you" in flat
    assert "no name, no card, no declarations" in flat
    # The location claim that makes the demo work from any city.
    assert "has not asked the browser for a position" in flat
    # The honest framing of the manual trigger, which the screen also states.
    assert "nothing is scheduled in the demo account" in flat.lower()
    # And the boundary that keeps a real brand from vouching for an invented price.
    assert "supplier prices later in the demo are invented" in flat


def test_the_rehearsal_shows_a_refusal_as_well_as_a_result():
    """A demo that only ever succeeds is a demo of the happy path.

    The whole argument for a member-anchored run is that it answers *your* declarations —
    which is only checkable when one of the answers is no.
    """
    flat = " ".join(_read("docs/DEMO_SCRIPT.md").split())
    assert "both answers are no" in flat
    assert "the supplier will not sell fewer than" in flat
    # And the report may never be described as weighing something it did not evaluate.
    assert 'Never say Pool "considered" something the report does not list' in flat


def test_the_rehearsal_keeps_the_refusal_that_makes_the_sequence_evidence():
    """One quote that turns a no into a yes is an answer key.

    The changing-world sequence is only evidence because the *first* quote resolves the
    supply objection and is still refused on economics. That beat is the one a presenter
    running long would reach for first, so the script forbids cutting it explicitly and
    this pins the instruction.
    """
    flat = " ".join(_read("docs/DEMO_SCRIPT.md").split())
    assert "Do **not** cut the split-case quote" in flat
    assert "looks like an answer key" in flat
    # The mechanism is stated as one offer row, and as changing nothing about demand.
    assert "one supplier offer row was written" in flat
    assert "no agent ran" in flat
    # Provenance is never softened in narration.
    assert "Riverbend Wholesale does not exist" in flat


def test_the_rehearsal_says_the_showcase_has_its_own_community():
    """The backup replays a whole lifecycle. A judge has to know it does not replay it
    over the account the recording just set up."""
    flat = " ".join(_read("docs/DEMO_SCRIPT.md").split())
    assert "its own copy of Demo University" in flat
    assert "does not touch the account you set up" in flat


def test_readme_describes_the_product_run_as_its_own_proof():
    readme = _read("README.md")

    assert "No second live invocation is needed" in readme
    assert "`created_by_run`" in readme
    assert "zero EventBridge rules" in readme
    assert "31 allowlisted API paths" in readme


def test_the_rehearsal_quotes_figures_the_screen_will_actually_show():
    """Every number in the script is one the presenter will read off the page.

    The script's own continuity rule is "never say a number not visible on screen", and a
    stale pair does not look wrong — it looks like the presenter took a wrong turn. The
    detergent line broke it once by quoting the arithmetic of a *four*-unit declaration
    while step 6 tells the presenter to keep the form's default of two.

    So the whole changing-world sequence is driven here, through the same endpoints the
    browser calls, on the same defaults the form ships (``apps/web/src/views/needs.tsx``).
    Every sentence the script puts in a blockquote has to come back out of a real
    response. Nothing is asserted; it is all computed and then looked for.
    """
    from datetime import date, timedelta

    from fastapi.testclient import TestClient

    from pool.api import app as api
    from pool.services import supplier_updates as su

    # Blockquote markers dropped, not just collapsed: sentences are quoted across two
    # lines, so a plain whitespace join leaves a ">" in the middle of one.
    flat = " ".join(w for w in _read("docs/DEMO_SCRIPT.md").split() if w != ">")

    def quoted(sentence: str, what: str) -> None:
        assert sentence in flat, f"the rehearsal does not quote the {what}: {sentence}"

    api._repo.reset("demo")
    client = TestClient(api.app)
    client.get("/api/state")
    client.post(
        "/api/onboarding", json={"display_name": "Marco", "autonomy_mode": "ask_me_first"}
    )
    client.post("/api/onboarding/payment-method")
    household = client.get("/api/state").json()["consumer"]["household_id"]

    def declare(product_id: str) -> None:
        # `blankDraft` in the Needs form: two units, every 30 days, needed in 14.
        response = client.post(
            "/api/needs",
            json={
                "household_id": household,
                "product_id": product_id,
                "quantity": 2,
                "cadence_days": 30,
                "expected_next_need_date": (date.today() + timedelta(days=14)).isoformat(),
                "flexibility_days": 14,
                "routine_lead_days": 7,
                "min_savings_pct": 15,
                "max_spend_cents": 12000,
                "substitution": "exact_only",
            },
        )
        assert response.status_code == 200, response.text

    def me() -> dict:
        return client.get(f"/api/members/{household}").json()

    def run_results() -> dict[str, dict]:
        run = client.post("/api/agent/run", json={"trigger": "member_scan"}).json()
        report = client.get(
            f"/api/runs/{run['run_id']}/report", params={"household_id": household}
        ).json()
        return {r["product_id"]: r for r in report["results"]}

    declare(su.PRODUCT_ID)
    declare("prod_paper_towels")

    # --- the pre-run screen: demand that accumulated with no supplier behind it.
    standing = next(d for d in me()["standing_demand"] if d["product_id"] == su.PRODUCT_ID)
    quoted(
        f"{standing['compatible_members']} other members have independently declared "
        f"something this could be bought for — {standing['compatible_units']} bags. "
        f"With yours, {standing['compatible_units'] + standing['my_units']}.",
        "standing demand",
    )
    assert standing["has_supplier"] is False
    assert standing["minimum_units"] == 0

    # --- the first run: two refusals, for two different reasons.
    first = run_results()
    quoted(first[su.PRODUCT_ID]["headline"], "no-supplier refusal")
    quoted(first["prod_paper_towels"]["headline"], "supplier-minimum refusal")

    # --- the split-case quote, and the blocker it moves to. No run in between.
    split = su.QUOTES["rice_split_case"]
    client.post("/api/demo/supplier-updates", json={"quote": split.key})
    outlook = next(o for o in me()["needs_outlook"] if o["product_id"] == su.PRODUCT_ID)
    quoted(outlook["reason"], "outlook after the split-case quote")

    # --- the case-programme quote, and the minimum the screen then shows.
    program = su.QUOTES["rice_case_program"]
    client.post("/api/demo/supplier-updates", json={"quote": program.key})
    standing = next(d for d in me()["standing_demand"] if d["product_id"] == su.PRODUCT_ID)
    quoted(
        f"The supplier's best price starts at {standing['minimum_units']}.",
        "supplier minimum after the case-programme quote",
    )

    # --- the second run, on the changed world.
    second = run_results()
    result = second[su.PRODUCT_ID]
    assert result["result"] == "formed_included", result

    # The script quotes four of the six "why this worked" lines and says so — reading all
    # of them out loud is worse television. What it may never do is quote a line the run
    # did not produce, so every fact in that blockquote has to come back out of the run.
    block = flat.split("Open **Why this worked** and read three lines, not all six:")[1]
    block = block.split("That last line matters")[0]
    quoted_facts = [
        piece.strip(" *·") for piece in block.split(" · ") if piece.strip(" *·")
    ]
    assert len(quoted_facts) >= 4, quoted_facts
    for fact in quoted_facts:
        assert fact in result["facts"], (
            f"the rehearsal quotes a line this run did not produce: {fact}"
        )

    detail = client.get(f"/api/pools/{result['pool_id']}").json()
    mine = next(m for m in detail["members"] if m["household_id"] == household)
    quoted(
        f"Your {mine['units']} bags · about {mine['estimated_cost_display']} instead of "
        f"{mine['baseline_display']} buying alone.",
        "member's own line on the order card",
    )

    # --- and the quote terms the operator panel prints.
    for quote, price in ((split, "$9.75"), (program, "$6.25")):
        assert f"{price} a bag" in flat, quote.key
        assert f"minimum {quote.min_units} bags" in flat or (
            f"{quote.min_units} minimum" in flat
        ), quote.key
