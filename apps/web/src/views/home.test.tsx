/* The proof action belongs to the pool the card actually drew.
 *
 * Home's opportunity card and the "technical proof for this run" button next to it used
 * to arrive at their pool independently — the card rendered one, the handler looked up
 * another. In the canonical single-pool scenario they always agreed, which is exactly
 * what makes the coupling worth pinning: the failure only appears once a second pool
 * exists, and by then it is a judge being shown the wrong run.
 *
 * So this asserts identity rather than behaviour: whatever pool is on screen, the id the
 * proof action carries is that pool's id.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppState, PoolView } from "../api";
import * as apiModule from "../api";
import { Home } from "./home";

const ROSA = { id: "hh_navarro", display_name: "Rosa N." };

function poolView(overrides: Partial<PoolView> = {}): PoolView {
  return {
    pool_id: "pool_shown",
    created_by_run: "run_shown",
    execution_proof: {
      pool_id: "pool_shown",
      created_by_run: "run_shown",
      run_id: "run_shown",
      relation_verified: true,
      execution: { service: "In-process Strands coordinator", live: false, region: "local" },
      workspace_readback: { run_recorded: true, pool_recorded: true, same_workspace: true },
      run: {
        run_id: "run_shown",
        trigger: "manual_scan",
        outcome: "pool_created",
        iterations: 3,
        tool_calls: ["list_latent_demand"],
        termination_reason: "candidate_pool_created",
        model_provider: "offline",
        model_id: "offline-deterministic-planner",
        duration_ms: 40,
        input_tokens: 0,
        output_tokens: 0,
        started_at: "2026-08-18T12:00:00Z",
      },
    },
    community_id: "community_demo",
    product_id: "prod_whey",
    product_name: "Whey protein, vanilla",
    unit: "tub",
    brand: "Fixture",
    supplier: "Riverbend Wholesale",
    status: "final_offer",
    pickup_site: "North Hall lobby",
    pickup_is_public: true,
    pickup_permission: "demo",
    threshold_units: 24,
    provisional_units: 24,
    funded_units: 24,
    member_count: 10,
    buyer_count: 10,
    progress_pct: 100,
    has_final_offer: true,
    quote_verified_at: "2026-08-18T12:00:00Z",
    failure_reason: "",
    timing: {},
    host: null,
    economics: null,
    savings_display: "$266.32",
    savings_pct: "23.6%",
    is_estimate: false,
    ...overrides,
  };
}

/* A second pool, so "the pool on screen" and "some pool in state" are distinguishable. */
const OTHER = poolView({
  pool_id: "pool_other",
  created_by_run: "run_other",
  product_name: "Paper towels, 6 rolls",
  execution_proof: null,
});

function appState(pools: PoolView[]): AppState {
  return {
    workspace: "w_test",
    community: null,
    pools,
    decisions: [],
    activity: [],
    metrics: {
      estimated_retail_spend_cents: 0,
      pool_spend_cents: 0,
      collective_savings_cents: 0,
      average_buyer_savings_cents: 0,
      host_earnings_cents: 0,
      payment_processing_cents: 0,
      platform_fee_cents: 0,
      pools_locked_or_beyond: 0,
    } as AppState["metrics"],
    runs: [],
    counts: { members: 24, needs: 33, products: 6, standing_hosts: 4, open_issues: 0 },
    is_demo_data: true,
  };
}

function renderHome(pools: PoolView[], onShowAgent: (poolId: string) => void) {
  return render(
    <Home
      state={appState(pools)}
      identity={ROSA}
      lastRun={null}
      running={false}
      busyDecision={null}
      onFind={() => {}}
      onOpenPool={() => {}}
      onRespond={() => {}}
      onShowAgent={onShowAgent}
      onGoNeeds={() => {}}
      liveDiscovery={false}
    />,
  );
}

afterEach(cleanup);

describe("the proof action on Home", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiModule.api, "needs").mockResolvedValue({
      needs: [],
      products: [],
      limits: {
        max_quantity: 100,
        max_cadence_days: 365,
        max_min_savings_pct: 90,
        max_spend_cents: 500000,
        max_horizon_days: 365,
      },
    });
    vi.spyOn(apiModule.api, "member").mockRejectedValue(new Error("not needed"));
    vi.spyOn(apiModule.api, "hostOpportunities").mockRejectedValue(new Error("not needed"));
  });

  it("opens the proof for the pool the card is showing, not for whichever pool sorts first", async () => {
    const shown = poolView();
    const onShowAgent = vi.fn();
    renderHome([shown, OTHER], onShowAgent);

    // Whatever the card drew is the pool whose proof must open.
    expect(screen.getByText(shown.product_name)).toBeTruthy();
    expect(screen.queryByText(OTHER.product_name)).toBeNull();

    await userEvent.click(
      screen.getByRole("button", { name: /technical proof for this run/i }),
    );

    await waitFor(() => expect(onShowAgent).toHaveBeenCalledTimes(1));
    expect(onShowAgent).toHaveBeenCalledWith(shown.pool_id);
    expect(onShowAgent).not.toHaveBeenCalledWith(OTHER.pool_id);
  });
});
