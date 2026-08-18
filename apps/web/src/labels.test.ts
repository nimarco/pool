/* Provisional, final, simulated — the words next to a number have to match the number.
 *
 * The group saving is the figure a judge is most likely to quote back, and before a host
 * accepts it is an estimate: host compensation is not fixed, so neither is the total it
 * feeds. The caption used to say "after every cost" in both cases, which read as settled
 * on a pool that had settled nothing (#audit P1-3).
 */

import { describe, expect, it } from "vitest";

import { groupSavingsCaption } from "./labels";

describe("the group saving caption", () => {
  it("marks a candidate pool's total as an estimate", () => {
    const caption = groupSavingsCaption({
      economics: { net_savings_cents: 26632 },
      is_estimate: true,
    });

    expect(caption).toMatch(/estimated using provisional host pay/);
    expect(caption).not.toMatch(/after every cost/);
  });

  it("states what a final total is actually net of", () => {
    const caption = groupSavingsCaption({
      economics: { net_savings_cents: 26632 },
      is_estimate: false,
    });

    expect(caption).toContain("$266.32");
    expect(caption).toMatch(/merchandise, host pay, card processing and Pool's fee/);
    // "every cost" is a claim about the world; this is a claim about four line items.
    expect(caption).not.toMatch(/after every cost/);
  });

  it("hedges nothing and promises nothing when there is no host yet", () => {
    const caption = groupSavingsCaption({ economics: null, is_estimate: true });

    expect(caption).toBe("host pay is not fixed until a host accepts");
  });

  it("never presents a provisional total in the same words as a final one", () => {
    const provisional = groupSavingsCaption({
      economics: { net_savings_cents: 26632 },
      is_estimate: true,
    });
    const final = groupSavingsCaption({
      economics: { net_savings_cents: 26632 },
      is_estimate: false,
    });

    expect(provisional).not.toBe(final);
  });
});
