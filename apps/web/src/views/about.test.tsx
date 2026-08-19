/* The truth boundary, and the licence obligations that sit on it.
 *
 * Two different things are asserted here, and both are the kind that decay silently.
 *
 * ODbL and CC-BY-SA require attribution wherever the data is publicly used. Search
 * results carry it inline, but that only appears if somebody searches — so the durable
 * credit lives here, and a test keeps it from being tidied away in a copy pass.
 *
 * The second is the sharper one. Once real brands appear next to Pool's invented
 * supplier prices, "synthetic" has to say *which* things are synthetic. A page that
 * shows an Optimum Nutrition tub beside a wholesale price has to state plainly that the
 * price is not a quote anybody gave, or it is implying a relationship that does not
 * exist (AGENTS.md §8, §12).
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { About } from "./about";

afterEach(cleanup);

function renderAbout() {
  return render(
    <About
      health={null}
      demoConfig={null}
      memberCount={24}
      needCount={32}
      onBack={() => {}}
      onOpenTechnical={() => {}}
      onRun={() => {}}
      running={false}
    />,
  );
}

describe("what the product says about itself", () => {
  it("credits the catalogue the licence requires it to credit", () => {
    renderAbout();
    const text = document.body.textContent ?? "";
    expect(text).toMatch(/Open Food Facts/);
    expect(text).toMatch(/Open Database License|ODbL/);
    expect(text).toMatch(/CC-BY-SA/);

    const link = screen.getAllByRole("link", { name: /open food facts/i })[0];
    expect(link.getAttribute("href")).toMatch(/openfoodfacts\.org/);
  });

  it("says the supplier prices are invented, not merely that data is synthetic", () => {
    renderAbout();
    const text = document.body.textContent ?? "";
    // The specific claim, because "synthetic community" alone would leave a judge to
    // assume the price beside a real brand came from somewhere.
    expect(text).toMatch(/no wholesale relationship exists/i);
    expect(text).toMatch(/supplier price/i);
    expect(text).toMatch(/no manufacturer has any involvement/i);
  });

  it("separates what the catalogue supplies from what Pool computes", () => {
    renderAbout();
    const text = document.body.textContent ?? "";
    expect(text).toMatch(/supplies no price, case\s*size or supplier minimum/i);
  });

  it("does not claim a background scheduler it does not run", () => {
    renderAbout();
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/runs automatically every|scheduled scan runs/i);
  });
});
