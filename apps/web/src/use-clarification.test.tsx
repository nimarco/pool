/** When Pool is allowed to ask, and what an answer must never cost.
 *
 *  This hook is the only thing on the member's side that can buy a model run, so the
 *  interesting assertions are about calls *not* made. The one that matters most is the
 *  last: an answer below the gate is not a fresh decision to allow alternatives, and
 *  treating it as one both bought a second plan and — because an arriving plan resets
 *  the form to its narrowest reading — silently discarded the answer that triggered it.
 *  Somebody ticking "dark roast works for me" watched it un-tick itself and saved a
 *  declaration they had not made.
 */
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as apiModule from "./api";
import { NeedPreferences, PreferenceQuestion } from "./api";
import { useClarification } from "./use-clarification";

const QUESTIONS: PreferenceQuestion[] = [
  {
    attribute: "form",
    kind: "keep",
    prompt: "It has to be whole bean",
    hint: "",
    product_value: "WHOLE_BEAN",
    product_value_label: "Whole bean",
    options: [
      { value: "GROUND", label: "Ground" },
      { value: "WHOLE_BEAN", label: "Whole bean" },
    ],
  },
  {
    attribute: "roast",
    kind: "choose",
    prompt: "Roasts that work for you",
    hint: "",
    product_value: "MEDIUM",
    product_value_label: "Medium",
    options: [
      { value: "DARK", label: "Dark" },
      { value: "MEDIUM", label: "Medium" },
    ],
  },
];

const REACH = { exact_requests: 4, compatible_requests: 12, sourceable_alternatives: 5 };

let preferences: ReturnType<typeof vi.fn>;
let clarification: ReturnType<typeof vi.fn>;

beforeEach(() => {
  preferences = vi.fn().mockResolvedValue({
    family: "roast_coffee",
    family_noun: "coffee",
    schema_version: 1,
    product_id: "prod_kestrel",
    questions: QUESTIONS,
  });
  clarification = vi.fn().mockResolvedValue({
    family: "roast_coffee",
    family_noun: "coffee",
    schema_version: 1,
    product_id: "prod_kestrel",
    /* The agent's subset, in the agent's order — deliberately not the schema's. */
    questions: [QUESTIONS[1], QUESTIONS[0]],
    plan_id: "cpl_x",
    planned: true,
    planned_now: true,
    questions_offered: ["roast_coffee.form", "roast_coffee.roast"],
    flexibility: REACH,
  });
  vi.spyOn(apiModule.api, "productPreferences").mockImplementation(preferences);
  vi.spyOn(apiModule.api, "productClarification").mockImplementation(clarification);
});

function flexible(over: Partial<NeedPreferences> = {}): NeedPreferences {
  return { flexibility: "similar", keep: ["form"], accept: { roast: ["MEDIUM"] }, ...over };
}

describe("asking what is worth asking", () => {
  it("reads the approved questions when a product is chosen, and buys nothing", async () => {
    const { result } = renderHook(() => useClarification("prod_kestrel"));
    await waitFor(() => expect(result.current.questions).toHaveLength(2));
    expect(preferences).toHaveBeenCalledTimes(1);
    expect(clarification).not.toHaveBeenCalled();
  });

  it("stays silent for somebody who never allows alternatives", async () => {
    const { result } = renderHook(() => useClarification("prod_kestrel"));
    await waitFor(() => expect(result.current.questions).toHaveLength(2));
    act(() => result.current.answer({ flexibility: "exact", keep: [], accept: {} }));
    expect(clarification).not.toHaveBeenCalled();
    expect(result.current.flexibility).toBeNull();
  });

  it("asks once, when consent is given, and takes the order it is given", async () => {
    const { result } = renderHook(() => useClarification("prod_kestrel"));
    await waitFor(() => expect(result.current.questions).toHaveLength(2));

    act(() => result.current.answer(flexible()));
    await waitFor(() => expect(result.current.flexibility).toEqual(REACH));

    expect(clarification).toHaveBeenCalledTimes(1);
    expect(result.current.questions.map((q) => q.attribute)).toEqual(["roast", "form"]);
    expect(result.current.planned).toBe(true);
  });

  it("does not ask again when they change their mind twice", async () => {
    const { result } = renderHook(() => useClarification("prod_kestrel"));
    await waitFor(() => expect(result.current.questions).toHaveLength(2));

    act(() => result.current.answer(flexible()));
    await waitFor(() => expect(clarification).toHaveBeenCalledTimes(1));
    for (let i = 0; i < 3; i++) {
      act(() => result.current.answer({ flexibility: "exact", keep: [], accept: {} }));
      act(() => result.current.answer(flexible()));
    }
    expect(clarification).toHaveBeenCalledTimes(1);
  });

  it("keeps an answer given below the gate", async () => {
    /* The regression. Ticking a second roast is an answer to a question already asked;
       if that is treated as crossing the gate, the plan arrives, resets the form to its
       narrowest reading, and the member's tick is gone. */
    const { result } = renderHook(() => useClarification("prod_kestrel"));
    await waitFor(() => expect(result.current.questions).toHaveLength(2));

    act(() => result.current.answer(flexible()));
    await waitFor(() => expect(result.current.flexibility).toEqual(REACH));

    act(() => result.current.answer(flexible({ accept: { roast: ["MEDIUM", "DARK"] } })));
    await waitFor(() =>
      expect(result.current.preferences?.accept.roast).toEqual(["MEDIUM", "DARK"]),
    );
    expect(clarification).toHaveBeenCalledTimes(1);
  });

  it("opens an edit on the saved answers without asking anything", async () => {
    const { result } = renderHook(() => useClarification("prod_kestrel"));
    await waitFor(() => expect(result.current.questions).toHaveLength(2));

    const saved = flexible({ keep: [], accept: { form: [], roast: ["MEDIUM", "DARK"] } });
    act(() => result.current.load(saved));
    expect(result.current.preferences).toEqual(saved);
    expect(clarification).not.toHaveBeenCalled();

    /* And an edit made after reopening is still an answer, not a crossing. */
    act(() => result.current.answer(flexible({ accept: { roast: ["DARK"] } })));
    expect(clarification).not.toHaveBeenCalled();
  });

  it("survives a plan it could not fetch, with the approved questions intact", async () => {
    clarification.mockRejectedValue(new Error("offline"));
    const { result } = renderHook(() => useClarification("prod_kestrel"));
    await waitFor(() => expect(result.current.questions).toHaveLength(2));

    act(() => result.current.answer(flexible()));
    await waitFor(() => expect(result.current.planning).toBe(false));

    expect(result.current.questions).toHaveLength(2);
    expect(result.current.planned).toBe(false);
    expect(result.current.preferences?.flexibility).toBe("similar");
  });
});
