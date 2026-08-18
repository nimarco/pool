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
