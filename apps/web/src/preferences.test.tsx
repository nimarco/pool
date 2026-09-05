/** The flexibility questions, and the shape of the answer they produce.
 *
 *  The component decides nothing about compatibility — the server does — so what is
 *  worth pinning here is the *payload*: which answers travel, and what happens to a
 *  question nobody touched. Every default is the narrowest one, because the mapping on
 *  the other side treats an unanswered "keep" as kept, and a widening therefore has to
 *  be a deliberate act rather than an omission.
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { NeedPreferences, PreferenceQuestion } from "./api";
import { EXACT, narrowestSimilar } from "./preference-answers";
import { Preferences } from "./preferences";

const QUESTIONS: PreferenceQuestion[] = [
  {
    attribute: "form",
    kind: "keep",
    prompt: "It has to be whole bean",
    hint: "Ground coffee and whole beans are not the same thing to most people.",
    product_value: "WHOLE_BEAN",
    product_value_label: "Whole bean",
    options: [
      { value: "GROUND", label: "Ground" },
      { value: "WHOLE_BEAN", label: "Whole bean" },
    ],
  },
  {
    attribute: "caffeine",
    kind: "keep",
    prompt: "It has to be caffeinated",
    hint: "",
    product_value: "CAFFEINATED",
    product_value_label: "Caffeinated",
    options: [
      { value: "CAFFEINATED", label: "Caffeinated" },
      { value: "DECAF", label: "Decaf" },
    ],
  },
  {
    attribute: "roast",
    kind: "choose",
    prompt: "Roasts that work for you",
    hint: "Pick every roast you would be happy with.",
    product_value: "MEDIUM",
    product_value_label: "Medium",
    options: [
      { value: "DARK", label: "Dark" },
      { value: "LIGHT", label: "Light" },
      { value: "MEDIUM", label: "Medium" },
    ],
  },
];

const REACH = {
  exact_requests: 4,
  compatible_requests: 12,
  sourceable_alternatives: 5,
};

/** Server-shaped reach, attached to the roast question. Numbers a member could check
 *  against the store, never a forecast. */
const ROAST_REACH = {
  keep: { sourceable_products: 3, standing_requests: 7, standing_units: 22, values: ["MEDIUM"] },
  any: {
    sourceable_products: 5,
    standing_requests: 11,
    standing_units: 33,
    values: ["DARK", "LIGHT", "MEDIUM"],
  },
  options: {
    DARK: { sourceable_products: 1, standing_requests: 2, standing_units: 6 },
    LIGHT: { sourceable_products: 1, standing_requests: 2, standing_units: 5 },
    MEDIUM: { sourceable_products: 3, standing_requests: 7, standing_units: 22 },
  },
  varies: true,
};

const FORM_REACH = {
  keep: {
    sourceable_products: 5,
    standing_requests: 10,
    standing_units: 29,
    values: ["WHOLE_BEAN"],
  },
  any: {
    sourceable_products: 6,
    standing_requests: 12,
    standing_units: 36,
    values: ["GROUND", "WHOLE_BEAN"],
  },
  options: {
    GROUND: { sourceable_products: 1, standing_requests: 2, standing_units: 7 },
    WHOLE_BEAN: { sourceable_products: 5, standing_requests: 10, standing_units: 29 },
  },
  varies: true,
};

function withReach(): PreferenceQuestion[] {
  return QUESTIONS.map((q) =>
    q.attribute === "roast"
      ? { ...q, reach: ROAST_REACH }
      : q.attribute === "form"
        ? { ...q, reach: FORM_REACH }
        : q,
  );
}

function renderPrefs(
  value: NeedPreferences = EXACT,
  props: Partial<Parameters<typeof Preferences>[0]> = {},
) {
  const onChange = vi.fn();
  const view = render(
    <Preferences
      questions={QUESTIONS}
      value={value}
      onChange={onChange}
      noun="coffee"
      {...props}
    />,
  );
  return { onChange, view };
}

describe("the flexibility questions", () => {
  it("starts on exact-only and asks nothing else", () => {
    renderPrefs();
    expect(screen.getByLabelText(/only this exact coffee/i)).toBeTruthy();
    expect(screen.queryByText(/It has to be whole bean/)).toBeNull();
  });

  it("speaks about the product, never about the schema", () => {
    renderPrefs(narrowestSimilar(QUESTIONS));
    const text = document.body.textContent ?? "";
    expect(text).toMatch(/It has to be whole bean/);
    expect(text).toMatch(/Roasts that work for you/);
    for (const token of [
      "WHOLE_BEAN",
      "CAFFEINATED",
      "attribute_constrained",
      "substitute_group",
      "schema",
    ]) {
      expect(text).not.toContain(token);
    }
  });

  it("opens on the narrowest reading of allowing alternatives", async () => {
    const { onChange } = renderPrefs();
    await userEvent.click(screen.getByLabelText(/any brand that matches my preferences/i));

    /* Everything the product already is, kept — including the roast it happens to be.
       Anything looser is something the member does next, one control at a time. */
    expect(onChange).toHaveBeenCalledWith({
      flexibility: "similar",
      keep: ["form", "caffeine"],
      accept: { roast: ["MEDIUM"] },
    });
  });

  it("widens the roast only when a roast is actually chosen", async () => {
    const { onChange } = renderPrefs(narrowestSimilar(QUESTIONS));
    await userEvent.click(screen.getByLabelText(/^Dark/));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ accept: { roast: ["MEDIUM", "DARK"] } }),
    );
  });

  it("says out loud that a requirement was dropped", async () => {
    /* An empty list rather than an absent key: the server reads a missing answer as
       "kept", so unticking has to travel as a statement rather than as silence. */
    const { onChange } = renderPrefs(narrowestSimilar(QUESTIONS));
    await userEvent.click(screen.getByLabelText(/It has to be caffeinated/));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ keep: ["form"], accept: expect.objectContaining({ caffeine: [] }) }),
    );
  });

  it("going back to exact-only clears every answer", async () => {
    const { onChange } = renderPrefs(narrowestSimilar(QUESTIONS));
    await userEvent.click(screen.getByLabelText(/only this exact coffee/i));
    expect(onChange).toHaveBeenCalledWith(EXACT);
  });

  it("offers nothing to widen when the product has no curated questions", () => {
    const onChange = vi.fn();
    render(<Preferences questions={[]} value={EXACT} onChange={onChange} />);
    const flexible = screen.getByLabelText(/any brand that matches my preferences/i) as HTMLInputElement;
    expect(flexible.disabled).toBe(true);
    expect(document.body.textContent).toMatch(/it will only buy this one/i);
  });

  it("marks which value is the member's own, so the pills are not a quiz", () => {
    renderPrefs(narrowestSimilar(QUESTIONS));
    const medium = screen.getByLabelText(/^Medium/).closest("label");
    expect(medium?.textContent).toMatch(/yours/);
  });
});

describe("what Pool says about being flexible", () => {
  it("says nothing at all until somebody has chosen to allow alternatives", () => {
    /* The counts are fetched by that choice, so guidance about them cannot appear
       before it. A screen that already knew would have paid for the answer on render. */
    renderPrefs(EXACT, { flexibility: REACH });
    expect(document.body.textContent).not.toMatch(/requests/);
  });

  it("gives counted demand and never a probability", () => {
    renderPrefs(narrowestSimilar(QUESTIONS), { flexibility: REACH });
    const text = document.body.textContent ?? "";

    expect(text).toMatch(/4 other members have asked for this exact coffee/);
    expect(text).toMatch(/12 requests/);
    /* The whole class of claim Pool cannot support. It has no model of whether an order
       forms — the evaluator answers that only after a buyer set has been costed — so a
       number with a % or a "likely" attached would be invented. */
    expect(text).not.toMatch(/%|likely|chance|probably|expect to|guarantee/i);
    expect(text).toMatch(/cannot tell you whether an order will form/i);
  });

  it("labels the flexible option with what it reaches, never with advice", () => {
    /* It used to say "Recommended", which is Pool telling somebody their preferences
       should be looser. It has no basis for that: a preference genuinely held is not
       worse for reaching less demand. What it can say is the count, so the label is the
       count's name and disappears when there is nothing to count. */
    const { view } = renderPrefs(EXACT, { flexibility: REACH });
    expect(screen.getByText(/Reaches more current demand/)).toBeTruthy();
    expect(screen.queryByText(/Recommended/)).toBeNull();

    view.rerender(
      <Preferences
        questions={QUESTIONS}
        value={EXACT}
        onChange={vi.fn()}
        noun="coffee"
        flexibility={{
          exact_requests: 3,
          compatible_requests: 3,
          sourceable_alternatives: 0,
        }}
      />,
    );
    expect(screen.queryByText(/Reaches more current demand/)).toBeNull();
    expect(screen.queryByText(/More options/)).toBeNull();
    expect(screen.queryByText(/Recommended/)).toBeNull();
  });

  it("says more options, not more demand, when only the catalogue is wider", () => {
    renderPrefs(EXACT, {
      flexibility: { exact_requests: 3, compatible_requests: 3, sourceable_alternatives: 4 },
    });
    expect(screen.getByText(/More options/)).toBeTruthy();
    expect(screen.queryByText(/Reaches more current demand/)).toBeNull();
  });

  it("does not claim any brand is acceptable when nothing was worth asking", () => {
    /* A plan may legitimately choose no questions. The server still reads every
       unanswered question as unchanged, so roast, form and caffeine stay hard
       requirements and only the brand opens up — saying "any brand it can source is
       acceptable" described a permission wider than the one actually saved. */
    renderPrefs(narrowestSimilar([]), { questions: [] });
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/treat any brand it can source as acceptable/i);
    expect(text).toMatch(/within the requirements already saved/i);
    expect(text).toMatch(/everything about it stays as it is/i);
  });

  it("is honest when widening changes nothing today", () => {
    renderPrefs(narrowestSimilar(QUESTIONS), {
      flexibility: { exact_requests: 2, compatible_requests: 2, sourceable_alternatives: 0 },
    });
    expect(document.body.textContent).toMatch(/changes nothing you can see/i);
  });

  it("waits for the questions rather than showing the wrong ones", () => {
    renderPrefs(narrowestSimilar(QUESTIONS), { loading: true });
    expect(document.body.textContent).toMatch(/what is worth asking/i);
    expect(screen.queryByText(/It has to be whole bean/)).toBeNull();
  });

  it("explains that the questions were chosen, without claiming a model decided meaning", () => {
    renderPrefs(narrowestSimilar(QUESTIONS), { planned: true });
    const why = screen.getByText(/why is pool asking these/i);
    expect(why).toBeTruthy();
    const text = why.closest("details")?.textContent ?? "";
    expect(text).toMatch(/change which orders you could join/i);
    expect(text).toMatch(/never guesses what an answer means/i);
  });

  it("does not claim questions were chosen when they were not", () => {
    renderPrefs(narrowestSimilar(QUESTIONS), { planned: false });
    const text =
      screen.getByText(/why is pool asking these/i).closest("details")?.textContent ?? "";
    expect(text).toMatch(/everything Pool can establish/i);
    expect(text).not.toMatch(/picked the questions/i);
  });
});

describe("what each answer would reach", () => {
  it("shows the standing demand behind every value it offers", () => {
    const questions = withReach();
    renderPrefs(narrowestSimilar(questions), { questions });
    const text = document.body.textContent ?? "";

    /* Per value, because that is the shape of the decision: "would dark do as well?" is
       a question about dark, and a combined figure would be a number nobody stored. */
    expect(text).toMatch(/22 units standing/);
    expect(text).toMatch(/6 units standing/);
    expect(text).toMatch(/5 units standing/);
  });

  it("tells a keep question what insisting costs, in both currencies", () => {
    const questions = withReach();
    renderPrefs(narrowestSimilar(questions), { questions });
    const text = document.body.textContent ?? "";
    // Both currencies, as ratios rather than as a sentence per checkbox.
    expect(text).toMatch(/keeps 5 of 6 coffees/);
    expect(text).toMatch(/29 of 36 units/);
  });

  it("never turns a count into a forecast", () => {
    const questions = withReach();
    renderPrefs(narrowestSimilar(questions), { questions, flexibility: REACH });
    const text = document.body.textContent ?? "";
    for (const forecast of [
      /%/,
      /likely/i,
      /chance of/i,
      /probability/i,
      /odds/i,
      /guarantee/i,
      /you will get an order/i,
    ]) {
      expect(text).not.toMatch(forecast);
    }
    /* An order forming may be mentioned only as something Pool does not know. Written as
       a rule over every occurrence rather than a ban on the phrase, because the honest
       sentence and the dishonest one differ by one word. */
    for (const match of text.matchAll(/.{0,24}order will form/gi)) {
      expect(match[0]).toMatch(/whether an order will form/i);
    }
    expect(text).toMatch(/cannot tell you whether an order will form/i);
    /* And it does not tell anybody what to pick. */
    expect(text).toMatch(/only pick what you would actually accept/i);
    expect(text).not.toMatch(/you should|we recommend you|pick dark/i);
  });

  it("says nothing at all when the answer cannot change anything", () => {
    /* Every sourceable coffee has the same roast, so no answer here moves a cohort.
       A count in that situation is noise wearing the costume of information. */
    const flat = QUESTIONS.map((q) =>
      q.attribute === "roast" ? { ...q, reach: { ...ROAST_REACH, varies: false } } : q,
    );
    renderPrefs(narrowestSimilar(flat), { questions: flat });
    expect(document.body.textContent).not.toMatch(/units standing/);
  });

  it("shows nothing before the member has agreed to alternatives", () => {
    /* The reach only arrives with the plan, and the plan is only fetched on consent —
       so an exact-only form has no figures to leak. */
    const questions = withReach();
    renderPrefs(EXACT, { questions });
    expect(document.body.textContent).not.toMatch(/units standing/);
  });
});
