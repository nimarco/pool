/** What Pool asks about one product, and the one place that can buy a model call.
 *
 *  Two screens declare needs — setting up, and the needs list — and they must behave
 *  identically, because the second is where somebody *changes* what the first recorded.
 *  When the fetching lived in both, the rules that matter lived in both too, and a rule
 *  duplicated is a rule that drifts.
 *
 *  The rules:
 *
 *  **Choosing a product costs nothing.** The approved questions are a plain read of a
 *  curated schema, so a member browsing between products pays nothing and sees the same
 *  form either way.
 *
 *  **Only consent buys a plan.** Asking *which* of those questions are worth asking is a
 *  bounded agent run, and it happens exactly when somebody moves to "any brand that
 *  matches my preferences" — never on render, never on reload, never on an answer below
 *  the gate, and never when they stay exact-only. Somebody who never allows alternatives
 *  never causes a model call from this screen at all.
 *
 *  **Once per product.** The answer is remembered for the session, so going back,
 *  toggling to exact and back again, or reopening the same edit is free. The server
 *  is idempotent on the same grounds — the plan id digests the world it was made for —
 *  so this cache is a courtesy rather than the safety property.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import {
  FlexibilityContext,
  NeedPreferences,
  PreferenceQuestion,
  ProductClarification,
  api,
} from "./api";
import { EXACT, narrowestSimilar } from "./preference-answers";

export interface Clarification {
  /** What to put in front of the member, in the order Pool chose to ask. */
  questions: PreferenceQuestion[];
  /** Their answers. `null` for a product with nothing curated to ask about, which is
   *  what makes the older substitution control appear instead. */
  preferences: NeedPreferences | null;
  /** The curated consumer noun for the family — "coffee". Empty outside one. */
  noun: string;
  /** Counted demand either side of the choice. Null until they have made it. */
  flexibility: FlexibilityContext | null;
  /** Whether `questions` is a chosen subset rather than everything approved. */
  planned: boolean;
  /** The plan that produced those questions, empty when none was made. Sent with the
   *  declaration so the coordination event can record what shaped it, once, rather than
   *  the proof surface searching for a plan afterwards and finding the newest. */
  planId: string;
  /** A plan is in flight. */
  planning: boolean;
  /** Record an answer to the gate or to any question below it. The only call that can
   *  cost a run, and only on the transition into flexible. */
  answer: (next: NeedPreferences) => void;
  /** Open on a saved declaration's own answers, without asking anything. */
  load: (saved: NeedPreferences) => void;
  /** Back to nothing chosen. */
  reset: () => void;
}

export function useClarification(productId: string | undefined): Clarification {
  const [questions, setQuestions] = useState<PreferenceQuestion[]>([]);
  const [preferences, setPreferences] = useState<NeedPreferences | null>(null);
  const [noun, setNoun] = useState("");
  const [flexibility, setFlexibility] = useState<FlexibilityContext | null>(null);
  const [planned, setPlanned] = useState(false);
  const [planId, setPlanId] = useState("");
  const [planning, setPlanning] = useState(false);
  const asked = useRef(new Map<string, ProductClarification>());
  /** Whether the member was *already* past the gate when the last answer arrived. Read
   *  from a ref rather than from state because the check has to be about the value the
   *  answer is replacing, and a callback closed over the render's `preferences` would be
   *  asking about whichever render it was created in. */
  const wasFlexible = useRef(false);

  /* The approved questions, read whenever a product is chosen. A read of a curated
     schema: no model, no cost, and the same answer every time for the same product. */
  useEffect(() => {
    if (!productId) {
      wasFlexible.current = false;
      setQuestions([]);
      setPreferences(null);
      setNoun("");
      setFlexibility(null);
      setPlanned(false);
      setPlanId("");
      return;
    }
    let live = true;
    void api
      .productPreferences(productId)
      .then((offered) => {
        if (!live) return;
        setQuestions(offered.questions);
        setNoun(offered.family_noun ?? "");
        /* Exact-only until somebody says otherwise, for each product. Carrying a
           previous product's answers across would be applying consent to a thing it was
           never given about — but an answer already given about *this* product survives,
           which is what makes reopening an edit safe. */
        setPreferences((current) =>
          current ? current : offered.questions.length > 0 ? EXACT : null,
        );
      })
      .catch(() => {
        if (!live) return;
        setQuestions([]);
        setPreferences(null);
        setNoun("");
      });
    return () => {
      live = false;
    };
  }, [productId]);

  const answer = useCallback(
    (next: NeedPreferences) => {
      const crossed = next.flexibility === "similar" && !wasFlexible.current;
      wasFlexible.current = next.flexibility === "similar";
      setPreferences(next);
      /* Only the crossing. Every answer *below* the gate is an answer to a question
         already asked — ticking a roast is not a fresh decision to allow alternatives —
         and treating one as a transition both bought a second plan and threw away the
         answer that triggered it, because the arriving plan resets the form to its
         narrowest reading. */
      if (!crossed || !productId) return;

      const seen = asked.current.get(productId);
      if (seen) {
        /* The whole cached response, not a corner of it. Restoring only the counts left
           the *approved* list on screen beside a plan that had chosen a subset of it —
           harmless while nothing read the plan, and wrong the moment the declaration
           started recording which plan asked what. What is displayed and what is recorded
           have to be the same plan's questions. */
        setQuestions(seen.questions);
        setFlexibility(seen.flexibility);
        setPlanned(seen.planned);
        setPlanId(seen.plan_id);
        setNoun(seen.family_noun ?? "");
        setPreferences((current) =>
          current && current.flexibility === "similar"
            ? narrowestSimilar(seen.questions)
            : current,
        );
        return;
      }
      setPlanning(true);
      void api
        .productClarification(productId)
        .then((plan) => {
          asked.current.set(productId, plan);
          setQuestions(plan.questions);
          setFlexibility(plan.flexibility);
          setPlanned(plan.planned);
          setPlanId(plan.plan_id);
          setNoun(plan.family_noun ?? "");
          /* The questions may now be a subset, and "everything stays as it is" is
             defined over the ones actually asked. Re-deriving it keeps that sentence
             true of what is on the screen rather than of a list nobody saw. */
          setPreferences((current) =>
            current && current.flexibility === "similar"
              ? narrowestSimilar(plan.questions)
              : current,
          );
        })
        .catch(() => {
          /* The approved questions are already on screen from the plain read, so a
             failed plan costs targeting rather than the form. */
        })
        .finally(() => setPlanning(false));
    },
    [productId],
  );

  const load = useCallback((saved: NeedPreferences) => {
    wasFlexible.current = saved.flexibility === "similar";
    /* What they said, read back by the server from what it stored. Never a fetch:
       reopening a declaration is not a new consent decision, and a plan bought here
       would be a model call somebody paid for by pressing *Edit*. */
    setPreferences(saved);
    setFlexibility(null);
    setPlanned(false);
    /* Reopening a declaration asks nothing, so this edit has no plan of its own. Sending
       the previous one would attach a plan to a revision it never shaped — and an event
       whose questions came from nowhere is better recorded as having come from nowhere
       than credited to the last plan lying around. */
    setPlanId("");
  }, []);

  const reset = useCallback(() => {
    wasFlexible.current = false;
    setQuestions([]);
    setPreferences(null);
    setNoun("");
    setFlexibility(null);
    setPlanned(false);
    setPlanId("");
  }, []);

  return {
    questions,
    preferences,
    noun,
    flexibility,
    planned,
    planId,
    planning,
    answer,
    load,
    reset,
  };
}
