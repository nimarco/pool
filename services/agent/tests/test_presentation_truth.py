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

    assert "29 of 45 API paths reachable" in svg
    assert "45 s cooperative" in svg
    assert (
        f'{effects["read"]} read · {effects["record"]} record · '
        f'{effects["act"]} act · {effects["end"]} end'
    ) in svg
    assert "Deployed judge account: zero EventBridge rules" in svg
    assert "created_by_run proves causality" in svg

    for stale in (
        "14 of 45", "28 of 44", "23 allowlisted", "25 calls · 120 s", "Created disabled",
    ):
        assert stale not in svg


def test_rehearsal_uses_one_product_invocation_and_later_opens_stored_proof():
    script = _read("docs/DEMO_SCRIPT.md")

    assert "Click `Run Pool now` exactly once" in script
    assert "Technical proof for this run" in script
    assert "Do not open it" in script  # collapsed Run again control
    assert "Never invoke the runtime again" in script
    assert "Press **Run the deployed" not in script
    assert "same stored run" in script


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
    assert "one of the answers is no" in flat
    assert "the supplier will not sell fewer than" in flat
    # And the report may never be described as weighing something it did not evaluate.
    assert 'Never say Pool "considered" something the report does not list' in flat


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
    assert "29 allowlisted API paths" in readme


def test_the_rehearsal_quotes_figures_the_screen_will_actually_show():
    """Every number in the script is one the presenter will read off the page.

    The script's own continuity rule is "never say a number not visible on screen", and
    the detergent line broke it: the pair it quoted was the arithmetic of a *four*-unit
    declaration, while step 6 tells the presenter to keep the form's default of two. Both
    figures move together with the quantity, so a stale pair does not look wrong — it
    looks like the presenter took a wrong turn.

    Computed here through the same endpoints the browser calls, on the same defaults the
    form ships (``apps/web/src/views/needs.tsx``), rather than asserted.
    """
    from datetime import date, timedelta

    from fastapi.testclient import TestClient

    from pool.api import app as api

    api._repo.reset("demo")
    client = TestClient(api.app)
    client.get("/api/state")
    client.post(
        "/api/onboarding", json={"display_name": "Marco", "autonomy_mode": "ask_me_first"}
    )
    client.post("/api/onboarding/payment-method")
    household = client.get("/api/state").json()["consumer"]["household_id"]
    # `blankDraft` in the Needs form: two units, every 30 days, needed in 14.
    response = client.post(
        "/api/needs",
        json={
            "household_id": household,
            "product_id": "prod_detergent_pods",
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

    run = client.post("/api/agent/run", json={"trigger": "member_scan"}).json()
    report = client.get(
        f"/api/runs/{run['run_id']}/report", params={"household_id": household}
    ).json()
    headline = report["results"][0]["headline"]

    # Blockquote markers dropped, not just collapsed: the sentence is quoted across two
    # lines, so a plain whitespace join leaves a ">" in the middle of it.
    flat = " ".join(w for w in _read("docs/DEMO_SCRIPT.md").split() if w != ">")
    assert headline in flat, f"the rehearsal does not quote what the screen says: {headline}"
