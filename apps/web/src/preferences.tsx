/** "How flexible are you?", asked about one specific product.
 *
 *  The old control was one select over `SubstitutionPolicy` values — `exact_only`,
 *  `same_product_other_variant`, `structured_category_match`. Every one of those is a
 *  sentence about a database, and the member is left to guess which of them means the
 *  thing they actually think, which is usually something like *"any decent whole-bean
 *  caffeinated coffee, but not decaf and not ground"*.
 *
 *  So the questions are about the product in front of them, and the answers are answers
 *  rather than policy. Three properties hold this together, and none of them lives here:
 *
 *  **The dimensions are authoritative.** They come from the curated family schema
 *  (`domain/attributes.py`), fetched per product. This component renders whatever the
 *  server says can be asked and cannot invent a question — there is no list of coffee
 *  attributes in this file.
 *
 *  **The wording is curated too.** Prompts and value labels come from a committed table
 *  beside the schema. No model authored them, and none is called to choose them.
 *
 *  **The meaning is the server's.** What reaches the API is what somebody said — which
 *  attributes they want kept, which values they would accept — and
 *  `services/needs.policy_from_answers` decides what that implies. Every default there is
 *  the narrowest reading, so an unanswered question can never widen a rule.
 *
 *  A later phase may let a bounded agent choose *which* of the approved questions to ask
 *  and in what order. It would still be choosing from the same server payload and
 *  producing the same answer shape, so nothing here would have to change.
 */
import { NeedPreferences, PreferenceQuestion } from "./api";
import { EXACT, narrowestSimilar } from "./preference-answers";

export function Preferences({
  questions,
  value,
  onChange,
  disabled,
}: {
  questions: PreferenceQuestion[];
  value: NeedPreferences;
  onChange: (next: NeedPreferences) => void;
  disabled?: boolean;
}) {
  const flexible = value.flexibility === "similar";

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
            <strong>Only this exact product</strong>
            <span className="small muted">Pool will never buy you anything else.</span>
          </span>
        </label>
        <label className="prefs-radio">
          <input
            type="radio"
            name="flexibility"
            checked={flexible}
            onChange={() => setFlexibility("similar")}
            disabled={questions.length === 0}
          />
          <span>
            <strong>Similar products are okay</strong>
            <span className="small muted">
              {questions.length === 0
                ? "Pool cannot tell what makes this product what it is, so it will only buy this one."
                : "Tell Pool what has to stay the same, below."}
            </span>
          </span>
        </label>
      </div>

      {flexible && questions.length > 0 ? (
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
                </span>
              </label>
            ) : (
              <div className="prefs-group" key={q.attribute}>
                <span className="prefs-group-label" id={`prefs-${q.attribute}`}>
                  {q.prompt}
                </span>
                {q.hint ? <span className="small muted">{q.hint}</span> : null}
                <div className="prefs-options" role="group" aria-labelledby={`prefs-${q.attribute}`}>
                  {q.options.map((option) => {
                    const on = (value.accept[q.attribute] ?? []).includes(option.value);
                    return (
                      <label className={`prefs-pill${on ? " is-on" : ""}`} key={option.value}>
                        <input
                          type="checkbox"
                          checked={on}
                          onChange={(e) => toggleAccept(q.attribute, option.value, e.target.checked)}
                        />
                        <span>{option.label}</span>
                        {option.value === q.product_value ? (
                          <span className="small muted"> — yours</span>
                        ) : null}
                      </label>
                    );
                  })}
                </div>
              </div>
            ),
          )}
          <p className="small muted prefs-note">
            Pool only ever buys one exact product. These answers decide which ones it is
            allowed to consider for you — nothing here widens on its own, and anything you
            leave alone stays as it is on the product you picked.
          </p>
        </div>
      ) : null}
    </fieldset>
  );
}
