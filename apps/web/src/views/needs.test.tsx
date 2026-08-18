/* The primary Product action, and the labels a judge reads off the screen.
 *
 * These are the two things a frontend test can assert that a Python test cannot: that
 * the distinctive user action actually reaches the API, and that the words next to a
 * number match what that number is. Everything else worth pinning — the economics, the
 * lifecycle, the policy verdicts — is asserted where it is enforced.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Needs } from "./needs";
import * as apiModule from "../api";

const ROSA = { id: "hh_navarro", display_name: "Rosa N." };

const PRODUCTS = [
  { product_id: "prod_coffee_beans", name: "Whole bean coffee, 2 lb", unit: "bag", brand: "Acme" },
  { product_id: "prod_paper_towels", name: "Paper towels, 6 rolls", unit: "pack", brand: "Acme" },
];

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
    product_id: "prod_paper_towels",
    product_name: "Paper towels, 6 rolls",
    unit: "pack",
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

function renderNeeds() {
  return render(
    <Needs
      identity={ROSA}
      communityName="Demo University"
      onFind={() => {}}
      running={false}
      hasPool={false}
      liveDiscovery={false}
    />,
  );
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
  });

  it("offers the action rather than only describing it", async () => {
    renderNeeds();
    expect(await screen.findByRole("button", { name: /add a need/i })).toBeTruthy();
  });

  it("sends the declaration to the API and re-reads the authoritative list", async () => {
    const declare = vi
      .spyOn(apiModule.api, "declareNeed")
      .mockResolvedValue(needRow({ need_id: "need_2" }));
    renderNeeds();

    await userEvent.click(await screen.findByRole("button", { name: /add a need/i }));
    await userEvent.click(screen.getByRole("button", { name: /add this need/i }));

    await waitFor(() => expect(declare).toHaveBeenCalledTimes(1));
    const sent = declare.mock.calls[0][0];
    expect(sent.household_id).toBe(ROSA.id);
    expect(sent.product_id).toBe(PRODUCTS[0].product_id);
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

    await userEvent.click(await screen.findByRole("button", { name: /add a need/i }));
    await userEvent.click(screen.getByRole("button", { name: /add this need/i }));

    await waitFor(() => expect(declare).toHaveBeenCalled());
    expect(declare.mock.calls[0][0].household_id).toBe(ROSA.id);
  });

  it("shows the server's refusal instead of pretending the need was saved", async () => {
    vi.spyOn(apiModule.api, "declareNeed").mockRejectedValue(
      new Error("You already have a standing need for this item."),
    );
    renderNeeds();

    await userEvent.click(await screen.findByRole("button", { name: /add a need/i }));
    await userEvent.click(screen.getByRole("button", { name: /add this need/i }));

    expect(await screen.findByText(/already have a standing need/i)).toBeTruthy();
    // The form stays open with the rejected values, so the member can fix them.
    expect(screen.getByRole("button", { name: /add this need/i })).toBeTruthy();
  });

  it("edits an existing declaration in place rather than adding a second", async () => {
    const amend = vi.spyOn(apiModule.api, "amendNeed").mockResolvedValue(needRow());
    const declare = vi.spyOn(apiModule.api, "declareNeed");
    renderNeeds();

    await userEvent.click(await screen.findByRole("button", { name: /change/i }));
    await userEvent.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => expect(amend).toHaveBeenCalledTimes(1));
    expect(amend.mock.calls[0][0]).toBe("need_1");
    expect(declare).not.toHaveBeenCalled();
  });

  it("retires a need through the same authoritative path", async () => {
    const amend = vi.spyOn(apiModule.api, "amendNeed").mockResolvedValue(needRow());
    renderNeeds();

    await userEvent.click(await screen.findByRole("button", { name: /change/i }));
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
    renderNeeds();

    await userEvent.click(await screen.findByRole("button", { name: /add a need/i }));
    const early = screen.getByLabelText(/may buy this many days early/i);
    await userEvent.clear(early);
    await userEvent.type(early, "0");

    expect(await screen.findByText(/nothing will ever be brought forward/i)).toBeTruthy();
  });

  it("offers only substitution policies the domain can act on", async () => {
    renderNeeds();
    await userEvent.click(await screen.findByRole("button", { name: /add a need/i }));

    const options = Array.from(
      screen.getByLabelText(/substitutes/i).querySelectorAll("option"),
    ).map((o) => (o as HTMLOptionElement).value);

    // The two allowlist-driven policies need data this form does not collect, so
    // offering them would be a control that silently means nothing.
    expect(options).not.toContain("approved_products");
    expect(options).not.toContain("approved_brands");
    expect(options).toContain("exact_only");
  });
});
