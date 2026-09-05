/** The self-guided verification path, from a cold session, end to end in one file.
 *
 *  Every claim `/verify` makes is about a sequence — arrive, become a member, declare
 *  what you buy, read why — and until now each step was tested in isolation while the
 *  path between them was only ever walked by hand. The two defects that mattered most
 *  were both properties of the *path*: the first screen offered a scripted walkthrough to
 *  the one visitor who had explicitly chosen not to watch one, and the quantity field
 *  started on a number that produces a truthful no-action in this fixture, so a sceptic
 *  following the page's own instructions could land on "nothing happened" and reasonably
 *  read it as broken software.
 *
 *  This pins the sequence at component level rather than in a browser. No automation
 *  framework is added for it: the surfaces below are the real ones, the API calls are the
 *  real call sites, and what a browser would add here is a rendering engine rather than a
 *  fact. The deployed path is separately walked by hand before release
 *  (`docs/RELEASE_CHECKLIST.md`).
 */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as apiModule from "../api";
import { Onboarding } from "./onboarding";
import { Verify } from "./verify";
import { WhyThisOrder } from "./why";

const PLACE: apiModule.Place = {
  community_id: "comm_demo_university",
  community_name: "Demo University",
  member_count: 24,
  pickup_site_count: 4,
  synthetic: true,
};

const FRESH: apiModule.Consumer = {
  household_id: "hh_navarro",
  display_name: "You",
  onboarded: false,
  has_payment_method: false,
  autonomy_mode: "ask_me",
  place: PLACE,
};

const KESTREL: apiModule.ProductCandidate = {
  product_id: "prod_rc_kestrel_medium",
  name: "Kestrel Medium Roast",
  brand: "Kestrel",
  variant: "Medium",
  display_size: "340 g",
  unit: "bag",
  category: "coffee",
  image_ref: "",
};

const ATTRIBUTION: apiModule.CatalogAttribution = {
  source: "Open Food Facts",
  source_url: "https://openfoodfacts.org",
  data_license: "ODbL-1.0",
  image_license: "CC-BY-SA-4.0",
  credit: "Open Food Facts contributors",
  snapshot: "2026-08-19",
};

const HEALTH: apiModule.Health = {
  ok: true,
  repository: "dynamodb",
  routing_provider: "deterministic",
  model_provider: "offline",
  model_id: "offline-deterministic-planner",
  payment_provider: "simulated",
  payment_mode: "simulated",
  purchase_executor: "simulated",
  purchase_simulated: true,
  schedules_enabled: false,
  bounds: {
    max_iterations: 8,
    max_tool_calls: 25,
    max_duplicate_tool_calls: 2,
    workflow_timeout_seconds: 120,
  },
  agent_tools: [],
};

/** Everything the setup screens call, stubbed at the API boundary and nowhere lower. */
function stubApi() {
  vi.spyOn(apiModule.api, "setVerifyScope").mockImplementation(() => {});
  vi.spyOn(apiModule.api, "searchProducts").mockResolvedValue({
    query: "kestrel",
    groups: [],
    results: [KESTREL],
    attribution: ATTRIBUTION,
  });
  vi.spyOn(apiModule.api, "productPreferences").mockResolvedValue({
    product_id: KESTREL.product_id,
    family: "roast_coffee",
    family_noun: "coffee",
    schema_version: 1,
    questions: [],
  });
  vi.spyOn(apiModule.api, "declareNeed").mockResolvedValue({} as never);
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
  vi.spyOn(apiModule.api, "saveOwnPaymentMethod").mockResolvedValue({
    ok: true,
    has_payment_method: true,
  });
  vi.spyOn(apiModule.api, "completeOnboarding").mockResolvedValue({
    ...FRESH,
    display_name: "Jordan",
    onboarded: true,
  });
}

/** In the verification world, or in the ordinary product. The only difference these
 *  tests care about, and the one both fixes are scoped by. */
function inVerifyScope(on: boolean) {
  vi.spyOn(apiModule.api, "inVerifyScope").mockReturnValue(on);
}

async function nameYourself(name = "Jordan") {
  await userEvent.type(screen.getByLabelText(/your name/i), name);
  await userEvent.click(screen.getByRole("button", { name: /continue/i }));
}

async function chooseTheCoffee() {
  await userEvent.type(screen.getByLabelText(/what do you buy/i), "kestrel");
  await userEvent.click(await screen.findByRole("option", { name: /Kestrel Medium Roast/i }));
}

beforeEach(() => {
  vi.restoreAllMocks();
  stubApi();
});
afterEach(cleanup);

describe("arriving at /verify", () => {
  it("enters the verification world and sends the visitor into the product", async () => {
    const onStart = vi.fn();
    inVerifyScope(true);
    render(<Verify health={HEALTH} onStart={onStart} onHome={() => {}} />);

    expect(apiModule.api.setVerifyScope).toHaveBeenCalledWith(true);
    await userEvent.click(screen.getByRole("button", { name: /add what you buy/i }));
    expect(onStart).toHaveBeenCalledTimes(1);
  });

  it("tells the visitor the provider this deployment actually runs on", () => {
    inVerifyScope(true);
    render(<Verify health={HEALTH} onStart={() => {}} onHome={() => {}} />);
    expect(document.body.textContent).toContain("offline");
  });
});

describe("setting up inside the verification world", () => {
  it("does not offer the scripted walkthrough", async () => {
    inVerifyScope(true);
    render(<Onboarding consumer={FRESH} onDone={() => {}} onJudgeDemo={() => {}} />);

    expect(screen.queryByRole("button", { name: /judge walkthrough/i })).toBeNull();
    expect(document.body.textContent).not.toMatch(/here to evaluate pool/i);
  });

  it("still offers it at the ordinary front door", () => {
    inVerifyScope(false);
    render(<Onboarding consumer={FRESH} onDone={() => {}} onJudgeDemo={() => {}} />);
    expect(screen.getByRole("button", { name: /judge walkthrough/i })).toBeTruthy();
  });

  it("starts the declaration on the quantity this fixture is written around", async () => {
    inVerifyScope(true);
    render(<Onboarding consumer={FRESH} onDone={() => {}} />);
    await nameYourself();
    await chooseTheCoffee();

    const quantity = screen.getByLabelText(/how many/i) as HTMLInputElement;
    expect(quantity.value).toBe("3");
  });

  it("leaves the ordinary product's default alone", async () => {
    inVerifyScope(false);
    render(<Onboarding consumer={FRESH} onDone={() => {}} />);
    await nameYourself();
    await userEvent.click(screen.getByRole("button", { name: /join demo university/i }));
    await chooseTheCoffee();

    const quantity = screen.getByLabelText(/how many/i) as HTMLInputElement;
    expect(quantity.value).toBe("2");
  });

  it("declares through the ordinary member path, with the quantity on screen", async () => {
    inVerifyScope(true);
    render(<Onboarding consumer={FRESH} onDone={() => {}} />);
    await nameYourself();
    await chooseTheCoffee();
    await userEvent.click(screen.getByRole("button", { name: /add this/i }));

    await waitFor(() => expect(apiModule.api.declareNeed).toHaveBeenCalledTimes(1));
    const sent = vi.mocked(apiModule.api.declareNeed).mock.calls[0][0];
    expect(sent.product_id).toBe(KESTREL.product_id);
    expect(sent.household_id).toBe(FRESH.household_id);
    expect(sent.quantity).toBe(3);
  });

  it("keeps the quantity editable, including back down to the refusing one", async () => {
    /* The page promises that two produces a truthful "it could assemble an order, but not
       one you would be in". That promise is only keepable while the field is a field. */
    inVerifyScope(true);
    render(<Onboarding consumer={FRESH} onDone={() => {}} />);
    await nameYourself();
    await chooseTheCoffee();

    const quantity = screen.getByLabelText(/how many/i) as HTMLInputElement;
    expect(quantity.disabled).toBe(false);
    expect(quantity.readOnly).toBe(false);
    await userEvent.clear(quantity);
    await userEvent.type(quantity, "2");
    await userEvent.click(screen.getByRole("button", { name: /add this/i }));

    await waitFor(() => expect(apiModule.api.declareNeed).toHaveBeenCalledTimes(1));
    expect(vi.mocked(apiModule.api.declareNeed).mock.calls[0][0].quantity).toBe(2);
  });
});

describe("what the declaration caused, afterwards", () => {
  const coordination: apiModule.NeedCoordination = {
    need_id: "need_1",
    event: {
      event_id: "cev_1",
      status: "completed",
      run_id: "run_1",
      outcome: "pool_created",
      terminal_reason: "candidate_pool_created",
      pool_id: "pool_1",
      formed_order: true,
      reached_a_verdict: true,
    },
    clarification: {
      plan_id: "cpl_a",
      run_id: "run_clarify",
      status: "active",
      family: "roast_coffee",
      schema_version: 1,
      question_definition_version: 1,
      offered: ["q_roast", "q_form", "q_caffeine"],
      asked: ["q_roast", "q_form", "q_caffeine"],
      model_provider: "offline",
      model_id: "offline-deterministic-planner",
      iterations: 2,
      input_tokens: 0,
      output_tokens: 0,
    },
    evidence_run_id: "run_1",
    run: {
      run_id: "run_1",
      trigger: "need_declared",
      objective: "member",
      model_provider: "offline",
      model_id: "offline-deterministic-planner",
      outcome: "pool_created",
      termination_reason: "completed",
      iterations: 5,
      input_tokens: 0,
      output_tokens: 0,
      duration_ms: 3350,
      tool_calls: [
        { name: "list_cohort_strategies", ok: true },
        { name: "evaluate_cohort_strategy", ok: false },
        { name: "evaluate_cohort_strategy", ok: true },
        { name: "create_pool_from_strategy", ok: true },
      ],
      bounds: {
        max_iterations: 8,
        max_tool_calls: 25,
        max_strategy_listings: 1,
        max_strategy_evaluations: 3,
        max_strategy_pool_creations: 1,
      },
    },
    considered: [
      {
        strategy_id: "cst_kestrel",
        product: "Kestrel Medium Roast",
        attributes: { roast: "MEDIUM" },
        compatible_declarations: 8,
        compatible_units: 23,
        lowest_supplier_minimum_units: 12,
      },
      {
        strategy_id: "cst_harbourstone",
        product: "Harbourstone Dark Roast",
        attributes: { roast: "DARK" },
        compatible_declarations: 6,
        compatible_units: 18,
        lowest_supplier_minimum_units: 12,
      },
    ],
    investigated: [
      {
        strategy_id: "cst_kestrel",
        evaluation_id: "sev_kestrel",
        product: "Kestrel Medium Roast",
        viable: false,
        blocker_code: "not_cheaper",
        matched_units: 23,
        minimum_units: 12,
        selected_units: 0,
        cases: 0,
        case_units: 6,
        surplus_units: 0,
        all_in_display: "$367.19",
        retail_baseline_display: "$360.00",
        net_savings_display: "$0.00",
        net_savings_pct: "0%",
        includes_your_declaration: true,
      },
      {
        strategy_id: "cst_harbourstone",
        evaluation_id: "sev_harbourstone",
        product: "Harbourstone Dark Roast",
        viable: true,
        blocker_code: "",
        matched_units: 18,
        minimum_units: 12,
        selected_units: 18,
        cases: 3,
        case_units: 6,
        surplus_units: 0,
        all_in_display: "$263.76",
        retail_baseline_display: "$332.94",
        net_savings_display: "$69.18",
        net_savings_pct: "20.8%",
        includes_your_declaration: true,
      },
    ],
    chosen: null,
    exclusion_codes: { exact_product_required: 4 },
    order: {
      pool_id: "pool_1",
      status: "candidate",
      product: "Harbourstone Dark Roast",
      member_count: 6,
      units: 18,
      threshold_units: 12,
      cases: 3,
      case_units: 6,
      surplus_units: 0,
      pickup_site: "Student Union",
      distribution_day: "2026-09-02",
      provisional: true,
      host_status: "none",
      formed_by_this_run: true,
      created_by_run: "run_1",
    },
    not_yet: {
      host_accepted: false,
      final_price_issued: false,
      card_authorised: false,
      purchased: false,
    },
  };

  it("reaches the explanation and the proof from one server read", async () => {
    inVerifyScope(true);
    vi.spyOn(apiModule.api, "needCoordination").mockResolvedValue(coordination);
    render(
      <WhyThisOrder
        needId="need_1"
        productName="Kestrel Medium Roast"
        unit="bag"
        onBack={() => {}}
      />,
    );

    await waitFor(() =>
      expect(screen.getAllByText("Harbourstone Dark Roast").length).toBeGreaterThan(0),
    );
    expect(
      screen.getByText("Nothing has been charged, ordered or assigned"),
    ).toBeTruthy();

    await userEvent.click(screen.getByRole("button", { name: "Show" }));
    expect(document.body.textContent).toContain("cev_1");
    expect(document.body.textContent).toContain("run_1");
    expect(screen.getByText("Planner iterations")).toBeTruthy();
  });

  it("never describes the provisional order as bought", async () => {
    inVerifyScope(true);
    vi.spyOn(apiModule.api, "needCoordination").mockResolvedValue(coordination);
    render(
      <WhyThisOrder
        needId="need_1"
        productName="Kestrel Medium Roast"
        unit="bag"
        onBack={() => {}}
      />,
    );
    await waitFor(() =>
      expect(screen.getAllByText("Harbourstone Dark Roast").length).toBeGreaterThan(0),
    );
    await userEvent.click(screen.getByRole("button", { name: "Show" }));

    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/\bbought\b/i);
    expect(text).not.toMatch(/\bpurchased\b/i);
    expect(text).not.toMatch(/\bcharged your card\b/i);
    expect(text).toMatch(/No card has been charged/i);
    expect(text).toMatch(/Nothing has been ordered from the supplier/i);
  });
});
