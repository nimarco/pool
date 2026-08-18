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
