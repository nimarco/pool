/** The technical proof says which thing drove the loop, and calls it by its own name.
 *
 *  The public `/verify` run executes the real Strands loop against the **deterministic
 *  offline planner**: same tools, same bounds, same guarded writes, no model. The panel
 *  used to label its iterations "Model calls" and to narrate "The model chose…" three
 *  lines above a provider reading `offline` and a token count reading zero — a claim the
 *  same panel disproves, on the one surface whose entire purpose is being checkable.
 *
 *  So the vocabulary derives from `run.model_provider`, which is what the coordinator
 *  actually recorded. These tests pin both sides of that: an offline run is never
 *  described as a model, and a Bedrock run still gets the words that are true of it.
 *
 *  No model is called here in either direction. The Bedrock case is a serialised run
 *  record, which is exactly what the surface reads in production.
 */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NeedCoordination } from "../api";
import * as apiModule from "../api";
import { WhyThisOrder } from "./why";

function coordination(
  run: Partial<NonNullable<NeedCoordination["run"]>>,
  extra: Partial<NeedCoordination> = {},
): NeedCoordination {
  return {
    need_id: "need_1",
    event: {
      event_id: "cev_1",
      status: "completed",
      run_id: "run_1",
      outcome: "pool_created",
      terminal_reason: "candidate_pool_created",
      pool_id: "pool_1",
      formed_order: true,
      reached_a_verdict: true,
    },
    clarification: null,
    evidence_run_id: "run_1",
    run: {
      run_id: "run_1",
      trigger: "need_declared",
      objective: "member",
      model_provider: "offline",
      model_id: "offline-deterministic-planner",
      outcome: "pool_created",
      termination_reason: "completed",
      iterations: 5,
      input_tokens: 0,
      output_tokens: 0,
      duration_ms: 3350,
      tool_calls: [
        { name: "list_cohort_strategies", ok: true },
        { name: "evaluate_cohort_strategy", ok: true },
        { name: "create_pool_from_strategy", ok: true },
      ],
      bounds: {
        max_iterations: 8,
        max_tool_calls: 25,
        max_strategy_listings: 1,
        max_strategy_evaluations: 3,
        max_strategy_pool_creations: 1,
      },
      ...run,
    },
    considered: [],
    investigated: [],
    chosen: null,
    exclusion_codes: {},
    order: null,
    not_yet: {
      host_accepted: false,
      final_price_issued: false,
      card_authorised: false,
      purchased: false,
    },
    ...extra,
  };
}

const OFFLINE_PLAN: NonNullable<NeedCoordination["clarification"]> = {
  plan_id: "cpl_a",
  run_id: "run_clarify",
  status: "active",
  family: "roast_coffee",
  schema_version: 1,
  question_definition_version: 1,
  offered: ["q_roast", "q_form", "q_caffeine"],
  asked: ["q_roast", "q_form", "q_caffeine"],
  model_provider: "offline",
  model_id: "offline-deterministic-planner",
  iterations: 2,
  input_tokens: 0,
  output_tokens: 0,
};

async function openProof(data: NeedCoordination) {
  vi.spyOn(apiModule.api, "needCoordination").mockResolvedValue(data);
  render(<WhyThisOrder needId="need_1" productName="Kestrel medium roast" unit="bag" onBack={() => {}} />);
  await waitFor(() =>
    expect(
      screen.getByRole("heading", { name: "Technical proof for this run" }),
    ).toBeTruthy(),
  );
  await userEvent.click(screen.getByRole("button", { name: "Show" }));
}

/** Every word on the open proof panel, for the "nowhere on this surface" assertions. */
function proofText(): string {
  return document.body.textContent ?? "";
}

describe("technical proof, offline run", () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(cleanup);

  it("reports the provider it actually ran on", async () => {
    await openProof(coordination({}));
    expect(proofText()).toContain("offline · offline-deterministic-planner");
  });

  it("counts planner iterations rather than model calls", async () => {
    await openProof(coordination({}));
    expect(screen.getByText("Planner iterations")).toBeTruthy();
    expect(screen.queryByText("Model calls")).toBeNull();
  });

  it("says zero model tokens, and says why they are zero", async () => {
    await openProof(coordination({}));
    expect(screen.getByText("Model tokens")).toBeTruthy();
    expect(screen.getByText("0 in · 0 out")).toBeTruthy();
    expect(proofText()).toContain("deterministic offline planner");
    expect(proofText()).toContain("which is why the token counts above are zero");
  });

  it("never says the model chose anything", async () => {
    await openProof(coordination({}, { clarification: OFFLINE_PLAN }));
    const text = proofText();
    expect(text).toContain("The offline planner chose which option to investigate");
    expect(text).toContain("The offline planner selected which of the approved questions");
    expect(text).not.toMatch(/\bThe model\b/);
    expect(text).not.toMatch(/model calls/i);
  });

  it("does not let the offline path be mistaken for Nova Lite", async () => {
    await openProof(coordination({}, { clarification: OFFLINE_PLAN }));
    const text = proofText();
    expect(text).not.toMatch(/nova/i);
    // AgentCore is named once, and only to say that the live path is the *other* one.
    expect(text).toContain("separate, explicitly requested action");
  });
});

describe("technical proof, live Bedrock run", () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(cleanup);

  const bedrock = {
    model_provider: "bedrock",
    model_id: "us.amazon.nova-lite-v1:0",
    iterations: 2,
    input_tokens: 5513,
    output_tokens: 133,
  };

  it("shows the real provider and model", async () => {
    await openProof(coordination(bedrock));
    expect(proofText()).toContain("bedrock · us.amazon.nova-lite-v1:0");
  });

  it("is allowed to say model, because a model is what ran", async () => {
    await openProof(coordination(bedrock));
    expect(screen.getByText("Model iterations")).toBeTruthy();
    expect(screen.getByText("2 of 8 allowed")).toBeTruthy();
    expect(proofText()).toContain("The model chose which option to investigate");
  });

  it("reports token counts that are real, and drops the offline disclaimer", async () => {
    await openProof(coordination(bedrock));
    expect(screen.getByText("Tokens")).toBeTruthy();
    expect(screen.getByText("5513 in · 133 out")).toBeTruthy();
    expect(proofText()).not.toContain("deterministic offline planner");
  });

  it("labels each run by its own provider when the two differ", async () => {
    /* The planning run and the coordination run are deliberately separate runs. A
       deployment can have one live and the other not, and each panel says which. */
    await openProof(coordination(bedrock, { clarification: OFFLINE_PLAN }));
    const text = proofText();
    expect(text).toContain("The model chose which option to investigate");
    expect(text).toContain("The offline planner selected which of the approved questions");
  });
});

describe("historical clarification proof", () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(cleanup);

  it("shows the plan the event recorded, and says when it has been superseded", async () => {
    await openProof(
      coordination({}, { clarification: { ...OFFLINE_PLAN, status: "superseded" } }),
    );
    expect(proofText()).toContain("cpl_a");
    expect(screen.getByText("Plan status")).toBeTruthy();
    expect(screen.getByText("superseded")).toBeTruthy();
  });

  it("says nothing about questions when the declaration asked none", async () => {
    await openProof(coordination({}, { clarification: null }));
    expect(screen.queryByText("What Pool decided to ask, before any of this")).toBeNull();
  });
});
