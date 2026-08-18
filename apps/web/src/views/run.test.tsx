import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { ScenarioResult } from "../api";
import { RunView } from "./run";

const STAGES = [
  "seed",
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
  steps: STAGES.map((name) => ({
    name,
    detail: `Recorded ${name.replace(/_/g, " ")}`,
    facts: {},
  })),
};

afterEach(cleanup);

describe("13-stage lifecycle reader", () => {
  it("keeps every stage, its recorded summary, and disclosed explanation navigable", async () => {
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

    const ruler = screen.getByRole("navigation", { name: "Lifecycle steps" });
    expect(within(ruler).getAllByRole("button")).toHaveLength(13);
    expect(screen.getByText("01 / 13")).toBeTruthy();
    expect(screen.getByText("whole run: 42 ms")).toBeTruthy();
    expect(screen.getByText("Recorded seed.")).toBeTruthy();

    const firstNote = screen.getByText("Why this matters").closest("details") as HTMLDetailsElement;
    expect(firstNote.open).toBe(false);

    await userEvent.click(
      screen.getByRole("button", { name: "Step 8: Replace exactly what was lost" }),
    );
    expect(screen.getByText("08 / 13")).toBeTruthy();
    expect(screen.getByText("Recorded recovery.")).toBeTruthy();
    expect(screen.getByText("Recovery and count reconciliation")).toBeTruthy();

    await userEvent.click(
      screen.getByRole("button", { name: "Step 13: What the week actually cost" }),
    );
    expect(screen.getByText("13 / 13")).toBeTruthy();
    expect(screen.getByText("Recorded impact.")).toBeTruthy();
  });
});
