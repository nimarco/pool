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

import {
  AppState,
  Decision,
  MemberView,
  NeedOutlook,
  PersonalOpportunity,
  PoolMember,
  PoolView,
} from "../api";
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

/** The server's answer to "which pool is mine, and why". Home reads this and never
 *  infers it from the pool list — the whole point of the fix these tests pin. */
function opportunityIn(pool: PoolView, needId = "need_rosa_whey"): PersonalOpportunity {
  return {
    pool_id: pool.pool_id,
    status: pool.status,
    product_id: pool.product_id,
    participation_state: "authorized",
    units: 2,
    need_id: needId,
    declared_product_id: pool.product_id,
    is_exact_product: true,
    declared_product_name: "",
    substitution_disclosed: false,
  };
}

function memberView(
  options: {
    mode?: string;
    opportunity?: PersonalOpportunity | null;
    outlook?: NeedOutlook[];
    standing?: apiModule.StandingDemand[];
    otherPoolIds?: string[];
  } = {},
): MemberView {
  return {
    id: "hh_navarro",
    display_name: "Rosa N.",
    zone: "Campus core",
    opportunity: options.opportunity ?? null,
    other_pool_ids: options.otherPoolIds ?? [],
    standing_demand: options.standing ?? [],
    needs_outlook: options.outlook ?? [],
    community_membership: null,
    has_payment_method: true,
    autonomy_display: {
      mode: options.mode ?? "ask_me",
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
  options: {
    onShowAgent?: (poolId: string) => void;
    onWhy?: (needId: string, productName: string) => void;
    decisions?: Decision[];
    /** Defaults to "this member is in the first pool", which is the ordinary state
     *  every pre-existing assertion here was written against. Pass `null` for a member
     *  the server has said nothing about yet. */
    member?: MemberView | null;
    report?: apiModule.RunReport | null;
    onOpenPool?: (id: string) => void;
  } = {},
) {
  const member =
    "member" in options
      ? options.member ?? null
      : memberView({ opportunity: pools[0] ? opportunityIn(pools[0]) : null });
  return render(
    <Home
      state={appState(pools, options.decisions ?? [])}
      identity={ROSA}
      member={member}
      report={options.report ?? null}
      running={false}
      busyDecision={null}
      onFind={() => {}}
      onOpenPool={options.onOpenPool ?? (() => {})}
      onRespond={() => {}}
      onShowAgent={options.onShowAgent ?? (() => {})}
      onStartNeed={() => {}}
      onWhy={options.onWhy ?? (() => {})}
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
  vi.spyOn(apiModule.api, "hostOpportunities").mockRejectedValue(new Error("not needed"));
  vi.spyOn(apiModule.api, "pool").mockRejectedValue(new Error("not needed"));
});

describe("the proof action on Home", () => {
  it("opens the proof for the pool the card is showing, not for whichever pool sorts first", async () => {
    const shown = poolView();
    const onShowAgent = vi.fn();
    /* No declaration named on the opportunity, which is the case where the card still
       falls back to the run's execution trace. When the server *can* name one, the card
       offers "Why this order?" instead — the same evidence with the member-facing answer
       in front of it, asserted below. */
    renderHome([shown, OTHER], {
      onShowAgent,
      member: memberView({ opportunity: { ...opportunityIn(shown), need_id: "" } }),
    });

    // Whatever the card drew is the pool whose proof must open. The card appears once
    // the server has said which pool is this member's, so this waits for that answer
    // rather than for React's first paint.
    expect(await screen.findByText(shown.product_name)).toBeTruthy();
    // The other pool is on screen, but as the community's — never in this member's
    // slot, and with no proof button of its own competing with theirs.
    const elsewhere = document.querySelector(".panel-muted") as HTMLElement;
    expect(elsewhere.textContent).toMatch(OTHER.product_name);
    expect(elsewhere.textContent).toMatch(/You are not part of this order/);

    await userEvent.click(
      screen.getByRole("button", { name: /technical proof for this run/i }),
    );

    await waitFor(() => expect(onShowAgent).toHaveBeenCalledTimes(1));
    expect(onShowAgent).toHaveBeenCalledWith(shown.pool_id);
    expect(onShowAgent).not.toHaveBeenCalledWith(OTHER.pool_id);
  });

  it("asks why this order, for the declaration that caused it", async () => {
    const shown = poolView();
    const onWhy = vi.fn();
    renderHome([shown], {
      onWhy,
      member: memberView({
        opportunity: { ...opportunityIn(shown), need_id: "need_rosa_whey" },
      }),
    });

    await userEvent.click(screen.getByRole("button", { name: /why this order/i }));
    /* The unit travels with the declaration. The explanation counts in it, and the only
       screen that knows the member declared tubs rather than bags is this one — the
       coordination payload carries quantities and not the noun for them. */
    expect(onWhy).toHaveBeenCalledWith("need_rosa_whey", shown.product_name, shown.unit);
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

    expect(await screen.findByText(/your 2 tubs/)).toBeTruthy();
    // Her own final cost and her own baseline, both server strings, each in its own slot.
    expect(screen.getByText("$71.83")).toBeTruthy();
    expect(screen.getByText("What you pay")).toBeTruthy();
    expect(screen.getByText("$93.98")).toBeTruthy();
    expect(screen.getByText("Buying alone")).toBeTruthy();
    // Her saving, not the group's.
    expect(screen.getByText(/you save 23\.5%/)).toBeTruthy();
    expect(screen.queryByText(/23\.6%/)).toBeNull();
    expect(screen.getByText(/^Pool found something for you$/)).toBeTruthy();
  });

  it("calls a settled pool the member's own order once it has completed", async () => {
    const done = poolView({ status: "completed" });
    vi.spyOn(apiModule.api, "pool").mockResolvedValue({ ...done, members: [ROSA_MEMBERSHIP] });
    renderHome([done]);

    expect(await screen.findByText(/^Your order$/)).toBeTruthy();
  });

  it("shows the group's figures if the pool record has not caught up yet", async () => {
    /* The server has said this pool is theirs; the membership read has not landed.
       Leading with the group's numbers is the honest interim — inventing a personal
       price would not be. */
    const shown = poolView();
    vi.spyOn(apiModule.api, "pool").mockResolvedValue({
      ...shown,
      members: [{ ...ROSA_MEMBERSHIP, household_id: "hh_okafor", display_name: "Ada O." }],
    });
    renderHome([shown]);

    expect(await screen.findByText(/Pool found overlapping demand/)).toBeTruthy();
    expect(screen.queryByText(/your 2 tubs/)).toBeNull();
    expect(screen.getByText(/23\.6%/)).toBeTruthy();
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
    expect(screen.getByText(/fixed once a host accepts/)).toBeTruthy();
  });
});

describe("the standing facts about a forming order", () => {
  it("states the minimum, the open job and the untouched card as three separate facts", async () => {
    const forming = poolView({
      status: "forming",
      provisional_units: 18,
      threshold_units: 12,
      funded_units: 0,
      host: null,
    });
    vi.spyOn(apiModule.api, "pool").mockResolvedValue({ ...forming, members: [ROSA_MEMBERSHIP] });
    renderHome([forming]);

    /* Three list items rather than one sentence. The two a member can act on used to be
       interior clauses of a wrapped 12px line, which is where they were being missed. */
    const minimum = await screen.findByText(/18 tubs — past the supplier's 12-tub minimum/);
    const facts = minimum.closest("ul");
    expect(facts).toBeTruthy();
    expect(
      [...(facts as HTMLElement).querySelectorAll("li")].map((li) => li.textContent),
    ).toEqual([
      "18 tubs — past the supplier's 12-tub minimum",
      "Host needed",
      "Nothing charged",
    ]);
  });

  it("says what the open job is, because 'host needed' assumes the reader knows", async () => {
    const forming = poolView({ status: "forming", funded_units: 0, host: null });
    vi.spyOn(apiModule.api, "pool").mockResolvedValue({ ...forming, members: [ROSA_MEMBERSHIP] });
    renderHome([forming]);

    expect(await screen.findByText(/A neighbour collects the order, runs the pickup/)).toBeTruthy();
  });

  it("drops the note once somebody is carrying it, and names them instead", async () => {
    const carried = poolView({
      status: "forming",
      funded_units: 0,
      host: {
        household_id: "hh_okafor",
        display_name: "Ada O.",
        reward_display: "$14.00",
        handled_orders: 2,
        supplier_distance_km: 3.1,
      },
    });
    vi.spyOn(apiModule.api, "pool").mockResolvedValue({ ...carried, members: [ROSA_MEMBERSHIP] });
    renderHome([carried]);

    expect(await screen.findByText("Ada O. is carrying it")).toBeTruthy();
    expect(screen.queryByText(/A neighbour collects the order/)).toBeNull();
  });

  it("does not explain a host's pay twice on one card", async () => {
    /* The figure caption and the host note were both carrying the same reason, 200px
       apart. While the job is open the note has it; the caption only says the price is
       not settled. */
    const forming = poolView({
      status: "forming",
      savings_pct: "",
      has_final_offer: false,
      funded_units: 0,
      host: null,
    });
    vi.spyOn(apiModule.api, "pool").mockResolvedValue({
      ...forming,
      members: [{ ...ROSA_MEMBERSHIP, final_cost_display: "", savings_pct: "" }],
    });
    renderHome([forming]);

    expect(await screen.findByText("not final yet")).toBeTruthy();
    expect(screen.queryByText(/not final — a host's pay is part of the price/)).toBeNull();
  });
});

describe("a pool buying an authorised substitute", () => {
  it("says what the member actually declared, since the card shows the other product", async () => {
    const shown = poolView();
    vi.spyOn(apiModule.api, "pool").mockResolvedValue({ ...shown, members: [ROSA_MEMBERSHIP] });
    renderHome([shown], {
      member: memberView({
        opportunity: {
          ...opportunityIn(shown),
          product_id: "prod_whey_vanilla",
          declared_product_id: "prod_whey_chocolate",
          is_exact_product: false,
          declared_product_name: "Gold Standard 100% Whey",
          substitution_disclosed: true,
        },
      }),
    });

    expect(await screen.findByText(/A substitute for the/)).toBeTruthy();
    expect(screen.getByText("Gold Standard 100% Whey")).toBeTruthy();
  });

  it("says nothing of the kind when the member named a rule rather than a product", async () => {
    /* A different bag is not a *substitute* for somebody who declared "whole bean,
       caffeinated, medium or dark" — it is the thing they asked for. The server decides
       that (`relevance.substitution_disclosed`), because reading it off the two product
       ids was wrong for exactly this case and for family declarations (§21). */
    const shown = poolView();
    vi.spyOn(apiModule.api, "pool").mockResolvedValue({ ...shown, members: [ROSA_MEMBERSHIP] });
    renderHome([shown], {
      member: memberView({
        opportunity: {
          ...opportunityIn(shown),
          product_id: "prod_rc_harbourstone_dark",
          declared_product_id: "prod_rc_kestrel_medium",
          is_exact_product: false,
          declared_product_name: "Whole bean coffee, 2 lb",
          substitution_disclosed: false,
        },
      }),
    });

    await screen.findByText(/Pool found something for you|Forming/);
    expect(screen.queryByText(/A substitute for the/)).toBeNull();
  });

  it("says nothing extra when the pool buys exactly what was declared", async () => {
    const shown = poolView();
    vi.spyOn(apiModule.api, "pool").mockResolvedValue({ ...shown, members: [ROSA_MEMBERSHIP] });
    renderHome([shown]);

    expect(await screen.findByText(/your 2 tubs/)).toBeTruthy();
    expect(screen.queryByText(/A substitute for the/)).toBeNull();
  });
});

describe("a pool that belongs to somebody else", () => {
  /* The reported bug, in the interface. A member declared coffee, the coordinator
     correctly formed a whey order out of ten *other* students' declarations, and Home
     led with it because it led with `state.pools[0]`. Which pool is this member's is
     the server's answer now, and "none" is one of the answers it may give. */
  const COFFEE_STANDING: apiModule.StandingDemand = {
    need_id: "need_rosa_coffee",
    product_id: "prod_coffee_beans",
    product_name: "Pike Place Medium Roast",
    unit: "bag",
    my_units: 3,
    compatible_members: 5,
    compatible_units: 12,
    minimum_units: 18,
    has_supplier: true,
    sourceable_product_id: "",
    sourceable_product_name: "",
  };

  function declinedReport(): apiModule.RunReport {
    return {
      run_id: "run_1",
      trigger: "member_scan",
      objective_kind: "member",
      outcome: "no_action",
      at: "2026-08-19T10:00:00Z",
      model_provider: "offline",
      is_mine: true,
      evaluated_product_ids: ["prod_coffee_beans"],
      results: [
        {
          need_id: "need_rosa_coffee",
          product_id: "prod_coffee_beans",
          product_name: "Pike Place Medium Roast",
          quantity: 3,
          unit: "bag",
          result: "declined",
          pool_id: "",
          units: 0,
          reason_code: "below_minimum",
          is_exact_product: true,
          declared_product_name: "",
          headline:
            "15 compatible bags were declared near you, and the supplier will not sell " +
            "fewer than 18.",
          facts: ["Your declaration stays standing, and Pool keeps watching."],
        },
      ],
    };
  }

  it("never presents it as this member's result", async () => {
    renderHome([poolView()], {
      member: memberView({ opportunity: null, standing: [COFFEE_STANDING] }),
      report: declinedReport(),
    });

    expect(await screen.findByText(/What Pool is watching/)).toBeTruthy();
    expect(screen.queryByText(/Pool found something for you/)).toBeNull();
    expect(screen.queryByText(/Pool found overlapping demand/)).toBeNull();
    // No figure from the unrelated pool is presented as this member's saving.
    expect(screen.queryByText("23.6%")).toBeNull();
    expect(screen.queryByText(/you save/)).toBeNull();
    /* And the community's own sums are not here at all any more, which is the stronger
       version of the same rule. Home used to carry three coordination metrics and a
       money figure summed over every member — true, labelled, and still an answer to a
       question this member did not ask. A consumer surface stays personally scoped
       (AGENTS.md §8); those figures live where judge proof lives. */
    expect(screen.queryByText(/What Pool did across/)).toBeNull();
    expect(screen.queryByText(/Things Pool did on its own/)).toBeNull();
    expect(screen.queryByText(/Kept in the community/)).toBeNull();
  });

  it("states what the run actually established, and dates it", async () => {
    renderHome([], {
      member: memberView({ opportunity: null, standing: [COFFEE_STANDING] }),
      report: declinedReport(),
    });

    /* The server's sentence, passed through — not a shrug, and not recomputed here. It
       now sits on the row it is about, under the current state and marked with the time
       the run happened, because "what that run found" and "what is true now" are two
       claims and the changing-world sequence turns on them not being merged. */
    const row = (await screen.findByText(/6 people near you/)).closest(
      ".watch-row",
    ) as HTMLElement;
    expect(row.textContent).toMatch(/Last checked/);
    expect(row.textContent).toContain(declinedReport().results[0].headline);
    expect(screen.getAllByText(COFFEE_STANDING.product_name).length).toBeGreaterThan(0);
  });

  it("names the community's order as the community's, and can open it", async () => {
    const onOpenPool = vi.fn();
    renderHome([poolView()], {
      member: memberView({ opportunity: null, standing: [COFFEE_STANDING] }),
      onOpenPool,
    });

    expect(await screen.findByText(/You are not part of this order/)).toBeTruthy();
    expect(screen.getByText(/Whey protein, vanilla/)).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: /see it/i }));
    expect(onOpenPool).toHaveBeenCalledWith("pool_shown");
  });

  it("never calls a pool the member *is* in somebody else's", async () => {
    /* A member can be in a settled order and a live one at once. Excluding only the
       pool being led with would tell them "you are not in it" about the other. */
    const settled = poolView({ pool_id: "pool_mine_2", product_name: "Energy drink" });
    renderHome([poolView(), settled], {
      member: memberView({
        opportunity: null,
        standing: [COFFEE_STANDING],
        otherPoolIds: ["pool_mine_2"],
      }),
    });

    expect(await screen.findByText(/You are not part of this order/)).toBeTruthy();
    expect(screen.queryByText("Energy drink")).toBeNull();
    expect(screen.getByText(/Whey protein, vanilla/)).toBeTruthy();
  });
});

describe("before Pool has run", () => {
  const STANDING: apiModule.StandingDemand = {
    need_id: "need_rosa_coffee",
    product_id: "prod_coffee_beans",
    product_name: "Pike Place Medium Roast",
    unit: "bag",
    my_units: 3,
    compatible_members: 5,
    compatible_units: 15,
    minimum_units: 18,
    has_supplier: true,
    sourceable_product_id: "",
    sourceable_product_name: "",
  };

  /** The outlook the server sends alongside the demand. Home reads the blocker from
   *  here rather than composing its own, so the sentence a member sees on Home is the
   *  same sentence, from the same evaluator, as the one on their list of things. */
  function outlookFor(
    overrides: Partial<apiModule.NeedOutlook> = {},
  ): apiModule.NeedOutlook {
    return {
      need_id: STANDING.need_id,
      product_id: STANDING.product_id,
      product_name: STANDING.product_name,
      state: "short",
      reason:
        "Not enough of it yet: 18 bags declared nearby, and the supplier will not sell fewer than 24.",
      pool_id: "",
      units_needed: 24,
      units_available: 18,
      status: "watching",
      headline: "Not enough demand yet",
      blocker: "",
      ...overrides,
    };
  }

  it("poses the question rather than answering it", async () => {
    /* This slot used to draw the canonical whey arithmetic — eight due, eighteen units,
       two pulled forward, twenty-four — before the run. That told a judge the answer and
       then invited them to watch Pool produce it. What belongs here is the input. */
    renderHome([], {
      member: memberView({
        opportunity: null,
        standing: [STANDING],
        outlook: [outlookFor()],
      }),
    });

    expect(await screen.findByText(/What Pool is watching/)).toBeTruthy();
    const row = document.querySelector(".watch-row") as HTMLElement;
    /* The demand this member did not organise, and the quantity that is missing — as the
       two numbers themselves rather than as a sentence containing them. Both come from
       the outlook the server sent, so they are the values it built its own sentence
       from. */
    expect(row.textContent).toMatch(/6\s*people near you/);
    expect(row.textContent).toMatch(/18\s*bags declared/);
    expect(row.textContent).toMatch(/24\s*required/);
    // The state, in the five-word grammar, with its reason beside it.
    expect(row.textContent).toMatch(/Watching/);
    expect(row.textContent).toMatch(/Not enough demand yet/);
    // No verdict, because none has been earned.
    expect(screen.queryByText(/Worth pooling now/)).toBeNull();
    expect(screen.queryByText(/Nothing worth coordinating yet/)).toBeNull();
    // Nothing dated, because no run has happened.
    expect(row.textContent).not.toMatch(/Last checked/);
    expect(screen.getByRole("button", { name: /ask pool to check now/i })).toBeTruthy();
  });

  it("says plainly when Pool has no supplier for something", async () => {
    renderHome([], {
      member: memberView({
        opportunity: null,
        standing: [
          {
            ...STANDING,
            product_name: "Cardamom pods, 500g",
            has_supplier: false,
            compatible_members: 0,
            compatible_units: 0,
            minimum_units: 0,
          },
        ],
        outlook: [
          outlookFor({
            product_name: "Cardamom pods, 500g",
            state: "no_supply",
            headline: "No verified supplier yet",
            reason: "No supplier Pool has verified sells this in bulk yet.",
          }),
        ],
      }),
    });

    expect(
      await screen.findByText(/No supplier Pool has verified sells this in bulk yet/),
    ).toBeTruthy();
    expect(screen.getByText(/Nobody else near you buys this yet/)).toBeTruthy();
  });

  /* The distinction the whole watching row exists to draw, and the reason demand sits
     above the blocker. Both rows have no supplier; only one of them has nobody behind
     it, and the screen used to say the same thing about both. */
  it("still shows the demand when what is missing is a supplier, not people", async () => {
    renderHome([], {
      member: memberView({
        opportunity: null,
        standing: [
          {
            ...STANDING,
            product_name: "Jasmine rice, 5 lb",
            unit: "bag",
            my_units: 2,
            has_supplier: false,
            compatible_members: 6,
            compatible_units: 22,
            minimum_units: 0,
          },
        ],
        outlook: [
          outlookFor({
            product_name: "Jasmine rice, 5 lb",
            state: "no_supply",
            headline: "No verified supplier yet",
            reason:
              "6 other members near you already buy this — 22 bags standing. No supplier Pool has verified sells it in bulk yet.",
            units_needed: 0,
          }),
        ],
      }),
    });

    const row = (await screen.findByText(/7 people near you/)).closest(
      ".watch-row",
    ) as HTMLElement;
    // The demand, first, and as a number of people rather than a claim about supply.
    expect(row.textContent).toMatch(/24 bags standing/);
    // Then the blocker, as a blocker.
    expect(row.textContent).toMatch(/No supplier Pool has verified sells it in bulk yet/);
    // And no supplier minimum is invented to sit beside it.
    expect(row.textContent).not.toMatch(/will not sell fewer than/);
  });

  it("discloses a substitute before anything is bought, not after", async () => {
    renderHome([], {
      member: memberView({
        opportunity: null,
        standing: [
          {
            ...STANDING,
            sourceable_product_id: "prod_whey_vanilla",
            sourceable_product_name: "100% Whey Protein",
          },
        ],
        outlook: [outlookFor()],
      }),
    });

    expect(
      await screen.findByText(/would buy 100% Whey Protein, which your substitution rule allows/),
    ).toBeTruthy();
  });
});

describe("Home answers one question, and it is this member's", () => {
  /* These figures used to be here too, in a `Across Demo University` block that read
     `Members 24 / Standing needs 39 / Groups anyone organised 0` for a new account and
     three coordination counters plus a money total afterwards. Every one of them is a
     sum over the whole Community, and every one of them is still asserted — on the
     Community surface, where `community.test.tsx` pins the same 18, 3, 8 and $266.32
     along with the order they appear in. Two copies of one assertion is not twice the
     coverage; it is one place for the number to be right and another for it to be in
     front of somebody who did not ask.

     So what is pinned here is the boundary itself: Home is personally scoped, and a
     community aggregate appearing on it is a regression (AGENTS.md §8). */
  it("carries no community-wide aggregate, before or after a run", async () => {
    renderHome([poolView()]);
    await screen.findByRole("heading", { level: 1 });

    for (const community of [
      /Things Pool did on its own/i,
      /Actions Pool took on its own/i,
      /Times it had to ask a person/i,
      /commitments were made without asking/i,
      /Kept in the community/i,
      /Groups anyone organised/i,
      /Standing needs/i,
    ]) {
      expect(screen.queryByText(community)).toBeNull();
    }
    expect(screen.queryByText(/\$266\.32/)).toBeNull();
  });

  it("lists each thing the member buys exactly once", async () => {
    /* The shape this rebuild exists to remove. After a run, two declarations produced
       six rows: a verdict each under `POOL CHECKED`, demand and a blocker each under
       `Still standing`, and a cadence each under `What you buy anyway` — which was also
       the whole of the Needs page. */
    const standing: apiModule.StandingDemand[] = [
      {
        need_id: "need_a",
        product_id: "prod_coffee_beans",
        product_name: "Coffee",
        unit: "bag",
        my_units: 2,
        compatible_members: 6,
        compatible_units: 22,
        minimum_units: 16,
        has_supplier: true,
        sourceable_product_id: "",
        sourceable_product_name: "",
      },
      {
        need_id: "need_b",
        product_id: "prod_paper_towels",
        product_name: "Paper towels",
        unit: "pack",
        my_units: 2,
        compatible_members: 2,
        compatible_units: 4,
        minimum_units: 48,
        has_supplier: true,
        sourceable_product_id: "",
        sourceable_product_name: "",
      },
    ];
    renderHome([], { member: memberView({ opportunity: null, standing }) });

    await screen.findByText(/What Pool is watching/);
    expect(document.querySelectorAll(".watch-row")).toHaveLength(2);
    expect(screen.getAllByText("Coffee")).toHaveLength(1);
    expect(screen.getAllByText("Paper towels")).toHaveLength(1);
    // And the member's own list is a page, not a second copy of itself.
    expect(screen.queryByText(/What you buy anyway/)).toBeNull();
  });
});

describe("autonomy, as the member sees it", () => {
  it("leads with whether Pool may commit at all, not with the limits behind it", async () => {
    renderHome([poolView()], {
      member: memberView({ mode: "ask_me", opportunity: opportunityIn(poolView()) }),
    });

    expect(await screen.findByText(/No — Pool always asks first/)).toBeTruthy();
    // The limits stay reachable; they are simply not the headline.
    expect(screen.getByText(/Most it may ever spend/)).toBeTruthy();
    expect(screen.getByText("$90.00")).toBeTruthy();
  });

  it("says so when the stored policy does allow Pool to commit", async () => {
    renderHome([poolView()], {
      member: memberView({ mode: "smart_join", opportunity: opportunityIn(poolView()) }),
    });

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

describe("an order that filled without this member", () => {
  /* "Formed but not for you" is not "nothing happened", and it was rendering as both at
     once: the row vanished from Home entirely — because a `formed_excluded` result
     carries the pool id of the order that filled *without* it, which the standing filter
     treated as served — while an unrelated card announced that an order existed
     elsewhere. The declaration a member asked Pool to watch was nowhere on the screen. */
  const STANDING: apiModule.StandingDemand = {
    need_id: "need_rosa_coffee",
    product_id: "prod_coffee_beans",
    product_name: "Pike Place Medium Roast",
    unit: "bag",
    my_units: 2,
    compatible_members: 0,
    compatible_units: 0,
    minimum_units: 18,
    has_supplier: true,
    sourceable_product_id: "",
    sourceable_product_name: "",
  };

  function excludedRun(): apiModule.RunReport {
    return {
      run_id: "run_x",
      trigger: "member_scan",
      objective_kind: "member",
      outcome: "pool_created",
      at: "2026-08-19T10:00:00Z",
      model_provider: "offline",
      is_mine: true,
      evaluated_product_ids: ["prod_coffee_beans"],
      results: [
        {
          need_id: "need_rosa_coffee",
          product_id: "prod_coffee_beans",
          product_name: "Pike Place Medium Roast",
          quantity: 2,
          unit: "bag",
          result: "formed_excluded",
          pool_id: "pool_shown",
          units: 0,
          reason_code: "",
          is_exact_product: true,
          declared_product_name: "",
          headline:
            "Pool formed an order for Pike Place Medium Roast, and your units were not in this one.",
          facts: [],
        },
      ],
    };
  }

  it("keeps the declaration on the screen, standing", async () => {
    renderHome([poolView()], {
      member: memberView({
        opportunity: null,
        standing: [STANDING],
        outlook: [
          {
            need_id: "need_rosa_coffee",
            product_id: "prod_coffee_beans",
            product_name: "Pike Place Medium Roast",
            state: "case_boundary",
            reason:
              "There is a group order for this, but it filled to a whole case without your units this time.",
            blocker: "",
            pool_id: "pool_shown",
            units_needed: 18,
            units_available: 18,
            status: "watching",
            headline: "An order filled without your units",
            detail: { case_units: 6, cases: 3, units_purchased: 18, surplus_units: 0, your_units: 2 },
          },
        ],
      }),
      report: excludedRun(),
    });

    await screen.findByText(/What Pool is watching/);
    const row = document.querySelector(".watch-row") as HTMLElement;
    expect(row).toBeTruthy();
    expect(row.textContent).toMatch(/Pike Place Medium Roast/);
    expect(row.textContent).toMatch(/An order filled without your units/);

    /* And the boundary is drawn rather than described, because "it filled 3 complete
       cases exactly and your units did not fit inside the boundary" is the hardest thing
       this product asks anybody to picture. */
    const fit = row.querySelector(".casefit") as HTMLElement;
    expect(fit).toBeTruthy();
    expect(fit.querySelectorAll(".casefit-case:not(.is-left)")).toHaveLength(3);
    expect(fit.querySelectorAll(".casefit-unit.is-standing")).toHaveLength(2);
    expect(fit.getAttribute("aria-label")).toMatch(/3 full cases, 18 bags, nothing left over/);
  });

  it("does not tell them nobody buys it, when everybody who does is in the order", async () => {
    /* `compatible_members` counts households *not* already in a live pool for the
       product, which is the right number for "how much demand is available" and the
       wrong sentence here — it renders as "nobody else near you buys this yet" to the
       one person whose neighbours just bought it. */
    renderHome([poolView()], {
      member: memberView({
        opportunity: null,
        standing: [STANDING],
        outlook: [
          {
            need_id: "need_rosa_coffee",
            product_id: "prod_coffee_beans",
            product_name: "Pike Place Medium Roast",
            state: "not_in_round",
            reason: "A group order for this has already formed.",
            blocker: "",
            pool_id: "pool_shown",
            units_needed: 18,
            units_available: 18,
            status: "watching",
            headline: "An order filled without your units",
          },
        ],
      }),
      report: excludedRun(),
    });

    await screen.findByText(/What Pool is watching/);
    expect(screen.queryByText(/Nobody else near you buys this yet/)).toBeNull();
  });
});

describe("motion reports a change and never an arrival", () => {
  /* The whole consumer motion budget, and the rule that makes it honest. The
     changing-world beat is the product's strongest argument — one declaration answered
     three ways as supplier facts arrive — so the moment the answer changes is worth
     marking. Marking the *arrival* of a row would be marking something that did not
     happen: nothing arrived, a row was re-read. */
  const COFFEE: apiModule.StandingDemand = {
    need_id: "need_rosa_coffee",
    product_id: "prod_coffee_beans",
    product_name: "Pike Place Medium Roast",
    unit: "bag",
    my_units: 2,
    compatible_members: 6,
    compatible_units: 6,
    minimum_units: 18,
    has_supplier: false,
    sourceable_product_id: "",
    sourceable_product_name: "",
  };

  const watching = () =>
    renderHome([], {
      member: memberView({
        opportunity: null,
        standing: [COFFEE],
        outlook: [
          {
            need_id: "need_rosa_coffee",
            product_id: "prod_coffee_beans",
            product_name: "Pike Place Medium Roast",
            state: "no_supply",
            reason: "No verified supplier yet.",
            blocker: "No supplier Pool has verified sells this in bulk yet.",
            pool_id: "",
            units_needed: 18,
            units_available: 6,
            status: "watching",
            headline: "No verified supplier yet",
          },
        ],
      }),
    });

  it("does not animate a state on first paint", async () => {
    watching();
    await screen.findByText(/What Pool is watching/);
    expect(document.querySelector(".status-chip")).toBeTruthy();
    expect(document.querySelector(".status-chip.just-changed")).toBeNull();
  });

  it("keeps the state and its reason readable as text, so motion is never the carrier", async () => {
    watching();
    await screen.findByText(/What Pool is watching/);
    const chip = document.querySelector(".status-chip");
    expect((chip?.querySelector(".status-word")?.textContent ?? "").length).toBeGreaterThan(0);
    expect((chip?.querySelector(".status-reason")?.textContent ?? "").length).toBeGreaterThan(0);
  });
});
