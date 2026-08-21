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

function renderPrefs(value: NeedPreferences = EXACT) {
  const onChange = vi.fn();
  const view = render(
    <Preferences questions={QUESTIONS} value={value} onChange={onChange} />,
  );
  return { onChange, view };
}

describe("the flexibility questions", () => {
  it("starts on exact-only and asks nothing else", () => {
    renderPrefs();
    expect(screen.getByLabelText(/only this exact product/i)).toBeTruthy();
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

  it("opens on the narrowest reading of 'similar is okay'", async () => {
    const { onChange } = renderPrefs();
    await userEvent.click(screen.getByLabelText(/similar products are okay/i));

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
    await userEvent.click(screen.getByLabelText(/only this exact product/i));
    expect(onChange).toHaveBeenCalledWith(EXACT);
  });

  it("offers nothing to widen when the product has no curated questions", () => {
    const onChange = vi.fn();
    render(<Preferences questions={[]} value={EXACT} onChange={onChange} />);
    const flexible = screen.getByLabelText(/similar products are okay/i) as HTMLInputElement;
    expect(flexible.disabled).toBe(true);
    expect(document.body.textContent).toMatch(/it will only buy this one/i);
  });

  it("marks which value is the member's own, so the pills are not a quiz", () => {
    renderPrefs(narrowestSimilar(QUESTIONS));
    const medium = screen.getByLabelText(/^Medium/).closest("label");
    expect(medium?.textContent).toMatch(/yours/);
  });
});
