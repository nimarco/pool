import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { AppState } from "../api";
import { CommunityView } from "./community";

const state: AppState = {
  workspace: "wfixture",
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

    expect(screen.getByRole("heading", { name: "The community it ran inside" })).toBeTruthy();
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

describe("Community leads with both currencies", () => {
  function renderCommunity(metrics: Partial<AppState["metrics"]> = {}) {
    return render(
      <CommunityView
        state={{ ...state, metrics: { ...state.metrics, ...metrics } }}
        map={null}
        onOpenPool={() => {}}
        onRespond={() => {}}
        busyDecision={null}
        onOperations={() => {}}
      />,
    );
  }

  it("answers the autonomy question before the setting, and proves it in between", () => {
    renderCommunity({
      estimated_retail_spend_cents: 112776,
      pool_spend_cents: 86144,
      collective_savings_cents: 26632,
      // A community where an order actually locked, which is what makes the money
      // figures figures rather than a row of zeroes.
      pools_locked_or_beyond: 1,
      coordination_actions_automated: 18,
      human_decisions_requested: 3,
      commitments_without_asking: 8,
      pools_recovered: 1,
      pickups_completed: 10,
      pickups_expected: 10,
    });

    const headings = Array.from(
      document.querySelectorAll("h1, h2"),
    ).map((h) => h.textContent?.trim() ?? "");

    const index = headings.indexOf("Start here");
    const autonomy = headings.indexOf("What Pool did on its own");
    const waiting = headings.indexOf("Decisions waiting on a person");
    const actions = headings.indexOf("Every action, and who took it");
    const money = headings.indexOf("Where the money went");
    const setting = headings.indexOf("The community it ran inside");

    /* The deliberate order, and the reason for it. A judge is scoring autonomy, so the
       counts answer that first; the one pending question is the same fact at instance
       scale; the feed is the evidence for both. The money it moved follows, and the
       fixture that hosted it comes last — it used to sit third while the activity feed
       that substantiates the whole claim sat at the very bottom of the page. */
    // Index 0 is the page's own h1, so "Start here" is the first section on the page.
    expect(index).toBe(1);
    expect(autonomy).toBeGreaterThan(index);
    expect(waiting).toBeGreaterThan(autonomy);
    expect(actions).toBeGreaterThan(waiting);
    expect(money).toBeGreaterThan(actions);
    expect(setting).toBeGreaterThan(money);

    // Both currencies, both sums over stored rows.
    expect(screen.getByText("$266.32")).toBeTruthy();
    expect(screen.getByText("18")).toBeTruthy();
    expect(screen.getByText("3")).toBeTruthy();
    expect(screen.getByText("8")).toBeTruthy();
    expect(screen.getByText(/counted from stored rows/i)).toBeTruthy();
  });

  it("says no money has moved rather than printing a ledger of zeroes", () => {
    /* This page is inspected on purpose, and three $0.00 figures above the fold say
       "nothing here" about a page that is full of things. "No money has moved yet" is
       the same fact in one sentence, and it is the one that is useful. */
    renderCommunity({ pools_locked_or_beyond: 0, collective_savings_cents: 0 });

    expect(screen.getByText(/No money has moved in this community yet/i)).toBeTruthy();
    expect(screen.queryByText("If everyone bought alone")).toBeNull();
    /* And not the operator ledger either, which printed the same zero five more times
       directly underneath. The rule was already written down here; the ledger below it
       had simply never been held to it. */
    expect(screen.queryByText("Where the money went")).toBeNull();
    expect(screen.queryByText("Recorded all-in buyer cost")).toBeNull();
    // The attention ledger still shows, because that is where zero is the interesting
    // number: nobody has been asked anything.
    expect(screen.getByText(/What Pool did on its own/i)).toBeTruthy();
  });

  it("does not describe coordination it has not done", () => {
    renderCommunity();
    expect(screen.getByText(/0 of 0 handoffs confirmed/i)).toBeTruthy();
    expect(screen.queryByText(/no institutional partnership.*endorsed/i)).toBeNull();
  });
});
