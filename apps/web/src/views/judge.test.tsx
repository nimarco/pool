import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MemberView, NeedOutlook, StandingDemand } from "../api";
import { JudgeDemo } from "./judge";

const RICE = "prod_rice_jasmine";

function standing(over: Partial<StandingDemand> = {}): StandingDemand {
  return {
    need_id: "need_judge_rice",
    product_id: RICE,
    product_name: "Jasmine rice, 5 lb",
    unit: "bag",
    my_units: 2,
    compatible_members: 6,
    compatible_units: 22,
    minimum_units: 16,
    has_supplier: false,
    sourceable_product_id: "",
    sourceable_product_name: "",
    ...over,
  };
}

function outlook(over: Partial<NeedOutlook> = {}): NeedOutlook {
  return {
    need_id: "need_judge_rice",
    product_id: RICE,
    product_name: "Jasmine rice, 5 lb",
    state: "no_supply",
    reason: "",
    blocker: "No supplier Pool has verified sells this in bulk yet.",
    pool_id: "",
    units_needed: 16,
    units_available: 24,
    status: "watching",
    headline: "No verified supplier yet",
    ...over,
  };
}

function member(over: Partial<MemberView> = {}): MemberView {
  return {
    id: "hh_judge",
    display_name: "A judge",
    zone: "north",
    autonomy: "ask_me",
    autonomy_display: "Ask me first",
    has_payment_method: true,
    community_membership: null,
    host_profile: null,
    opportunity: null,
    other_pool_ids: [],
    standing_demand: [standing()],
    needs_outlook: [outlook()],
    ...over,
  } as MemberView;
}

function renderJudge(over: Partial<MemberView> | null = {}, hasOrder = false) {
  return render(
    <JudgeDemo
      member={over === null ? null : member(over)}
      hasOrder={hasOrder}
      onBack={() => {}}
      onShowcase={() => {}}
      onBehindPool={() => {}}
      onRefresh={() => {}}
    />,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("the judge walkthrough", () => {
  it("says what is synthetic before it asks anybody to believe a number", () => {
    renderJudge(null);
    const honesty = document.querySelector(".judge-honesty");
    expect(honesty?.textContent).toMatch(/Riverbend Wholesale does not exist/);
    expect(honesty?.textContent).toMatch(/simulated payments/i);
    expect(honesty?.textContent).toMatch(/parser and the arithmetic are real/i);
  });

  it("offers no way to skip a step, so the refusal cannot be walked past", () => {
    /* The middle beat is the whole argument: a supplier who will sell, and Pool still
       says no. A control that jumped to the end would turn the walkthrough into the
       thing it exists to disprove. */
    renderJudge(null);
    const quoteB = screen.getByRole("button", { name: /Import quote B/ }) as HTMLButtonElement;
    const run = screen.getByRole("button", { name: /Ask Pool to check now/ }) as HTMLButtonElement;
    expect(quoteB.disabled).toBe(true);
    expect(run.disabled).toBe(true);
  });

  it("unlocks each step only when the server's own state says the last one landed", () => {
    // A bulk offer exists and was judged not worth acting on: quote A has landed.
    renderJudge({
      needs_outlook: [outlook({ state: "not_worth_it", headline: "Supplier found — not cheaper" })],
    });
    const quoteB = screen.getByRole("button", { name: /Import quote B/ }) as HTMLButtonElement;
    const run = screen.getByRole("button", { name: /Ask Pool to check now/ }) as HTMLButtonElement;
    expect(quoteB.disabled).toBe(false);
    expect(run.disabled).toBe(true);
  });

  it("never writes its own verdict — every answer shown is the engine's", () => {
    renderJudge({
      needs_outlook: [outlook({ state: "not_worth_it", headline: "Supplier found — not cheaper" })],
    });
    const verdicts = [...document.querySelectorAll(".judge-verdict")].map((v) => v.textContent);
    expect(verdicts.join(" ")).toMatch(/Supplier found — not cheaper/);
    // Attributed to deterministic code, which is what computed it.
    expect(document.querySelector(".judge-verdict .actor-engine")).toBeTruthy();
    // And no congratulation anywhere: the page reports, it does not celebrate.
    const body = (document.body.textContent ?? "").toLowerCase();
    for (const word of ["success", "congratulations", "well done", "nice work"]) {
      expect(body).not.toContain(word);
    }
  });

  it("keeps the pre-existing demand as the headline fact, in the canonical numbers", () => {
    renderJudge({
      needs_outlook: [outlook({ state: "not_worth_it", headline: "Supplier found — not cheaper" })],
    });
    const said = document.querySelectorAll(".judge-said");
    const text = [...said].map((s) => s.textContent).join(" ").replace(/\s+/g, " ");
    expect(text).toMatch(/7 people near you buy this/);
    expect(text).toMatch(/24 bags standing, 2 of them yours/);
  });

  it("always offers a way back to the exact starting state", () => {
    renderJudge(null);
    const reset = screen.getByRole("button", { name: /Reset walkthrough/ }) as HTMLButtonElement;
    expect(reset.disabled).toBe(false);
  });

  it("ends by pointing at the two things it could not show", () => {
    renderJudge({ needs_outlook: [outlook({ state: "in_pool" })] }, true);
    expect(screen.getByRole("button", { name: /lifecycle, including a failure/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Behind Pool/ })).toBeTruthy();
  });
});
