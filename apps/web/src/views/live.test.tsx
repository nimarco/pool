import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { DemoConfig, Health, PoolExecutionProof } from "../api";
import { AgentExecution } from "./live";

const CONFIG: DemoConfig = {
  public_demo: true,
  live_agent_available: true,
  live_agent_runtime: "pool-runtime-v4",
  region: "us-east-1",
  max_live_per_session: 1,
  payments: "simulated",
  purchase: "simulated",
};

const HEALTH: Health = {
  ok: true,
  repository: "dynamodb",
  routing_provider: "haversine",
  model_provider: "offline",
  model_id: "offline",
  payment_provider: "simulated",
  payment_mode: "simulated",
  purchase_executor: "simulated",
  purchase_simulated: true,
  schedules_enabled: false,
  bounds: {
    max_iterations: 8,
    max_tool_calls: 25,
    max_duplicate_tool_calls: 2,
    workflow_timeout_seconds: 45,
  },
  agent_tools: [
    { name: "list_latent_demand", kind: "read" },
    { name: "create_candidate_pool", kind: "act" },
  ],
};

const PROOF: PoolExecutionProof = {
  pool_id: "pool_exact",
  created_by_run: "run_exact",
  run_id: "run_exact",
  relation_verified: true,
  execution: {
    service: "Amazon Bedrock AgentCore Runtime",
    live: true,
    region: "us-east-1",
  },
  workspace_readback: {
    run_recorded: true,
    pool_recorded: true,
    same_workspace: true,
  },
  run: {
    run_id: "run_exact",
    trigger: "manual_scan",
    outcome: "pool_created",
    iterations: 7,
    tool_calls: ["list_latent_demand", "create_candidate_pool"],
    termination_reason: "candidate_pool_created",
    model_provider: "bedrock",
    model_id: "amazon.nova-lite-v1:0",
    duration_ms: 7090,
    input_tokens: 23842,
    output_tokens: 516,
    started_at: "2026-08-18T12:00:00Z",
  },
};

afterEach(cleanup);

describe("stored execution evidence", () => {
  it("renders the exact run-to-pool readback before the secondary run action", () => {
    render(
      <AgentExecution
        config={CONFIG}
        health={HEALTH}
        result={null}
        busy={false}
        onRun={() => {}}
        runs={[
          {
            ...PROOF.run,
            run_id: "run_unrelated",
            tool_calls: ["unrelated_tool"],
          },
        ]}
        proof={PROOF}
      />,
    );

    const proof = screen.getByTestId("stored-execution-proof");
    expect(within(proof).getAllByText("run_exact")).toHaveLength(2);
    expect(within(proof).getByText("pool_exact")).toBeTruthy();
    expect(within(proof).getByText(/matches run id/i)).toBeTruthy();
    expect(within(proof).getByText(/verified · run \+ pool present/i)).toBeTruthy();
    expect(
      within(proof).getByText(
        /browser → Lambda → AgentCore → Bedrock \/ Strands → typed tools → DynamoDB → browser/i,
      ),
    ).toBeTruthy();
    expect(within(proof).getByText(/amazon\.nova-lite-v1:0/)).toBeTruthy();
    expect(within(proof).getByText("candidate_pool_created")).toBeTruthy();
    expect(within(proof).queryByText("unrelated_tool")).toBeNull();

    const runAgain = screen.getByText("Run again", { selector: "strong" });
    expect((runAgain.closest("details") as HTMLDetailsElement).open).toBe(false);
    expect(proof.compareDocumentPosition(runAgain) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});

describe("what an in-flight invocation is allowed to claim", () => {
  it("resolves no hop below the request the browser actually sent", () => {
    const { container } = render(
      <AgentExecution
        config={CONFIG}
        health={HEALTH}
        result={null}
        busy
        onRun={() => {}}
        runs={[]}
        proof={null}
      />,
    );

    const hops = Array.from(container.querySelectorAll(".hop"));
    expect(hops.length).toBeGreaterThan(1);
    // Exactly one row is resolved — the send — and nothing is dressed up as running.
    expect(hops.filter((h) => h.classList.contains("done"))).toHaveLength(1);
    expect(hops[0].classList.contains("done")).toBe(true);
    expect(container.querySelectorAll(".hop .spinner")).toHaveLength(0);
    expect(container.querySelectorAll(".hop.active")).toHaveLength(0);
    expect(screen.getByText(/no intermediate stage is being inferred/i)).toBeTruthy();
  });

  it("leaves every hop unresolved when the invocation failed", () => {
    const { container } = render(
      <AgentExecution
        config={CONFIG}
        health={HEALTH}
        result={{
          ok: false,
          live: false,
          classification: "ambiguous_remote_execution",
          remote_may_still_write: true,
          allow_local_fallback: false,
          refresh_state: true,
          reason: "The live request did not complete.",
        }}
        busy={false}
        onRun={() => {}}
        runs={[]}
        proof={null}
      />,
    );

    // A failure must not guess which hop broke, and must not retroactively claim the
    // ones before it succeeded.
    const hops = Array.from(container.querySelectorAll(".hop"));
    expect(hops.filter((h) => h.classList.contains("done"))).toHaveLength(1);
    expect(screen.getByText(/The live request did not complete/)).toBeTruthy();
  });
});

describe("what the screen may claim when the live route is not offered", () => {
  /* The two unavailable cases are different claims, and saying the wrong one is the
     single most damaging sentence on this page. The public judge demo has a runtime ARN
     and the kill switch off, and the screen used to answer that with "No AgentCore
     runtime is configured here" — which reads as *this project has no AgentCore
     deployment*, the opposite of the truth. */

  const off = (state: DemoConfig["live_agent_state"]): DemoConfig => ({
    ...CONFIG,
    live_agent_available: false,
    live_agent_runtime: "",
    region: "",
    live_agent_state: state,
  });

  const renderOff = (state: DemoConfig["live_agent_state"]) =>
    render(
      <AgentExecution
        config={off(state)}
        health={HEALTH}
        result={null}
        busy={false}
        onRun={() => {}}
        runs={[]}
        proof={null}
      />,
    );

  it("says the paid route is switched off, not that the runtime does not exist", () => {
    renderOff("switched_off");
    expect(screen.getByText(/Live AgentCore execution is/i)).toBeTruthy();
    expect(screen.getByText(/has been invoked and verified/i)).toBeTruthy();
    expect(screen.queryByText(/No AgentCore runtime is configured/i)).toBeNull();
  });

  it("never implies the visible runs used a model", () => {
    renderOff("switched_off");
    const body = document.body.textContent ?? "";
    expect(body).toMatch(/deterministic planner/i);
    expect(body).toMatch(/token/i);
    // The chip a judge reads at a glance has to agree with the paragraph under it.
    expect(screen.getByText("switched off here")).toBeTruthy();
    expect(screen.queryByText("live")).toBeNull();
  });

  it("still says so plainly when there genuinely is no runtime", () => {
    renderOff("not_configured");
    expect(screen.getByText(/No AgentCore runtime is configured for this deployment/i)).toBeTruthy();
    expect(screen.getByText("not configured")).toBeTruthy();
  });

  it("does not describe a hosted deployment's own runs as local", () => {
    renderOff("switched_off");
    // "local rehearsal" was served by the deployed judge demo as often as by a laptop.
    expect(document.body.textContent ?? "").not.toMatch(/local rehearsal/i);
  });
});
