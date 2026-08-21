/** "How flexible are you?", asked about one specific product.
 *
 *  The old control was one select over `SubstitutionPolicy` values — `exact_only`,
 *  `same_product_other_variant`, `structured_category_match`. Every one of those is a
 *  sentence about a database, and the member is left to guess which of them means the
 *  thing they actually think, which is usually something like *"any decent whole-bean
 *  caffeinated coffee, but not decaf and not ground"*.
 *
 *  So the questions are about the product in front of them, and the answers are answers
 *  rather than policy. Four properties hold this together, and none of them lives here:
 *
 *  **The dimensions are authoritative.** They come from the curated family schema
 *  (`domain/attributes.py`), fetched per product. This component renders whatever the
 *  server says can be asked and cannot invent a question — there is no list of coffee
 *  attributes in this file.
 *
 *  **The wording is curated too.** Prompts, value labels and even the noun for the
 *  family come from a committed table beside the schema. No model authored them.
 *
 *  **Which questions are worth asking is the agent's.** A bounded run picks a subset of
 *  the approved set and an order for it; this file receives the result as an ordinary
 *  list and cannot tell — nor need to — whether it was chosen or complete. What it must
 *  never do is ask before consent: brand flexibility is the gate, and the questions
 *  behind it are only fetched once somebody has passed through it.
 *
 *  **The meaning is the server's.** What reaches the API is what somebody said — which
 *  attributes they want kept, which values they would accept — and
 *  `services/needs.policy_from_answers` decides what that implies. Every default there is
 *  the narrowest reading, so an unanswered question can never widen a rule.
 */
import { FlexibilityContext, NeedPreferences, PreferenceQuestion } from "./api";
import { EXACT, narrowestSimilar } from "./preference-answers";

export function Preferences({
  questions,
  value,
  onChange,
  disabled,
  noun,
  flexibility,
  loading,
  planned,
}: {
  questions: PreferenceQuestion[];
  value: NeedPreferences;
  onChange: (next: NeedPreferences) => void;
  disabled?: boolean;
  /** What to call this kind of thing — "coffee", curated server-side. Empty for a
   *  product outside a curated family, where "product" is the honest word. */
  noun?: string;
  /** Counted demand on each side of the choice. Absent until somebody has chosen to
   *  allow alternatives, because that is when it is fetched. */
  flexibility?: FlexibilityContext | null;
  /** A plan is being fetched. The gate stays answerable; only the questions wait. */
  loading?: boolean;
  /** Whether these questions are a chosen subset rather than everything approved. */
  planned?: boolean;
}) {
  const flexible = value.flexibility === "similar";
  const thing = noun || "product";

  /* Grounded, or absent. Nothing here is a nudge Pool cannot justify from stored rows:
     the recommendation appears when allowing alternatives would genuinely reach more
     than insisting on one product does, and disappears when it would not. */
  const reaches = flexibility
    ? flexibility.compatible_requests - flexibility.exact_requests
    : 0;
  const worthIt = Boolean(flexibility && (reaches > 0 || flexibility.sourceable_alternatives > 0));

  function setFlexibility(next: "exact" | "similar") {
    onChange(next === "exact" ? EXACT : narrowestSimilar(questions));
  }

  function toggleKeep(attribute: string, keep: boolean) {
    const kept = new Set(value.keep);
    if (keep) kept.add(attribute);
    else kept.delete(attribute);
    /* An unticked "keep" has to be *said*, not merely omitted: the server reads a missing
       answer as "kept", so the empty array below is what carries the member's intent. */
    const accept = { ...value.accept };
    if (!keep) accept[attribute] = [];
    else delete accept[attribute];
    onChange({ ...value, keep: [...kept], accept });
  }

  function toggleAccept(attribute: string, option: string, on: boolean) {
    const current = new Set(value.accept[attribute] ?? []);
    if (on) current.add(option);
    else current.delete(option);
    onChange({ ...value, accept: { ...value.accept, [attribute]: [...current] } });
  }

  return (
    <fieldset className="field field-wide prefs" disabled={disabled}>
      <legend className="field-label">How flexible are you?</legend>

      <div className="prefs-choice" role="radiogroup" aria-label="How flexible are you?">
        <label className="prefs-radio">
          <input
            type="radio"
            name="flexibility"
            checked={!flexible}
            onChange={() => setFlexibility("exact")}
          />
          <span>
            <strong>Only this exact {thing}</strong>
            <span className="small muted">Pool will never buy you anything else.</span>
          </span>
        </label>
        <label className="prefs-radio">
          <input
            type="radio"
            name="flexibility"
            checked={flexible}
            onChange={() => setFlexibility("similar")}
            disabled={questions.length === 0 && !flexible}
          />
          <span>
            <strong>
              Any brand that matches my preferences
              {worthIt ? <span className="prefs-tag">Recommended</span> : null}
            </strong>
            <span className="small muted">
              {questions.length === 0 && !flexible
                ? `Pool cannot tell what makes this ${thing} what it is, so it will only buy this one.`
                : `You say what has to stay the same. The brand is the only thing this opens up.`}
            </span>
          </span>
        </label>
      </div>

      {flexible && flexibility ? (
        <p className="small muted prefs-reach">
          {reaches > 0 ? (
            <>
              {flexibility.exact_requests === 0
                ? `Nobody else here has asked for this exact ${thing}. `
                : `${plural(flexibility.exact_requests, "other member has", "other members have")} asked for this exact ${thing}. `}
              Allowing alternatives puts you alongside{" "}
              <strong>{plural(flexibility.compatible_requests, "request", "requests")}</strong>{" "}
              Pool could combine you with, across{" "}
              {plural(flexibility.sourceable_alternatives + 1, "product", "products")} it can
              source.
            </>
          ) : (
            <>
              Right now this changes nothing you can see:{" "}
              {plural(flexibility.compatible_requests, "standing request", "standing requests")}{" "}
              either way. It still lets Pool act if somebody declares something similar later.
            </>
          )}{" "}
          Pool cannot tell you whether an order will form — that depends on prices and
          minimums it checks at the time.
        </p>
      ) : null}

      {flexible ? (
        loading ? (
          <p className="small muted prefs-note">Working out what is worth asking…</p>
        ) : questions.length > 0 ? (
          <div className="prefs-questions">
            {questions.map((q) =>
              q.kind === "keep" ? (
                <label className="prefs-check" key={q.attribute}>
                  <input
                    type="checkbox"
                    checked={value.keep.includes(q.attribute)}
                    onChange={(e) => toggleKeep(q.attribute, e.target.checked)}
                  />
                  <span>
                    <strong>{q.prompt}</strong>
                    {q.hint ? <span className="small muted">{q.hint}</span> : null}
                    <Consequence question={q} thing={thing} />
                  </span>
                </label>
              ) : (
                <div className="prefs-group" key={q.attribute}>
                  <span className="prefs-group-label" id={`prefs-${q.attribute}`}>
                    {q.prompt}
                  </span>
                  {q.hint ? <span className="small muted">{q.hint}</span> : null}
                  <Consequence question={q} thing={thing} />
                  <div
                    className="prefs-options"
                    role="group"
                    aria-labelledby={`prefs-${q.attribute}`}
                  >
                    {q.options.map((option) => {
                      const on = (value.accept[q.attribute] ?? []).includes(option.value);
                      return (
                        <label className={`prefs-pill${on ? " is-on" : ""}`} key={option.value}>
                          <input
                            type="checkbox"
                            checked={on}
                            onChange={(e) =>
                              toggleAccept(q.attribute, option.value, e.target.checked)
                            }
                          />
                          <span>{option.label}</span>
                          {option.value === q.product_value ? (
                            <span className="small muted"> — yours</span>
                          ) : null}
                          <OptionReach question={q} value={option.value} />
                        </label>
                      );
                    })}
                  </div>
                </div>
              ),
            )}

            {/* §27. Somebody who is asked two questions about coffee and not a third is
                owed the reason, and the reason is not "the model felt like it" — it is
                that these are the ones whose answer could change what Pool may buy. */}
            <details className="prefs-why">
              <summary className="small muted">Why is Pool asking these?</summary>
              <p className="small muted">
                {planned ? (
                  <>
                    Pool looked at what it can actually source and what other members have
                    asked for, and picked the questions whose answers change which orders you
                    could join. Questions it left out would not have changed anything.
                  </>
                ) : (
                  <>
                    These are everything Pool can establish about this {thing} from supplier
                    data it has verified.
                  </>
                )}{" "}
                It never guesses what an answer means: each one maps to a fixed rule, and
                anything you leave alone stays exactly as it is on the {thing} you picked.
              </p>
            </details>

            <p className="small muted prefs-note">
              Pool only ever buys one exact {thing}. These answers decide which ones it is
              allowed to consider for you — nothing here widens on its own, and you can
              change any of it later.
            </p>
          </div>
        ) : (
          <p className="small muted prefs-note">
            There is nothing else to ask about this {thing}, so Pool will treat any brand
            it can source as acceptable.
          </p>
        )
      ) : null}
    </fieldset>
  );
}

/** What the answers to one question currently reach, in the member's terms.
 *
 *  Every figure is the server's, counted from stored declarations and the products this
 *  deployment can actually source (`services/clarification`). Nothing here adds anything
 *  up and nothing here forecasts: a narrower answer reaches less demand, which is a fact,
 *  and whether *any* order forms depends on prices and supplier minimums checked much
 *  later against a chosen buyer set.
 *
 *  Silent when the question cannot matter — when the things Pool can source do not differ
 *  on this dimension, no answer changes anybody's cohort, and saying so at length would be
 *  noise dressed as information.
 */
function Consequence({ question, thing }: { question: PreferenceQuestion; thing: string }) {
  const reach = question.reach;
  if (!reach || !reach.varies) return null;

  if (question.kind === "keep") {
    return (
      <span className="small muted">
        Insisting on this leaves {reach.keep.sourceable_products} of{" "}
        {reach.any.sourceable_products} {thing}s Pool can source, and{" "}
        {plural(reach.keep.standing_units, "unit", "units")} of other members&apos; standing
        demand against {reach.any.standing_units}.
      </span>
    );
  }
  return (
    <span className="small muted">
      Each answer shows the standing demand it would let Pool combine you with. More is not
      better on its own — it is only worth having if you would genuinely accept it.
    </span>
  );
}

/** The demand behind one specific answer. A stored count, shown where the answer is. */
function OptionReach({ question, value }: { question: PreferenceQuestion; value: string }) {
  const reach = question.reach;
  if (!reach || !reach.varies) return null;
  const row = reach.options[value];
  if (!row) return null;
  return (
    <span className="small faint prefs-reach-tag">
      {row.standing_units === 0
        ? "none standing"
        : `${plural(row.standing_units, "unit", "units")} standing`}
    </span>
  );
}

function plural(n: number, one: string, many: string) {
  return `${n} ${n === 1 ? one : many}`;
}
