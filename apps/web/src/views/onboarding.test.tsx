/* Setting up an account, from the outside.
 *
 * The bug this replaced was not a rendering bug — it was that a visitor was silently
 * cast as a seeded student, so "your needs" and "your order" belonged to somebody else.
 * These tests protect the behaviour that fixes it rather than the layout that carries it:
 * an arbitrary name reaches the server, the location step collects nothing, and the
 * product does not open until the account exists.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Onboarding } from "./onboarding";
import * as apiModule from "../api";

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

afterEach(cleanup);

function renderOnboarding(onDone = () => {}) {
  return render(<Onboarding consumer={FRESH} onDone={onDone} />);
}

/** Type a name and move on — the gate every later step sits behind. */
async function pastName(name = "Jordan") {
  await userEvent.type(screen.getByLabelText(/your name/i), name);
  await userEvent.click(screen.getByRole("button", { name: /continue/i }));
}

describe("setting up an account", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiModule.api, "searchProducts").mockResolvedValue({
      query: "vanilla whey",
      results: [WHEY],
      attribution: ATTRIBUTION,
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
  });

  it("asks who you are before anything else", () => {
    renderOnboarding();
    expect(screen.getByRole("heading", { name: /what should pool call you/i })).toBeTruthy();
    expect(screen.getByLabelText(/your name/i)).toBeTruthy();
  });

  it("never presents a seeded person as the visitor", () => {
    renderOnboarding();
    // The whole point. No roster, no "signed in as", nobody else's name.
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/Rosa/);
    expect(text).not.toMatch(/signed in as/i);
  });

  it("will not continue without a name", async () => {
    renderOnboarding();
    expect(screen.getByRole("button", { name: /continue/i })).toHaveProperty("disabled", true);
    await userEvent.type(screen.getByLabelText(/your name/i), "Alex");
    expect(screen.getByRole("button", { name: /continue/i })).toHaveProperty("disabled", false);
  });

  it("asks where you are without asking the browser", async () => {
    /* The location step's entire contract. If this ever starts calling geolocation, the
       deployed Permissions-Policy would have to be weakened and a judge's real position
       would be collected for a community that does not exist. */
    const geo = vi.fn();
    Object.defineProperty(navigator, "geolocation", {
      value: { getCurrentPosition: geo, watchPosition: geo },
      configurable: true,
    });

    renderOnboarding();
    await pastName();

    expect(screen.getByRole("heading", { name: /where are you/i })).toBeTruthy();
    expect(geo).not.toHaveBeenCalled();
  });

  it("says plainly that the community is invented and was not guessed", async () => {
    renderOnboarding();
    await pastName();

    const text = (document.body.textContent ?? "").replace(/\s+/g, " ");
    expect(text).toMatch(/Demo University/);
    expect(text).toMatch(/24 members/);
    expect(text).toMatch(/this community is invented/i);
    // Why a synthetic area exists at all — without it, "invented" reads as a limitation
    // rather than as the thing that makes the demo reproducible.
    expect(text).toMatch(/behave the same way wherever it is opened/i);
    // And the sentence that makes this work for a judge in any city on earth.
    expect(text).toMatch(/has not asked your browser for your location/i);
    // The step has no input, so the button is where the choice happens; it should name
    // the place rather than read as clicking past a screen.
    expect(screen.getByRole("button", { name: /continue in demo university/i })).toBeTruthy();
  });

  it("reuses the real catalogue search rather than a setup-only picker", async () => {
    renderOnboarding();
    await pastName();
    await userEvent.click(screen.getByRole("button", { name: /continue/i }));

    await userEvent.type(screen.getByLabelText(/what do you buy/i), "vanilla whey");
    const option = await screen.findByRole("option", { name: /100% Whey Protein/i });
    expect(option.textContent).toMatch(/Optimum Nutrition/);
    expect(option.textContent).not.toMatch(/prod_/);
  });

  it("declares through the real need path and will not continue empty-handed", async () => {
    renderOnboarding();
    await pastName();
    await userEvent.click(screen.getByRole("button", { name: /continue/i }));

    expect(screen.getByRole("button", { name: /add one to continue/i })).toHaveProperty(
      "disabled",
      true,
    );

    await userEvent.type(screen.getByLabelText(/what do you buy/i), "vanilla whey");
    await userEvent.click(await screen.findByRole("option", { name: /100% Whey Protein/i }));
    await userEvent.click(screen.getByRole("button", { name: /add this/i }));

    await waitFor(() => expect(apiModule.api.declareNeed).toHaveBeenCalledTimes(1));
    const sent = vi.mocked(apiModule.api.declareNeed).mock.calls[0][0];
    expect(sent.product_id).toBe(WHEY.product_id);
    expect(sent.household_id).toBe(FRESH.household_id);
    // "I need it by then" already says Pool may buy any time before then (§24).
    expect(sent.flexibility_days).toBeGreaterThan(0);
  });

  it("offers both autonomy modes in a member's words, with no rule slugs", async () => {
    renderOnboarding();
    await pastName();
    await userEvent.click(screen.getByRole("button", { name: /continue/i }));
    await userEvent.type(screen.getByLabelText(/what do you buy/i), "vanilla whey");
    await userEvent.click(await screen.findByRole("option", { name: /100% Whey Protein/i }));
    await userEvent.click(screen.getByRole("button", { name: /add this/i }));
    await waitFor(() => expect(apiModule.api.declareNeed).toHaveBeenCalled());
    await userEvent.click(screen.getByRole("button", { name: /^continue$/i }));

    expect(screen.getByRole("radio", { name: /ask me first/i })).toBeTruthy();
    expect(screen.getByRole("radio", { name: /act when it fits my limits/i })).toBeTruthy();
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/smart_join|ask_me|AutonomyMode/);
  });

  it("marks the payment method as simulated and takes no card details", async () => {
    renderOnboarding();
    await pastName();
    await userEvent.click(screen.getByRole("button", { name: /continue/i }));
    await userEvent.type(screen.getByLabelText(/what do you buy/i), "vanilla whey");
    await userEvent.click(await screen.findByRole("option", { name: /100% Whey Protein/i }));
    await userEvent.click(screen.getByRole("button", { name: /add this/i }));
    await waitFor(() => expect(apiModule.api.declareNeed).toHaveBeenCalled());
    await userEvent.click(screen.getByRole("button", { name: /^continue$/i }));

    const text = (document.body.textContent ?? "").replace(/\s+/g, " ");
    expect(text).toMatch(/simulated for this demo/i);
    expect(text).toMatch(/no real card, no real charge/i);
    // A public demo must never present a field that looks like it wants a card number.
    expect(document.querySelector('input[autocomplete*="cc-"]')).toBeNull();
    expect(text).not.toMatch(/card number|cvv|expiry/i);
  });

  it("sends the typed name and chosen mode, then hands over to the product", async () => {
    const onDone = vi.fn();
    renderOnboarding(onDone);
    await pastName("Priya");
    await userEvent.click(screen.getByRole("button", { name: /continue/i }));
    await userEvent.type(screen.getByLabelText(/what do you buy/i), "vanilla whey");
    await userEvent.click(await screen.findByRole("option", { name: /100% Whey Protein/i }));
    await userEvent.click(screen.getByRole("button", { name: /add this/i }));
    await waitFor(() => expect(apiModule.api.declareNeed).toHaveBeenCalled());
    await userEvent.click(screen.getByRole("button", { name: /^continue$/i }));

    await userEvent.click(screen.getByRole("radio", { name: /act when it fits my limits/i }));
    await userEvent.click(screen.getByRole("button", { name: /add a test card/i }));
    await waitFor(() => expect(apiModule.api.saveOwnPaymentMethod).toHaveBeenCalled());
    await userEvent.click(screen.getByRole("button", { name: /finish/i }));

    await waitFor(() => expect(apiModule.api.completeOnboarding).toHaveBeenCalledTimes(1));
    expect(vi.mocked(apiModule.api.completeOnboarding).mock.calls[0]).toEqual([
      "Priya",
      "smart_join",
    ]);
    await waitFor(() => expect(onDone).toHaveBeenCalled());
  });

  it("cannot finish while the card request is still in flight", async () => {
    /* Finishing writes the whole household row. If it read that row before the payment
       call had landed, it would write back a copy with no saved method — which fails
       silently now and fails this member's authorisation later, turning eleven
       membership rows into twelve. The same class of stale write was already found and
       fixed server-side; a fast click reaches it from here. */
    let release: (v: { ok: boolean; has_payment_method: boolean }) => void = () => {};
    vi.spyOn(apiModule.api, "saveOwnPaymentMethod").mockReturnValue(
      new Promise((resolve) => {
        release = resolve;
      }),
    );

    renderOnboarding();
    await pastName();
    await userEvent.click(screen.getByRole("button", { name: /continue/i }));
    await userEvent.type(screen.getByLabelText(/what do you buy/i), "vanilla whey");
    await userEvent.click(await screen.findByRole("option", { name: /100% Whey Protein/i }));
    await userEvent.click(screen.getByRole("button", { name: /add this/i }));
    await waitFor(() => expect(apiModule.api.declareNeed).toHaveBeenCalled());
    await userEvent.click(screen.getByRole("button", { name: /^continue$/i }));

    await userEvent.click(screen.getByRole("button", { name: /add a test card/i }));
    expect(screen.getByRole("button", { name: /finish/i })).toHaveProperty("disabled", true);

    release({ ok: true, has_payment_method: true });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /finish/i })).toHaveProperty("disabled", false),
    );
    expect(apiModule.api.completeOnboarding).not.toHaveBeenCalled();
  });

  it("shows the server's refusal rather than pretending setup finished", async () => {
    vi.spyOn(apiModule.api, "completeOnboarding").mockRejectedValue(
      new Error("Pool needs something to call you"),
    );
    const onDone = vi.fn();
    renderOnboarding(onDone);
    await pastName();
    await userEvent.click(screen.getByRole("button", { name: /continue/i }));
    await userEvent.type(screen.getByLabelText(/what do you buy/i), "vanilla whey");
    await userEvent.click(await screen.findByRole("option", { name: /100% Whey Protein/i }));
    await userEvent.click(screen.getByRole("button", { name: /add this/i }));
    await waitFor(() => expect(apiModule.api.declareNeed).toHaveBeenCalled());
    await userEvent.click(screen.getByRole("button", { name: /^continue$/i }));
    await userEvent.click(screen.getByRole("button", { name: /finish/i }));

    expect(await screen.findByText(/something to call you/i)).toBeTruthy();
    expect(onDone).not.toHaveBeenCalled();
  });

  it("resumes an interrupted setup from what was already declared", async () => {
    /* Somebody adds a declaration, refreshes before finishing, and comes back. The server
       correctly refuses a second active declaration for the same product, so a setup that
       only remembered its own session left them unable to continue — re-adding the thing
       they had chosen failed, and the only escape was declaring something else. */
    vi.spyOn(apiModule.api, "needs").mockResolvedValue({
      needs: [
        {
          need_id: "need_1",
          household_id: FRESH.household_id,
          household_name: "You",
          product_id: WHEY.product_id,
          product_name: WHEY.name,
          unit: WHEY.unit,
          brand: WHEY.brand,
          variant: WHEY.variant,
          category: WHEY.category,
          image_ref: WHEY.image_ref,
          quantity: 2,
          cadence_days: 30,
          expected_next_need_date: "2026-09-02",
          earliest_purchase_date: "2026-08-19",
          latest_purchase_date: "2026-09-02",
          flexibility_days: 14,
          routine_lead_days: 7,
          min_savings_pct: 15,
          max_spend_display: "$120.00",
          max_spend_cents: 12000,
          substitution: "exact_only",
          active: true,
        },
      ],
      products: [],
      limits: {
        max_quantity: 100,
        max_cadence_days: 365,
        max_min_savings_pct: 90,
        max_spend_cents: 500000,
        max_horizon_days: 365,
      },
    });

    renderOnboarding();
    await pastName();
    await userEvent.click(screen.getByRole("button", { name: /continue in/i }));

    // Their earlier declaration is shown, and they are not stuck behind it.
    expect(await screen.findByText(/100% Whey Protein/i)).toBeTruthy();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /^continue$/i })).toHaveProperty(
        "disabled",
        false,
      ),
    );
    expect(screen.queryByRole("button", { name: /add one to continue/i })).toBeNull();
  });

  it("lets somebody go back and change an earlier answer", async () => {
    renderOnboarding();
    await pastName("Alex");
    await userEvent.click(screen.getByRole("button", { name: /back/i }));

    expect(screen.getByRole("heading", { name: /what should pool call you/i })).toBeTruthy();
    expect(screen.getByLabelText(/your name/i)).toHaveProperty("value", "Alex");
  });
});
