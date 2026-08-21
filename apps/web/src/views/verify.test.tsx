/** What the verification page is allowed to promise.
 *
 *  It exists for a sceptic, so the failure that would matter most is not a broken button
 *  — it is a page that quietly guarantees the good outcome. Somebody who keeps every
 *  conservative default here gets a truthful refusal: there is compatible demand, but not
 *  enough of it under their own rules to buy against. That is the software working, and a
 *  page that had told them an order would appear would have turned a correct answer into
 *  an apparent bug.
 *
 *  So these tests are mostly about absence. They are worth having anyway, because "do not
 *  promise the result" is exactly the kind of rule that erodes one helpful sentence at a
 *  time.
 */
import { describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";

import * as apiModule from "../api";
import { Verify } from "./verify";

const HEALTH: apiModule.Health = {
  ok: true,
  repository: "memory",
  routing_provider: "deterministic",
  model_provider: "offline",
  model_id: "offline-deterministic-planner",
  payment_provider: "simulated",
  payment_mode: "simulated",
  purchase_executor: "simulated",
  purchase_simulated: true,
  schedules_enabled: false,
  bounds: {
    max_iterations: 8,
    max_tool_calls: 25,
    max_duplicate_tool_calls: 2,
    workflow_timeout_seconds: 120,
  },
  agent_tools: [],
};

function renderVerify() {
  vi.spyOn(apiModule.api, "setVerifyScope").mockImplementation(() => {});
  render(<Verify health={HEALTH} onStart={() => {}} onHome={() => {}} />);
  return document.body.textContent ?? "";
}

describe("the verification page", () => {
  it("does not promise that an order will form", () => {
    const text = renderVerify();
    for (const promise of [
      /you will get an order/i,
      /an order will form/i,
      /pool will form an order/i,
      /guaranteed/i,
      /always forms/i,
    ]) {
      expect(text).not.toMatch(promise);
    }
  });

  it("says plainly that watching is one of the real answers", () => {
    const text = renderVerify();
    expect(text).toMatch(/not necessarily an order/i);
    expect(text).toMatch(/leave pool watching/i);
  });

  it("never tells the visitor which answer to give", () => {
    /* The one instruction that would void the whole exercise: a page that says "pick
       dark roast so it works" has scripted the result it is asking somebody to check. */
    const text = renderVerify();
    for (const scripted of [
      /select dark/i,
      /choose dark/i,
      /pick dark/i,
      /say yes to/i,
      /accept the dark/i,
      /so the demo works/i,
    ]) {
      expect(text).not.toMatch(scripted);
    }
    expect(text).toMatch(/answer them the way you actually buy/i);
  });

  it("carries no probability, percentage or likelihood claim", () => {
    const text = renderVerify();
    expect(text).not.toMatch(/%|likely|chance of|probability|odds/i);
  });

  it("states what is synthetic before asking anybody to trust the result", () => {
    const text = renderVerify();
    expect(text).toMatch(/synthetic/i);
    expect(text).toMatch(/simulated/i);
    expect(text).toMatch(/has not asked your browser where you are/i);
  });

  it("says the answers can be taken back", () => {
    const text = renderVerify();
    expect(text).toMatch(/editable/i);
    expect(text).toMatch(/widen them again/i);
  });
});
