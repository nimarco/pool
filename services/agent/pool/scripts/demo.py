"""Run the showcase scenario from the command line and print a readable transcript.

Free: uses the in-memory repository, deterministic routing, and the offline planner
unless the environment says otherwise.
"""

from __future__ import annotations

import json
import sys

from pool.adapters.repository import build_repository
from pool.config import get_settings
from pool.services.demo import run_showcase

BOLD, DIM, GREEN, RED, RESET = "\033[1m", "\033[2m", "\033[32m", "\033[31m", "\033[0m"


def main() -> int:
    settings = get_settings()
    repo = build_repository(settings.repository, settings.dynamodb_table, settings.aws_region)
    workspace = "demo"

    print(f"{BOLD}Pool — showcase scenario{RESET}")
    print(f"{DIM}repository={settings.repository} routing={settings.routing_provider} "
          f"model={settings.model_provider}{RESET}\n")

    result = run_showcase(repo, workspace, settings=settings)

    for i, step in enumerate(result.steps, 1):
        print(f"{BOLD}{i}. {step.name}{RESET} — {step.detail}")
        for key, value in step.facts.items():
            rendered = json.dumps(value) if isinstance(value, (list, dict)) else value
            print(f"   {DIM}{key:34s}{RESET} {rendered}")
        print()

    if result.ok:
        print(f"{GREEN}✓ scenario completed: discovered, formed, approved, broke, recovered{RESET}")
        return 0
    print(f"{RED}✗ scenario failed: {result.failure}{RESET}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
