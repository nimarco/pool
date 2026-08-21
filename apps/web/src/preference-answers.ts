/** The default answers a member starts from, and what "narrowest" means.
 *
 *  Split out of the component so the two can be imported without it — and because these
 *  are the values the *server's* mapping is the mirror of. `services/needs.
 *  policy_from_answers` reads an unanswered "keep" as kept and an unchosen value set as
 *  the product's own; these defaults say the same thing on the way in, so the form a
 *  member sees and the rule Pool stores agree before anybody touches a control.
 */
import { NeedPreferences, PreferenceQuestion } from "./api";

export const EXACT: NeedPreferences = { flexibility: "exact", keep: [], accept: {} };

/** The narrowest possible "similar is fine" for a given product.
 *
 *  Everything the product already is, kept. Widening is then something the member does
 *  deliberately, one control at a time — never something that happens because a question
 *  was left alone. */
export function narrowestSimilar(questions: PreferenceQuestion[]): NeedPreferences {
  const accept: Record<string, string[]> = {};
  for (const q of questions) {
    if (q.kind === "choose") accept[q.attribute] = [q.product_value];
  }
  return {
    flexibility: "similar",
    keep: questions.filter((q) => q.kind === "keep").map((q) => q.attribute),
    accept,
  };
}
