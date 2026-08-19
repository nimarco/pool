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

    assert "28 of 43 API paths reachable" in svg
    assert "45 s cooperative" in svg
    assert (
        f'{effects["read"]} read · {effects["record"]} record · '
        f'{effects["act"]} act · {effects["end"]} end'
    ) in svg
    assert "Deployed judge account: zero EventBridge rules" in svg
    assert "created_by_run proves causality" in svg

    for stale in ("14 of 45", "23 allowlisted", "25 calls · 120 s", "Created disabled"):
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

    assert "`vanilla whey`" in flat
    # Setup, not a seeded account.
    assert "Pool knows nothing about you" in flat
    assert "no name, no card, no declarations" in flat
    # The location claim that makes the demo work from any city.
    assert "has not asked the browser for a position" in flat
    # The honest framing of the manual trigger, which the screen also states.
    assert "nothing is scheduled in the demo account" in flat.lower()
    # And the boundary that keeps a real brand from vouching for an invented price.
    assert "supplier prices later in the demo are invented" in flat


def test_readme_describes_the_product_run_as_its_own_proof():
    readme = _read("README.md")

    assert "No second live invocation is needed" in readme
    assert "`created_by_run`" in readme
    assert "zero EventBridge rules" in readme
    assert "28 allowlisted API paths" in readme
