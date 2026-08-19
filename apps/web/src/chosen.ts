/* What the member picked, before any form has to care which kind it was.
 *
 * Its own module rather than a corner of `product-search.tsx`: these are the shapes the
 * onboarding step, the needs form and the app shell all pass around, and a component
 * file that also exports helpers breaks fast refresh for every component in it.
 */

import { FamilyCandidate, ProductCandidate } from "./api";

/** What the member picked: a whole family, or one exact product. */
export type Picked =
  | { kind: "family"; family: FamilyCandidate }
  | { kind: "product"; product: ProductCandidate };

/** One picked thing, flattened, so the forms downstream do not each re-learn the union.
 *
 *  The only place the difference is allowed to matter is `draft` — a family sends its
 *  slug and lets the server look the exemplar up, a product sends its id. Everything
 *  else on this shape is presentation, and a family and a product are presented the
 *  same way on purpose: what the member picked is what they now see. */
export interface ChosenItem {
  key: string;
  label: string;
  unit: string;
  category: string;
  brand: string;
  image_ref: string;
  /** How many products the family covers. 0 when the member named one product. */
  familyCount: number;
  /** Pool holds a verified bulk quote for this — for the family, for anything in it.
   *  Undefined when the choice did not come from search and nobody has said. */
  sourceable?: boolean;
  draft: { product_id?: string; group?: string; substitution: string };
}

export function asChosen(picked: Picked): ChosenItem {
  if (picked.kind === "family") {
    const f = picked.family;
    return {
      key: `family:${f.group}`,
      label: f.label,
      unit: f.unit,
      category: f.category,
      brand: "",
      image_ref: "",
      familyCount: f.product_count,
      sourceable: f.sourceable,
      /* No `substitution` of its own to send: naming the family *is* the statement, and
         the server refuses a request that tries to claim family authority any other
         way. `exact_only` here would be a contradiction the server would reject. */
      draft: { group: f.group, substitution: "exact_only" },
    };
  }
  const p = picked.product;
  return {
    key: `product:${p.product_id}`,
    label: p.name,
    unit: p.unit,
    category: p.category,
    brand: p.brand,
    image_ref: p.image_ref,
    familyCount: 0,
    sourceable: p.sourceable,
    draft: { product_id: p.product_id, substitution: "exact_only" },
  };
}

