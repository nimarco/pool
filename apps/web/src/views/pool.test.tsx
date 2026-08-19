import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DemoConfig, Health, PoolMember, PoolView } from "../api";
import * as apiModule from "../api";
import { PoolRecord } from "./pool";

const proof = {
  pool_id: "pool_exact",
  created_by_run: "run_exact",
  run_id: "run_exact",
  relation_verified: true as const,
  execution: {
    service: "Amazon Bedrock AgentCore Runtime",
    live: true,
    region: "us-east-1",
  },
  workspace_readback: {
    run_recorded: true as const,
    pool_recorded: true as const,
    same_workspace: true as const,
  },
  run: {
    run_id: "run_exact",
    trigger: "manual_scan",
    outcome: "pool_created",
    iterations: 3,
    tool_calls: ["list_latent_demand", "create_candidate_pool"],
    termination_reason: "candidate_pool_created",
    model_provider: "bedrock",
    model_id: "amazon.nova-lite-v1:0",
    duration_ms: 1000,
    input_tokens: 100,
    output_tokens: 20,
    started_at: "2026-08-18T12:00:00Z",
  },
};

const pool: PoolView = {
  pool_id: "pool_exact",
  created_by_run: "run_exact",
  execution_proof: proof,
  community_id: "community_demo",
  product_id: "prod_whey",
  product_name: "Whey protein",
  unit: "tub",
  brand: "Fixture",
  variant: "",
  image_ref: "",
  supplier: "Synthetic Supply",
  offer_source: "synthetic",
  status: "final_offer",
  pickup_site: "Commons",
  pickup_is_public: true,
  pickup_permission: "demo",
  threshold_units: 24,
  provisional_units: 24,
  funded_units: 20,
  member_count: 10,
  buyer_count: 10,
  progress_pct: 100,
  has_final_offer: true,
  quote_verified_at: "2026-08-18T12:00:00Z",
  failure_reason: "",
  timing: {},
  host: {
    household_id: "hh_host",
    display_name: "Sam H.",
    reward_display: "$82.00",
    handled_orders: 10,
    supplier_distance_km: 4.2,
  },
  economics: null,
  savings_display: "$266.32",
  savings_pct: "23.6%",
  is_estimate: false,
};

const config: DemoConfig = {
  public_demo: true,
  live_agent_available: true,
  live_agent_runtime: "runtime-v4",
  region: "us-east-1",
  max_live_per_session: 1,
  payments: "simulated",
  purchase: "simulated",
};

const health: Health = {
  ok: true,
  repository: "dynamodb",
  routing_provider: "haversine",
  model_provider: "offline",
  model_id: "offline",
  payment_provider: "simulated",
  payment_mode: "simulated",
  purchase_executor: "simulated",
  purchase_simulated: true,
  schedules_enabled: false,
  bounds: {
    max_iterations: 8,
    max_tool_calls: 25,
    max_duplicate_tool_calls: 2,
    workflow_timeout_seconds: 45,
  },
  agent_tools: [],
};

const MEMBERS: PoolMember[] = [
  {
    household_id: "hh_first",
    display_name: "Ada O.",
    units: 3,
    state: "locked",
    path: "smart_join",
    estimated_cost_display: "$107.90",
    final_cost_display: "$107.61",
    baseline_display: "$140.97",
    savings_pct: "23.6%",
    travel_minutes: 2,
    is_host: false,
  },
  {
    household_id: "hh_member",
    display_name: "Rosa N.",
    units: 2,
    state: "locked",
    path: "human_approved",
    estimated_cost_display: "$71.93",
    final_cost_display: "$71.83",
    baseline_display: "$93.98",
    savings_pct: "23.5%",
    travel_minutes: 3,
    is_host: false,
  },
];

function renderPool(entry?: { tab?: string; deep?: string }, overrides: Partial<PoolView> = {}) {
  return render(
    <PoolRecord
      pool={{ ...pool, ...overrides }}
      runs={[proof.run]}
      activity={[]}
      identity={{ id: "hh_member", display_name: "Rosa N." }}
      mine={true}
      entry={entry}
      scenario={null}
      scenarioMs={null}
      running={false}
      health={health}
      demoConfig={config}
      live={null}
      liveBusy={false}
      onBack={() => {}}
      onRefresh={() => {}}
      onRunLive={() => {}}
      onRunScenario={() => {}}
    />,
  );
}

afterEach(cleanup);

describe("pool evidence and financial language", () => {
  it("lands directly on the exact stored execution when requested", () => {
    renderPool({ tab: "activity", deep: "execution" });

    expect(screen.getByRole("heading", { name: "Technical proof for this run" })).toBeTruthy();
    expect(screen.getAllByText("run_exact")).toHaveLength(2);
    expect(screen.getByText("pool_exact")).toBeTruthy();
  });

  it("prioritizes same-run proof on the Activity overview", () => {
    renderPool({ tab: "activity" });

    expect(screen.getByRole("heading", { name: "Technical proof for this run" })).toBeTruthy();
    expect(screen.getByText("Pool created_by_run")).toBeTruthy();
    expect(screen.getByText(/matches run id/i)).toBeTruthy();
    expect(screen.getByText(/verified · run \+ pool present/i)).toBeTruthy();
    expect(screen.getByText("Selected tool sequence")).toBeTruthy();
    expect(screen.getByText("AgentCore live")).toBeTruthy();
    expect(
      screen.getByText(
        /browser → Lambda → AgentCore → Bedrock \/ Strands → typed tools → DynamoDB → browser/i,
      ),
    ).toBeTruthy();
  });

  it("describes host compensation as earned and recorded, not paid out", () => {
    renderPool();

    expect(screen.getByText(/earns/i)).toBeTruthy();
    expect(screen.getByText(/recorded on the simulated transaction/i)).toBeTruthy();
    expect(screen.queryByText(/Paid \$82\.00/)).toBeNull();
  });

  it("says the quote is invented, on the screen where the money is the subject", () => {
    /* This became load-bearing when the products became real. The header of this page
       now reads "Optimum Nutrition · Riverbend Wholesale" above a complete price
       breakdown; a recognisable brand beside an unlabelled wholesale figure implies a
       relationship that does not exist. The About page says it too, but a judge reading
       the economics should not have to go and look. */
    renderPool(
      { tab: "economics" },
      {
        economics: {
          merchandise_cents: 75600,
          host_compensation_cents: 4468,
          other_fulfillment_cents: 0,
          platform_fee_cents: 3270,
          payment_processing_cents: 2806,
          all_in_cents: 86144,
          retail_baseline_cents: 112776,
          gross_savings_cents: 37176,
          net_savings_cents: 26632,
          net_savings_bps: 2362,
          host_is_estimated: false,
          packages: {
            total_units: 24,
            case_units: 12,
            cases: 2,
            units_purchased: 24,
            surplus_units: 0,
            moq_units: 24,
            moq_met: true,
            surplus_resolved: true,
          },
        },
      },
    );

    // JSX wraps this prose across text nodes, so match the rendered document rather
    // than pinning where React chose to break the line.
    const text = (document.body.textContent ?? "").replace(/\s+/g, " ");
    expect(text).toMatch(/this quote, its case size and its minimum are invented/i);
    expect(text).toMatch(/no wholesale relationship exists/i);
    // And it must not undercut the figures themselves, which are genuinely computed.
    expect(text).toMatch(/computed from those terms by Pool's own arithmetic/i);
  });
});

describe("pickup credentials belong to the person asking for one", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiModule.api, "checklist").mockRejectedValue(new Error("not needed"));
  });

  it("offers the signed-in member their own code, not whoever sorts first", async () => {
    const issue = vi
      .spyOn(apiModule.api, "issueCredential")
      .mockResolvedValue({
        pool_id: "pool_exact",
        household_id: "hh_member",
        code: "AAAA1111",
        token: "tok",
        replaced_previous: false,
      });

    renderPool({ tab: "fulfilment" }, { status: "distributing", members: MEMBERS });

    const button = await screen.findByRole("button", { name: /show my code/i });
    // Ada sorts first in the member list; the credential still has to be Rosa's.
    expect(screen.queryByRole("button", { name: /Ada O\.'s code/ })).toBeNull();
    await userEvent.click(button);

    await waitFor(() => expect(issue).toHaveBeenCalled());
    expect(issue.mock.calls[0][1]).toBe("hh_member");
  });

  it("still names the subject when the viewer is not one of the buyers", async () => {
    vi.spyOn(apiModule.api, "issueCredential").mockResolvedValue({
      pool_id: "pool_exact",
      household_id: "hh_first",
      code: "AAAA1111",
      token: "tok",
      replaced_previous: false,
    });

    renderPool({ tab: "fulfilment" }, { status: "distributing", members: [MEMBERS[0]] });

    expect(await screen.findByRole("button", { name: /Issue Ada O\.'s code/ })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /show my code/i })).toBeNull();
  });
});

describe("whose order this is", () => {
  /* Home was already careful about this — "Pool formed an order for coffee, and your
     units were not in this one" — and then one click later this page said
     `Buyers 6 — everyone still in` with no marker at all, which reads as a roster
     somebody is on. The prose fixed the contradiction and the next screen reintroduced
     it. The answer is the server's (`services/relevance.py`), never inferred here. */
  it("says so on the record when the member is not in the order", () => {
    render(
      <PoolRecord
        pool={pool}
        mine={false}
        runs={[]}
        activity={[]}
        identity={{ id: "hh_stranger", display_name: "Someone Else" }}
        scenario={null}
        scenarioMs={null}
        running={false}
        health={health}
        demoConfig={config}
        live={null}
        liveBusy={false}
        onBack={() => {}}
        onRefresh={() => {}}
        onRunLive={() => {}}
        onRunScenario={() => {}}
      />,
    );
    expect(screen.getByText(/You are not in this order/i)).toBeTruthy();
    expect(screen.queryByText(/You are in this order/i)).toBeNull();
  });

  it("says so either way, so an absent marker is never the flattering reading", () => {
    renderPool();
    expect(screen.getByText(/You are in this order/i)).toBeTruthy();
  });
});
