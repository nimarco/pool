/* Home is the one screen a member is guaranteed to see, so what it claims about the
 * agent has to be exactly what the server said.
 *
 * Four different failures are pinned here, and they are all the same failure: the
 * interface answering a question on the server's behalf.
 *
 *   - the proof action arriving at a *different* pool than the card drew;
 *   - the order card showing the group's numbers under a personal heading;
 *   - the autonomy panel listing limits while omitting the switch that decides whether
 *     any of them are ever consulted;
 *   - the decision card naming the rule that blocked a commitment instead of the policy
 *     engine's own sentence about it.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppState, Decision, MemberView, PoolMember, PoolView } from "../api";
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
    variant: "",
    image_ref: "",
    supplier: "Riverbend Wholesale",
    offer_source: "synthetic",
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

const ROSA_MEMBERSHIP: PoolMember = {
  household_id: "hh_navarro",
  display_name: "Rosa N.",
  units: 2,
  state: "authorized",
  path: "human_approved",
  estimated_cost_display: "$72.10",
  final_cost_display: "$71.83",
  baseline_display: "$93.98",
  savings_pct: "23.5%",
  travel_minutes: 3,
  is_host: false,
};

/* A second pool, so "the pool on screen" and "some pool in state" are distinguishable. */
const OTHER = poolView({
  pool_id: "pool_other",
  created_by_run: "run_other",
  product_name: "Paper towels, 6 rolls",
  execution_proof: null,
});

const METRICS = {
  estimated_retail_spend_cents: 112776,
  pool_spend_cents: 86144,
  collective_savings_cents: 26632,
  average_buyer_savings_cents: 2663,
  host_earnings_cents: 4468,
  payment_processing_cents: 2806,
  platform_fee_cents: 3270,
  pools_locked_or_beyond: 1,
  coordination_actions_automated: 18,
  human_decisions_requested: 3,
  commitments_without_asking: 8,
  pools_recovered: 1,
  pickups_completed: 10,
  pickups_expected: 10,
} as unknown as AppState["metrics"];

function appState(pools: PoolView[], decisions: Decision[] = []): AppState {
  return {
    workspace: "w_test",
  consumer: {
    household_id: "hh_navarro",
    display_name: "Alex",
    onboarded: true,
    has_payment_method: true,
    autonomy_mode: "ask_me",
    place: {
      community_id: "comm_demo_university",
      community_name: "Demo University",
      member_count: 24,
      pickup_site_count: 4,
      synthetic: true,
    },
  },
    community: null,
    pools,
    decisions,
    activity: [],
    metrics: METRICS,
    runs: [],
    counts: { members: 24, needs: 33, products: 6, standing_hosts: 4, open_issues: 0 },
    is_demo_data: true,
  };
}

function memberView(mode: string): MemberView {
  return {
    id: "hh_navarro",
    display_name: "Rosa N.",
    zone: "Campus core",
    community_membership: null,
    has_payment_method: true,
    autonomy_display: {
      mode,
      min_savings: "20%",
      max_spend: "$90.00",
      max_travel: "15 min",
      substitution: "exact_only",
      public_pickup_only: true,
    },
    host_profile: null,
  };
}

function renderHome(
  pools: PoolView[],
  options: { onShowAgent?: (poolId: string) => void; decisions?: Decision[] } = {},
) {
  return render(
    <Home
      state={appState(pools, options.decisions ?? [])}
      identity={ROSA}
      running={false}
      busyDecision={null}
      onFind={() => {}}
      onOpenPool={() => {}}
      onRespond={() => {}}
      onShowAgent={options.onShowAgent ?? (() => {})}
      onStartNeed={() => {}}
      onGoCommunity={() => {}}
      liveDiscovery={false}
      region={null}
    />,
  );
}

afterEach(cleanup);

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
  vi.spyOn(apiModule.api, "pool").mockRejectedValue(new Error("not needed"));
});

describe("the proof action on Home", () => {
  it("opens the proof for the pool the card is showing, not for whichever pool sorts first", async () => {
    const shown = poolView();
    const onShowAgent = vi.fn();
    renderHome([shown, OTHER], { onShowAgent });

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

describe("the member's own stake in a pool", () => {
  it("leads with this member's allocation and price, read from the pool record", async () => {
    const shown = poolView();
    vi.spyOn(apiModule.api, "pool").mockResolvedValue({
      ...shown,
      members: [
        ROSA_MEMBERSHIP,
        { ...ROSA_MEMBERSHIP, household_id: "hh_okafor", display_name: "Ada O." },
      ],
    });
    renderHome([shown]);

    expect(await screen.findByText(/Your 2 tubs/)).toBeTruthy();
    // Her own final cost and her own baseline, both server strings.
    expect(screen.getByText(/\$71\.83/)).toBeTruthy();
    expect(screen.getByText(/instead of \$93\.98 buying alone/)).toBeTruthy();
    // Her saving, not the group's.
    expect(screen.getByText("23.5%")).toBeTruthy();
    expect(screen.queryByText("23.6%")).toBeNull();
    expect(screen.getByText(/^Pool found something for you$/)).toBeTruthy();
  });

  it("calls a settled pool the member's own order once it has completed", async () => {
    const done = poolView({ status: "completed" });
    vi.spyOn(apiModule.api, "pool").mockResolvedValue({ ...done, members: [ROSA_MEMBERSHIP] });
    renderHome([done]);

    expect(await screen.findByText(/^Your order$/)).toBeTruthy();
  });

  it("falls back to the group's framing for somebody who is not in the pool", async () => {
    const shown = poolView();
    vi.spyOn(apiModule.api, "pool").mockResolvedValue({
      ...shown,
      members: [{ ...ROSA_MEMBERSHIP, household_id: "hh_okafor", display_name: "Ada O." }],
    });
    renderHome([shown]);

    expect(await screen.findByText(/Pool found overlapping demand/)).toBeTruthy();
    expect(screen.queryByText(/Your 2 tubs/)).toBeNull();
    // The group percentage, since there is no personal one to show.
    expect(screen.getByText("23.6%")).toBeTruthy();
  });

  it("says which invariant is holding instead of showing an empty price", async () => {
    const forming = poolView({
      status: "host_recruiting",
      savings_pct: "",
      savings_display: "",
      is_estimate: true,
      has_final_offer: false,
      funded_units: 0,
    });
    vi.spyOn(apiModule.api, "pool").mockResolvedValue({ ...forming, members: [] });
    renderHome([forming]);

    // A dash here would read as a missing number rather than as a rule being enforced.
    expect(await screen.findByText(/Not priced yet/)).toBeTruthy();
    expect(screen.getByText(/fixed once a fulfiller accepts/)).toBeTruthy();
  });
});

describe("what Pool handled on its own", () => {
  it("reports the server's own coordination counts, unmodified", async () => {
    renderHome([poolView()]);

    expect(await screen.findByText("18")).toBeTruthy();
    expect(screen.getByText("3")).toBeTruthy();
    expect(screen.getByText(/Things Pool did on its own/i)).toBeTruthy();
    expect(screen.getByText(/Times it had to ask a person/i)).toBeTruthy();
    expect(screen.getByText(/8 commitments were made without asking/)).toBeTruthy();
    expect(screen.getByText(/\$266\.32/)).toBeTruthy();
  });

  it("states the premise rather than a row of zeroes before anything has run", async () => {
    renderHome([]);

    expect(await screen.findByText(/Groups anyone organised/i)).toBeTruthy();
    expect(screen.getByText(/Pool is watching/i)).toBeTruthy();
    // No settled-outcome claim can appear before there is an outcome.
    expect(screen.queryByText(/Things Pool did on its own/i)).toBeNull();
  });
});

describe("autonomy, as the member sees it", () => {
  it("leads with whether Pool may commit at all, not with the limits behind it", async () => {
    vi.spyOn(apiModule.api, "member").mockResolvedValue(memberView("ask_me"));
    renderHome([poolView()]);

    expect(await screen.findByText(/No — Pool always asks first/)).toBeTruthy();
    // The limits stay reachable; they are simply not the headline.
    expect(screen.getByText(/Most it may ever spend/)).toBeTruthy();
    expect(screen.getByText("$90.00")).toBeTruthy();
  });

  it("says so when the stored policy does allow Pool to commit", async () => {
    vi.spyOn(apiModule.api, "member").mockResolvedValue(memberView("smart_join"));
    renderHome([poolView()]);

    expect(await screen.findByText(/Yes — when every limit below passes/)).toBeTruthy();
  });
});

describe("why Pool asked", () => {
  it("shows the policy engine's own sentence, never the rule identifier", async () => {
    const decision: Decision = {
      decision_id: "dec_1",
      household_id: "hh_navarro",
      household_name: "Rosa N.",
      pool_id: "pool_shown",
      kind: "approve_final_offer",
      state: "pending",
      facts: {
        product: "Whey protein, vanilla",
        units: 2,
        final_cost_display: "$71.83",
        baseline_display: "$93.98",
        savings_bps: 2357,
        travel_minutes: 3,
        pickup_site: "North Hall lobby",
        blocking_rule: "autonomy_mode",
        policy_checks: [
          {
            rule: "autonomy_mode",
            passed: false,
            detail: "member is on Ask Me — commitment requires explicit approval",
            hard: false,
          },
          { rule: "max_spend", passed: true, detail: "fits", hard: false },
        ],
      },
      created_at: "2026-08-18T12:00:00Z",
      expires_at: "",
    };
    renderHome([poolView()], { decisions: [decision] });

    expect(
      await screen.findByText(
        /Pool asked instead of deciding: member is on Ask Me — commitment requires explicit approval/,
      ),
    ).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/autonomy_mode/);
  });
});

describe("a pool that did not go ahead", () => {
  it("says why where the member is, not only on the record", async () => {
    const failed = poolView({
      status: "failed",
      failure_reason: "The supplier withdrew the offer before the pool locked.",
      savings_pct: "",
      has_final_offer: false,
    });
    vi.spyOn(apiModule.api, "pool").mockResolvedValue({ ...failed, members: [ROSA_MEMBERSHIP] });
    renderHome([failed]);

    expect(await screen.findByText(/^This one did not go ahead$/)).toBeTruthy();
    expect(
      screen.getByText(/The supplier withdrew the offer before the pool locked/),
    ).toBeTruthy();
  });
});
