/* Provisional, final, simulated — the words next to a number have to match the number.
 *
 * The group saving is the figure a judge is most likely to quote back, and before a host
 * accepts it is an estimate: host compensation is not fixed, so neither is the total it
 * feeds. The caption used to say "after every cost" in both cases, which read as settled
 * on a pool that had settled nothing (#audit P1-3).
 */

import { describe, expect, it } from "vitest";

import {
  autonomyModeCopy,
  blockingRuleExplanation,
  communityBadge,
  communityLabel,
  groupSavingsCaption,
} from "./labels";

describe("the group saving caption", () => {
  it("marks a candidate pool's total as an estimate", () => {
    const caption = groupSavingsCaption({
      economics: { net_savings_cents: 26632 },
      is_estimate: true,
    });

    expect(caption).toMatch(/estimated using provisional host compensation/);
    expect(caption).not.toMatch(/after every cost/);
  });

  it("states what a final total is actually net of", () => {
    const caption = groupSavingsCaption({
      economics: { net_savings_cents: 26632 },
      is_estimate: false,
    });

    expect(caption).toContain("$266.32");
    expect(caption).toMatch(/merchandise, host compensation, card processing and Pool's fee/);
    // "every cost" is a claim about the world; this is a claim about four line items.
    expect(caption).not.toMatch(/after every cost/);
  });

  it("hedges nothing and promises nothing when there is no host yet", () => {
    const caption = groupSavingsCaption({ economics: null, is_estimate: true });

    expect(caption).toBe("host compensation is not fixed until a host accepts");
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

describe("why Pool asked", () => {
  it("returns the policy engine's own sentence for the rule that blocked", () => {
    expect(
      blockingRuleExplanation({
        blocking_rule: "autonomy_mode",
        policy_checks: [
          { rule: "max_spend", passed: true, detail: "fits" },
          {
            rule: "autonomy_mode",
            passed: false,
            detail: "member is on Ask Me — commitment requires explicit approval",
          },
        ],
      }),
    ).toBe("member is on Ask Me — commitment requires explicit approval");
  });

  it("says nothing rather than inventing a reason", () => {
    expect(blockingRuleExplanation({})).toBe("");
    expect(blockingRuleExplanation({ blocking_rule: "autonomy_mode" })).toBe("");
    expect(
      blockingRuleExplanation({
        blocking_rule: "autonomy_mode",
        policy_checks: [{ rule: "max_spend", passed: true, detail: "fits" }],
      }),
    ).toBe("");
  });
});

describe("standing autonomy, in a member's words", () => {
  it("answers the question the panel asks", () => {
    expect(autonomyModeCopy("ask_me")).toBe("No — Pool always asks first");
    expect(autonomyModeCopy("smart_join")).toBe("Yes — when every limit below passes");
  });

  it("does not guess at a mode it has never seen", () => {
    expect(autonomyModeCopy("some_future_mode")).toBe("some future mode");
  });
});

describe("what a consumer surface calls the community", () => {
  it("names it, in the ordinary product", () => {
    expect(communityBadge("Riverside Apartments", false)).toBe("Riverside Apartments");
    expect(communityLabel("Riverside Apartments", false)).toBe("Riverside Apartments");
    expect(communityLabel("Riverside Apartments", false, { sentenceStart: true })).toBe(
      "Riverside Apartments",
    );
  });

  it("is generic on the verification walkthrough, in both shapes", () => {
    /* The fixture is one invented campus. Naming it in the top bar of every screen made
       Pool look like a product for universities, which is the opposite of what it is —
       and the demo sheet the badge opens still states the name in full. */
    expect(communityBadge("Demo University", true)).toBe("Demo");
    expect(communityLabel("Demo University", true)).toBe("your area");
    expect(communityLabel("Demo University", true, { sentenceStart: true })).toBe("Your area");
  });

  it("never leaks a campus into a consumer sentence", () => {
    for (const shape of [
      communityBadge("Demo University", true),
      communityLabel("Demo University", true),
      communityLabel("Demo University", true, { sentenceStart: true }),
    ]) {
      expect(shape).not.toMatch(/university/i);
      expect(shape).not.toMatch(/campus/i);
    }
  });
});
