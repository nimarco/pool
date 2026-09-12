/* Judge-facing label logic.
 *
 * Strings whose *correctness* matters, kept out of the components that render them so
 * they can be asserted directly. Everything here answers one question: does this
 * sentence describe the number it sits next to?
 *
 * This is not a copy file. Ordinary prose belongs in the view; what lives here is the
 * handful of captions that change meaning with the data — provisional versus final,
 * earned versus paid, simulated versus real.
 */

import { money } from "./api";

/** The caption under a pool's group saving.
 *
 * Before a host accepts, host compensation is an estimate, so the total it feeds is one
 * too. The caption used to say "after every cost" in both cases, which read as settled
 * on a pool that had settled nothing. After the final offer the figure is exact, and
 * names the four costs it is net of rather than claiming to cover every cost there is.
 */
export function groupSavingsCaption(pool: {
  economics: { net_savings_cents: number } | null;
  is_estimate: boolean;
}): string {
  if (!pool.economics) return "host compensation is not fixed until a host accepts";
  const amount = money(pool.economics.net_savings_cents);
  return pool.is_estimate
    ? `about ${amount} across the group, estimated using provisional host compensation`
    : `${amount} across the group, after merchandise, host compensation, card processing and Pool's fee`;
}

/** Why Pool asked a person instead of deciding for them.
 *
 * The decision payload carries both the machine name of the rule that blocked the
 * commitment (`blocking_rule`) and the deterministic policy engine's own sentence about
 * it inside `policy_checks`. Only the second one means anything to the person being
 * asked: "autonomy_mode" is an identifier, "member is on Ask Me — commitment requires
 * explicit approval" is the answer to their question.
 *
 * Returned verbatim. The UI frames it, and never paraphrases it — a rewritten policy
 * explanation is a second source of truth about an authorisation decision.
 */
export function blockingRuleExplanation(facts: Record<string, unknown>): string {
  const rule = facts.blocking_rule;
  if (typeof rule !== "string" || !rule) return "";
  const checks = facts.policy_checks;
  if (!Array.isArray(checks)) return "";
  for (const entry of checks) {
    if (entry && typeof entry === "object") {
      const check = entry as { rule?: unknown; detail?: unknown };
      if (check.rule === rule && typeof check.detail === "string" && check.detail) {
        return check.detail;
      }
    }
  }
  return "";
}

/** The four or five words beside a declaration's status chip.
 *
 * Normally the server's, verbatim. The exception is `in_pool`, and it is the reason this
 * lives here rather than inline in a view: `relevance._WATCHING_HEADLINES` maps eight of
 * the nine outlook states and `in_pool` is the one it misses, so the table's default —
 * "Pool is watching this" — is served for the single state `relevance.consumer_status`
 * documents as *not* watching. Home rendered it beside a Coordinating chip while Orders
 * said "YOU ARE IN THIS", about the same order, for the same member.
 *
 * Corrected in one place because two screens read this field. Fixing it in the view that
 * happened to be looked at would have left the other one still saying the opposite.
 */
export function outlookHeadline(state: string, headline: string): string {
  if (state === "in_pool") return "In an order";
  return headline || "Pool is watching this";
}

/** Whether the outlook's own sentence adds anything to that headline.
 *
 * False for `in_pool`, where the sentence ("Pool is already coordinating this one.") is
 * the headline again in longer words. */
export function outlookHasDetail(state: string): boolean {
  return state !== "in_pool";
}

/** How Pool describes its own standing permission over one member's money.
 *
 * `autonomy_display.mode` is the master switch: every other stored limit is only
 * consulted when it is `smart_join`. Showing the limits without showing this was the
 * interface claiming Pool might act when the stored policy said it never would.
 */
export function autonomyModeCopy(mode: string): string {
  if (mode === "smart_join") return "Yes — when every limit below passes";
  if (mode === "ask_me") return "No — Pool always asks first";
  return mode.replace(/_/g, " ");
}

/* ------------------------------------------------------------------ community */

/** What to call the member's community on a consumer surface.
 *
 *  Two shapes, because one word cannot do both jobs: a badge sits alone in the top bar,
 *  and a label sits inside a sentence.
 *
 *  On the verification walkthrough both are generic, and that is a product decision
 *  rather than a cosmetic one. The fixture genuinely is one invented campus, and naming
 *  it in the top bar of every screen made Pool look like a product for universities —
 *  the opposite of what it is. Pool coordinates wherever people are dense enough to
 *  share a pickup: apartment blocks, neighbourhoods, workplaces. A campus is one case of
 *  that, not the shape of the thing.
 *
 *  The synthetic community is still named in full, one tap away, inside the demo sheet
 *  the badge opens. This moves the disclosure to where it is the subject; it does not
 *  remove it.
 *
 *  Everywhere else — the ordinary product, the operator surfaces, the record — a
 *  community's real name is its real name.
 */
export function communityBadge(name: string, verifying: boolean): string {
  return verifying ? "Demo" : name;
}

/** The same thing, worded to sit inside a sentence: *standing needs across …*,
 *  *elsewhere in …*. `sentenceStart` capitalises it for the one slot that begins a
 *  line. */
export function communityLabel(
  name: string,
  verifying: boolean,
  opts: { sentenceStart?: boolean } = {},
): string {
  if (!verifying) return name;
  return opts.sentenceStart ? "Your area" : "your area";
}

/** `3 bag` was rendering on What you buy: a quantity beside a raw unit noun. The two
 *  other places that print a quantity each grew their own `n === 1 ? u : u + "s"`, and
 *  `preferences.tsx` grew a third as a local `plural`. One of the three simply got
 *  missed. Shared so the next screen that prints a quantity has something to reach for. */
export function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** The plural of a unit noun the server supplied, which is always regular here —
 *  `bag`, `pack`, `tub`, `unit`. */
export function units(n: number, unit: string): string {
  return plural(n, unit, `${unit}s`);
}
