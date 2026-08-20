import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ScenarioResult } from "../api";
import { RunView } from "./run";

/* The steps a successful run actually emits, in order, as asserted by
   `services/agent/tests/test_demo_scenario.py::test_the_whole_lifecycle_completes`.
   This list was thirteen long and omitted `member_declared_need` — the step that begins
   the scenario — which is how the reader shipped with fourteen steps and thirteen
   authored chapters. Keep the two in step. */
const STAGES = [
  "seed",
  "member_declared_need",
  "latent_demand_discovered",
  "host_candidates_evaluated",
  "host_accepted",
  "final_offer",
  "payment_failure",
  "decision_inbox",
  "recovery",
  "locked_and_captured",
  "purchase",
  "distribution_open",
  "pickup",
  "impact",
];

const SCENARIO: ScenarioResult = {
  ok: true,
  failure: "",
  pool_id: "pool_complete",
  workspace: "wtestsession01-showcase",
  steps: STAGES.map((name) => ({
    name,
    detail: `Recorded ${name.replace(/_/g, " ")}`,
    facts:
      name === "latent_demand_discovered"
        ? { threshold_units: 24, provisional_units: 24 }
        : name === "payment_failure"
          ? { units_lost: 2, threshold_units: 24, funded_units: 22 }
          : name === "recovery"
            ? { recovered: 2, funded_units_now: 24 }
            : name === "purchase"
              ? { units: 24, cases: 2 }
              : {},
  })),
};

function renderSheet() {
  render(
    <RunView
      scenario={SCENARIO}
      roundTripMs={42}
      running={false}
      onRun={() => {}}
      onOpenPool={() => {}}
      onLive={() => {}}
    />,
  );
}

afterEach(cleanup);

describe("the lifecycle sheet", () => {
  it("puts every recorded step on one page, so the causal chain is co-visible", () => {
    renderSheet();

    /* The point of the sheet. The reader used to paginate, and the arithmetic that makes
       this a real coordinator — 24 funded, two lost to a declined card, two restored by
       a replacement — was spread over three pages that could not be seen together. Two
       of those pages printed the identical figure while one claimed a repair. */
    for (const name of STAGES) {
      expect(screen.getByText(`Recorded ${name.replace(/_/g, " ")}.`)).toBeTruthy();
    }
    expect(screen.getByText(/14 steps · 42 ms/)).toBeTruthy();
  });

  it("authors every step it renders, including the one that begins the run", () => {
    renderSheet();

    // `member_declared_need` had no chapter, so it fell through to a fallback that cut a
    // headline out of the server's sentence and attributed a person's act to the engine.
    expect(screen.getByText("One person said what she buys")).toBeTruthy();
    expect(screen.queryByText(/has no authored chapter yet/)).toBeNull();
    expect(screen.queryByText("member declared need")).toBeNull();
  });

  it("names the acts as destinations rather than unlabelled segments", () => {
    renderSheet();

    const acts = screen.getByRole("navigation", { name: "Acts" });
    const labels = within(acts)
      .getAllByRole("link")
      .map((a) => a.textContent);
    expect(labels).toContain("A member declares");
    expect(labels).toContain("Failure");
    expect(labels).toContain("Recovery");
    // Consecutive steps in one act collapse to a single destination.
    expect(new Set(labels).size).toBe(labels.length);
  });

  it("says in words whatever the spine draws, so the drawing is never the only carrier", () => {
    renderSheet();

    const caption = document.querySelector(".spine-caption");
    expect(caption?.getAttribute("aria-live")).toBe("polite");
    expect((caption?.textContent ?? "").length).toBeGreaterThan(0);
  });

  it("closes on the claim rather than on a collapsed disclosure", () => {
    renderSheet();

    const close = screen.getByText(/Nobody created a group/);
    expect(close.closest("details")).toBeNull();
    expect(screen.getByRole("button", { name: /Now run it live on AWS/ })).toBeTruthy();
  });
});
