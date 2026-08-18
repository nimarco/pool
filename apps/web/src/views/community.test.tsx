import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { AppState } from "../api";
import { CommunityView } from "./community";

const state: AppState = {
  workspace: "wfixture",
  community: {
    id: "community_demo",
    name: "Demo University",
    kind: "university",
    schedule: {},
    platform_fee: { mode: "share_of_savings", bps: 1000, fixed_cents_per_buyer: 0 },
    quote_max_age_hours: 48,
    synthetic: true,
    enablement: {
      verified_members: 20,
      total_memberships: 20,
      verification_methods: ["demo"],
      independent_need_declarers: 13,
      designated_pickup_sites: [
        { id: "site_1", name: "Commons", is_public: true, permission: "demo" },
      ],
    },
  },
  pools: [],
  decisions: [],
  activity: [
    {
      id: "evt_capture",
      kind: "payment_captured",
      summary: "Simulated capture recorded: $50.00 across 1 buyer(s)",
      facts: { provider_mode: "simulated" },
      pool_id: "pool_fixture",
      household_id: null,
      run_id: null,
      at: "2026-08-18T12:00:00Z",
    },
  ],
  runs: [],
  metrics: {
    members_participating: 0,
    pools_total: 0,
    pools_locked_or_beyond: 0,
    pools_recovered: 0,
    estimated_retail_spend_cents: 0,
    pool_spend_cents: 0,
    collective_savings_cents: 0,
    average_buyer_savings_cents: 0,
    merchandise_cents: 0,
    host_compensation_cents: 0,
    payment_processing_cents: 0,
    platform_fee_cents: 0,
    host_jobs: 0,
    host_earnings_cents: 0,
    host_handled_orders: 0,
    pickups_completed: 0,
    pickups_expected: 0,
    no_shows: 0,
    coordination_actions_automated: 0,
    human_decisions_requested: 0,
    commitments_without_asking: 0,
    is_demo_data: true,
  },
  counts: { members: 20, needs: 21, products: 4, standing_hosts: 3, open_issues: 0 },
  is_demo_data: true,
};

afterEach(cleanup);

describe("Community enablement", () => {
  it("shows server-backed boundaries without implying institutional endorsement", () => {
    render(
      <CommunityView
        state={state}
        map={null}
        onOpenPool={() => {}}
        onRespond={() => {}}
        busyDecision={null}
        onOperations={() => {}}
      />,
    );

    expect(screen.getByRole("heading", { name: "How this Community enables Pool" })).toBeTruthy();
    expect(screen.getByText(/20 of 20 fixture memberships verified/i)).toBeTruthy();
    expect(screen.getByText(/13 members declared needs separately/i)).toBeTruthy();
    expect(screen.getByText("Community enables", { selector: "strong" })).toBeTruthy();
    expect(screen.getByText(/handles matching, economics, hosts/i)).toBeTruthy();
    expect(screen.getByText(/does not buy or front inventory/i)).toBeTruthy();
    expect(screen.getByText(/no institutional partnership/i)).toBeTruthy();
    expect(
      (screen.getByText("Who is responsible for what").closest("details") as HTMLDetailsElement)
        .open,
    ).toBe(false);
    expect(screen.getByText(/simulated capture recorded ·/i)).toBeTruthy();
    expect(screen.queryByText(/payment captured ·/i)).toBeNull();
  });
});
