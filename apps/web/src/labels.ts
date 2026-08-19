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
