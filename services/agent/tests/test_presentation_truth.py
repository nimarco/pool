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

    assert "24 of 40 API paths reachable" in svg
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

    assert "Click `Find opportunities` exactly once" in script
    assert "Technical proof for this run" in script
    assert "Do not open it" in script  # collapsed Run again control
    assert "Never invoke the runtime again" in script
    assert "Press **Run the deployed" not in script
    assert "same stored run" in script


def test_readme_describes_the_product_run_as_its_own_proof():
    readme = _read("README.md")

    assert "No second live invocation is needed" in readme
    assert "`created_by_run`" in readme
    assert "zero EventBridge rules" in readme
    assert "24 allowlisted API paths" in readme
