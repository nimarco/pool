/* The primary Product action, and the labels a judge reads off the screen.
 *
 * These are the two things a frontend test can assert that a Python test cannot: that
 * the distinctive user action actually reaches the API, and that the words next to a
 * number match what that number is. Everything else worth pinning — the economics, the
 * lifecycle, the policy verdicts — is asserted where it is enforced.
 *
 * Since the catalogue landed, the action has two halves. A member says what they buy in
 * their own words and confirms a product they recognise; only then are they asked how
 * much and how often. Both halves are exercised here, because a search that finds the
 * right thing and a form that sends the wrong id would still be a broken product.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Picked } from "../chosen";
import { Needs } from "./needs";
import * as apiModule from "../api";

const ROSA = { id: "hh_navarro", display_name: "Rosa N." };

const PRODUCTS = [
  { product_id: "prod_coffee_beans", name: "Whole bean coffee, 2 lb", unit: "bag", brand: "Acme" },
  { product_id: "prod_paper_towels", name: "Paper towels, 6 rolls", unit: "pack", brand: "Acme" },
];

const WHEY: apiModule.ProductCandidate = {
  product_id: "prod_whey_vanilla",
  name: "100% Whey Protein",
  brand: "Optimum Nutrition",
  variant: "Vanilla Ice Cream",
  display_size: "",
  unit: "tub",
  category: "nutrition",
  image_ref: "prod_whey_vanilla",
};

const ATTRIBUTION: apiModule.CatalogAttribution = {
  source: "Open Food Facts",
  source_url: "https://openfoodfacts.org",
  data_license: "ODbL-1.0",
  image_license: "CC-BY-SA-4.0",
  credit: "Open Food Facts contributors",
  snapshot: "2026-08-19",
};

const LIMITS = {
  max_quantity: 100,
  max_cadence_days: 365,
  max_min_savings_pct: 90,
  max_spend_cents: 500000,
  max_horizon_days: 365,
};

function needRow(overrides: Partial<apiModule.NeedRow> = {}): apiModule.NeedRow {
  return {
    need_id: "need_1",
    household_id: ROSA.id,
    household_name: "Rosa N.",
    declared_family: "",
    product_id: "prod_paper_towels",
    product_name: "Paper towels, 6 rolls",
    unit: "pack",
    brand: "",
    variant: "",
    category: "household",
    image_ref: "",
    quantity: 2,
    cadence_days: 30,
    expected_next_need_date: "2026-09-01",
    earliest_purchase_date: "2026-08-17",
    latest_purchase_date: "2026-09-01",
    flexibility_days: 15,
    routine_lead_days: 7,
    min_savings_pct: 20,
    max_spend_display: "$90.00",
    max_spend_cents: 9000,
    substitution: "exact_only",
    active: true,
    ...overrides,
  };
}

function renderNeeds(
  initialProduct: Picked | null = null,
  outlook: apiModule.NeedOutlook[] = [],
) {
  return render(
    <Needs
      identity={ROSA}
      communityName="Demo University"
      initialProduct={initialProduct}
      onConsumeInitialProduct={() => {}}
      onFind={() => {}}
      running={false}
      hasPool={false}
      outlook={outlook}
      liveDiscovery={false}
      region={null}
    />,
  );
}

/** Open the form and get through the product half of it, the way a member would. */
async function chooseProduct(query = "vanilla whey") {
  await userEvent.click(await screen.findByRole("button", { name: /add a need/i }));
  await userEvent.type(screen.getByLabelText(/what do you buy/i), query);
  const option = await screen.findByRole("option", { name: /100% Whey Protein/i });
  await userEvent.click(option);
}

afterEach(cleanup);

describe("declaring a standing need", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiModule.api, "needs").mockResolvedValue({
      needs: [needRow()],
      products: PRODUCTS,
      limits: LIMITS,
    });
    vi.spyOn(apiModule.api, "searchProducts").mockResolvedValue({
      query: "vanilla whey",
      groups: [],
      results: [WHEY],
      attribution: ATTRIBUTION,
    });
  });

  it("labels the current outlook as current, not as something a run concluded", async () => {
    /* Two different claims. "Pool evaluated this and declined" belongs to a run and is
       reported after one; this is a read-only recomputation of how it looks as things
       stand, and calling them the same thing would let a screen imply work that never
       happened. */
    renderNeeds(null, [
      {
        need_id: "need_1",
        product_id: "prod_paper_towels",
        product_name: "Paper towels, 6 rolls",
        state: "short",
      status: "watching",
      headline: "Not enough demand yet",
      blocker: "",
        reason: "Not enough of it yet: 4 packs declared nearby, and the supplier will not sell fewer than 48.",
        pool_id: "",
        units_needed: 48,
        units_available: 4,
      },
    ]);

    expect(await screen.findByText(/As things stand/)).toBeTruthy();
    expect(screen.getByText(/supplier will not sell fewer than 48/)).toBeTruthy();
  });

  it("offers the action rather than only describing it", async () => {
    renderNeeds();
    expect(await screen.findByRole("button", { name: /add a need/i })).toBeTruthy();
  });

  it("starts by asking what the member buys, not for procurement fields", async () => {
    renderNeeds();
    await userEvent.click(await screen.findByRole("button", { name: /add a need/i }));

    expect(screen.getByLabelText(/what do you buy/i)).toBeTruthy();
    // Nothing about quantity or cadence until Pool knows what the thing is.
    expect(screen.queryByLabelText(/how many/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /add this need/i })).toBeNull();
  });

  it("resolves what was typed into a product the member recognises", async () => {
    renderNeeds();
    await userEvent.click(await screen.findByRole("button", { name: /add a need/i }));
    await userEvent.type(screen.getByLabelText(/what do you buy/i), "vanilla whey");

    const option = await screen.findByRole("option", { name: /100% Whey Protein/i });
    expect(option.textContent).toMatch(/Optimum Nutrition/);
    expect(option.textContent).toMatch(/Vanilla Ice Cream/);
    // The internal identifier is what the form sends, and never what a member reads.
    expect(option.textContent).not.toMatch(/prod_/);
  });

  it("sends the chosen product's id and re-reads the authoritative list", async () => {
    const declare = vi
      .spyOn(apiModule.api, "declareNeed")
      .mockResolvedValue(needRow({ need_id: "need_2" }));
    renderNeeds();

    await chooseProduct();
    await userEvent.click(screen.getByRole("button", { name: /add this need/i }));

    await waitFor(() => expect(declare).toHaveBeenCalledTimes(1));
    const sent = declare.mock.calls[0][0];
    expect(sent.household_id).toBe(ROSA.id);
    expect(sent.product_id).toBe(WHEY.product_id);
    // The list is re-read from the server rather than patched with what was sent, so a
    // field the server rejected or normalised cannot linger on screen looking saved.
    expect(apiModule.api.needs).toHaveBeenCalledTimes(2);
  });

  it("declares for the signed-in member only, never for anyone else", async () => {
    const declare = vi.spyOn(apiModule.api, "declareNeed").mockResolvedValue(needRow());
    vi.spyOn(apiModule.api, "needs").mockResolvedValue({
      needs: [needRow(), needRow({ need_id: "need_other", household_id: "hh_okafor" })],
      products: PRODUCTS,
      limits: LIMITS,
    });
    renderNeeds();

    await chooseProduct();
    await userEvent.click(screen.getByRole("button", { name: /add this need/i }));

    await waitFor(() => expect(declare).toHaveBeenCalled());
    expect(declare.mock.calls[0][0].household_id).toBe(ROSA.id);
  });

  it("takes a product already chosen on Home rather than searching twice", async () => {
    renderNeeds({ kind: "product", product: WHEY });
    // Straight to the second half: the card is shown and the fields are live.
    expect(await screen.findByLabelText(/how many/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /add this need/i })).toBeTruthy();
  });

  it("shows the server's refusal instead of pretending the need was saved", async () => {
    vi.spyOn(apiModule.api, "declareNeed").mockRejectedValue(
      new Error("You already have a standing need for this item."),
    );
    renderNeeds();

    await chooseProduct();
    await userEvent.click(screen.getByRole("button", { name: /add this need/i }));

    expect(await screen.findByText(/already have a standing need/i)).toBeTruthy();
    // The form stays open with the rejected values, so the member can fix them.
    expect(screen.getByRole("button", { name: /add this need/i })).toBeTruthy();
  });

  it("offers to record an item the catalogue does not have", async () => {
    vi.spyOn(apiModule.api, "searchProducts").mockResolvedValue({
      query: "obscure thing",
      groups: [],
      results: [],
      attribution: ATTRIBUTION,
    });
    renderNeeds();

    await userEvent.click(await screen.findByRole("button", { name: /add a need/i }));
    await userEvent.type(screen.getByLabelText(/what do you buy/i), "obscure thing");

    // A real product does not tell somebody they cannot want a thing.
    expect(await screen.findByText(/does not have/i)).toBeTruthy();
    expect(screen.getByText(/until a supplier for it has been verified/i)).toBeTruthy();
  });

  it("edits an existing declaration in place rather than adding a second", async () => {
    const amend = vi.spyOn(apiModule.api, "amendNeed").mockResolvedValue(needRow());
    const declare = vi.spyOn(apiModule.api, "declareNeed");
    renderNeeds();

    await userEvent.click(await screen.findByRole("button", { name: /^change$/i }));
    await userEvent.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => expect(amend).toHaveBeenCalledTimes(1));
    expect(amend.mock.calls[0][0]).toBe("need_1");
    expect(declare).not.toHaveBeenCalled();
  });

  it("retires a need through the same authoritative path", async () => {
    const amend = vi.spyOn(apiModule.api, "amendNeed").mockResolvedValue(needRow());
    renderNeeds();

    await userEvent.click(await screen.findByRole("button", { name: /^change$/i }));
    await userEvent.click(screen.getByRole("button", { name: /stop buying this/i }));

    await waitFor(() => expect(amend).toHaveBeenCalled());
    expect(amend.mock.calls[0][1].active).toBe(false);
  });

  it("never offers a way to create a group or invite anyone", async () => {
    renderNeeds();
    await screen.findByRole("button", { name: /add a need/i });

    // Canonical invariant 1: the primary input is a declaration about one household.
    // A "start a group" affordance here would be the product failure, not a feature.
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/invite/i);
    expect(text).not.toMatch(/create a group/i);
    expect(text).not.toMatch(/start a pool/i);
  });

  it("says plainly what a zero flexibility window means", async () => {
    renderNeeds({ kind: "product", product: WHEY });
    await screen.findByLabelText(/how many/i);

    const early = screen.getByLabelText(/may buy this many days early/i);
    await userEvent.clear(early);
    await userEvent.type(early, "0");

    expect(await screen.findByText(/never bought early/i)).toBeTruthy();
  });

  it("states the buy-early window in words, because it is the field that authorises", async () => {
    renderNeeds({ kind: "product", product: WHEY });
    await screen.findByLabelText(/how many/i);

    // §24: this window is permission, not a preference. It is derived from the date the
    // member gave, and it is never silently hidden — only its exact size is.
    expect(screen.getByText(/Pool may buy any time in the \d+ days before that/i)).toBeTruthy();
  });

  it("says which result Pool can actually source, and does not hide the others", async () => {
    const sourceable = { ...WHEY, sourceable: true };
    const other = {
      ...WHEY,
      product_id: "prod_other_whey",
      brand: "Designer Whey",
      name: "Natural 100% Whey Protein Powder",
      sourceable: false,
    };
    vi.spyOn(apiModule.api, "searchProducts").mockResolvedValue({
      query: "whey",
      groups: [],
      results: [sourceable, other],
      attribution: ATTRIBUTION,
    });
    renderNeeds();
    await userEvent.click(await screen.findByRole("button", { name: /add a need/i }));
    await userEvent.type(screen.getByLabelText(/what do you buy/i), "whey");

    await screen.findByRole("option", { name: /Optimum Nutrition/i });
    const options = screen.getAllByRole("option");
    expect(options[0].textContent).toMatch(/Optimum Nutrition/);
    expect(options[0].textContent).toMatch(/Pool can source this/i);
    // The rest of the catalogue is still offered. This is a ranking and a label, not a
    // filter, and a member may declare anything they actually buy.
    expect(options[1].textContent).toMatch(/Designer Whey/);
    expect(options[1].textContent).not.toMatch(/Pool can source this/i);
  });

  it("tells a member what an unsourceable choice means, where they choose it", async () => {
    renderNeeds({ kind: "product", product: { ...WHEY, sourceable: false } });
    await screen.findByLabelText(/how many/i);

    const substitutes = screen.getByLabelText(/would another product do/i);
    expect(substitutes).toBeTruthy();
    const field = substitutes.closest("label") as HTMLElement;
    expect(field.textContent).toMatch(/no bulk supplier for this exact product yet/i);
    // Stated, not acted on: the choice stays theirs and the default is unchanged.
    expect((substitutes as HTMLSelectElement).value).toBe("exact_only");
  });

  it("offers only substitution policies the domain can act on", async () => {
    renderNeeds({ kind: "product", product: WHEY });
    await screen.findByLabelText(/how many/i);

    const options = Array.from(
      screen.getByLabelText(/would another product do/i).querySelectorAll("option"),
    ).map((o) => (o as HTMLOptionElement).value);

    // The two allowlist-driven policies need data this form does not collect, so
    // offering them would be a control that silently means nothing.
    expect(options).not.toContain("approved_products");
    expect(options).not.toContain("approved_brands");
    expect(options).toContain("exact_only");
  });

  it("keeps the authorisation constraints available, and unchanged, behind a disclosure", async () => {
    const declare = vi.spyOn(apiModule.api, "declareNeed").mockResolvedValue(needRow());
    renderNeeds({ kind: "product", product: WHEY });
    await screen.findByLabelText(/how many/i);

    // Collapsed by default: setting up a restock reminder should not start with a
    // savings floor. The summary still states the values, so nothing is hidden.
    const advanced = document.querySelector("details.need-advanced") as HTMLDetailsElement;
    expect(advanced).toBeTruthy();
    expect(advanced.open).toBe(false);
    expect(advanced.textContent).toMatch(/never below 15% saving/);
    expect(advanced.textContent).toMatch(/never above \$120\.00/);

    // Still real controls, and still reachable.
    expect(screen.getByLabelText(/won't join below/i)).toBeTruthy();
    expect(screen.getByLabelText(/never spend more than/i)).toBeTruthy();
    // Substitution is deliberately *not* in here. It decides whose demand may combine
    // with whose, and for a product Pool cannot source it is the only setting that could
    // change the answer — so it sits in the main form where somebody sees it.
    expect(advanced.querySelector("select")).toBeNull();

    // Moving a control behind a disclosure must not change what it sends.
    await userEvent.click(screen.getByRole("button", { name: /add this need/i }));
    await waitFor(() => expect(declare).toHaveBeenCalled());
    const sent = declare.mock.calls[0][0];
    expect(sent.min_savings_pct).toBe(15);
    expect(sent.max_spend_cents).toBe(12000);
    expect(sent.substitution).toBe("exact_only");
  });
});

/* --------------------------------------------------------------- declaring a family */

const COFFEE_FAMILY: apiModule.FamilyCandidate = {
  group: "coffee",
  label: "Coffee",
  category: "beverage",
  unit: "bag",
  product_count: 26,
  exemplar_product_id: "prod_coffee_beans",
  sourceable: true,
};

describe("saying what you buy, rather than which bag of it", () => {
  beforeEach(() => {
    vi.spyOn(apiModule.api, "needs").mockResolvedValue({
      needs: [],
      products: PRODUCTS,
      limits: LIMITS,
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  async function search(term: string) {
    renderNeeds();
    await userEvent.click(await screen.findByRole("button", { name: /add a need/i }));
    await userEvent.type(screen.getByLabelText(/what do you buy/i), term);
  }

  it("offers the family first, and keeps the exact products one click away", async () => {
    vi.spyOn(apiModule.api, "searchProducts").mockResolvedValue({
      query: "coffee",
      groups: [COFFEE_FAMILY],
      results: [{ ...WHEY, product_id: "prod_coffee_beans", name: "Pike Place" }],
      attribution: ATTRIBUTION,
    });
    await search("coffee");

    // One option, and it is the family. Six brand cards under it is the browse
    // experience this screen exists not to be.
    const options = await screen.findAllByRole("option");
    expect(options).toHaveLength(1);
    expect(options[0].textContent).toMatch(/Coffee/);
    expect(options[0].textContent).toMatch(/Any of 26/);

    // Available, not hidden.
    const widen = screen.getByRole("button", { name: /or pick one exact product/i });
    await userEvent.click(widen);
    expect((await screen.findAllByRole("option")).length).toBe(2);
  });

  it("sends the family, and never a product id beside it", async () => {
    const declare = vi.spyOn(apiModule.api, "declareNeed").mockResolvedValue(needRow());
    vi.spyOn(apiModule.api, "searchProducts").mockResolvedValue({
      query: "coffee",
      groups: [COFFEE_FAMILY],
      results: [],
      attribution: ATTRIBUTION,
    });
    await search("coffee");
    await userEvent.click(await screen.findByRole("option", { name: /Coffee/i }));
    await screen.findByLabelText(/how many/i);
    await userEvent.click(screen.getByRole("button", { name: /add this need/i }));

    await waitFor(() => expect(declare).toHaveBeenCalled());
    const sent = declare.mock.calls[0][0];
    // The server owns the exemplar lookup, so family authority can only come from a
    // family a human put in the catalogue. Sending both is refused, not reconciled.
    expect(sent.group).toBe("coffee");
    expect(sent.product_id).toBeUndefined();
  });

  it("names the family on the form, not the exemplar behind it", async () => {
    vi.spyOn(apiModule.api, "searchProducts").mockResolvedValue({
      query: "coffee",
      groups: [COFFEE_FAMILY],
      results: [],
      attribution: ATTRIBUTION,
    });
    await search("coffee");
    await userEvent.click(await screen.findByRole("option", { name: /Coffee/i }));

    // Showing "Pike Place Medium Roast" here would be Pool telling somebody who typed
    // "coffee" what they declared.
    const card = document.querySelector(".chosen-product") as HTMLElement;
    expect(card.textContent).toMatch(/Coffee/);
    expect(card.textContent).not.toMatch(/Pike Place/);
  });

  it("offers no family when the member named a brand", async () => {
    vi.spyOn(apiModule.api, "searchProducts").mockResolvedValue({
      query: "pike place",
      groups: [],
      results: [{ ...WHEY, product_id: "prod_coffee_beans", name: "Pike Place" }],
      attribution: ATTRIBUTION,
    });
    await search("pike place");

    // Somebody who typed a brand has already said which product they want. The exact
    // products show straight away, and there is nothing to expand.
    const options = await screen.findAllByRole("option");
    expect(options).toHaveLength(1);
    expect(options[0].textContent).toMatch(/Pike Place/);
    expect(screen.queryByRole("button", { name: /or pick one exact product/i })).toBeNull();
  });
});
