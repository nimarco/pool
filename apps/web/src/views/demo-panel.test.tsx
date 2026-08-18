import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, DemoConfig, Health } from "../api";
import { DemoPanel } from "./demo-panel";

const config: DemoConfig = {
  public_demo: true,
  live_agent_available: true,
  live_agent_runtime: "runtime-v4",
  region: "us-east-1",
  max_live_per_session: 1,
  payments: "simulated",
  purchase: "simulated",
};

const health: Health = {
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
  agent_tools: [],
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("demo truth labels", () => {
  it("separates live discovery, deterministic lifecycle, and simulated rails", () => {
    vi.spyOn(api, "needs").mockImplementation(() => new Promise(() => undefined));

    render(
      <DemoPanel
        open
        onClose={() => {}}
        state={null}
        health={health}
        demoConfig={config}
        identity={{ id: "hh_navarro", display_name: "Rosa N." }}
        onIdentity={() => {}}
        onReset={() => {}}
        onRefresh={async () => {}}
        onAbout={() => {}}
        onTechnical={() => {}}
        onLifecycle={() => {}}
        onOperations={() => {}}
        onShowcase={() => {}}
      />,
    );

    expect(screen.getByText(/AgentCore \/ Bedrock available · us-east-1/i)).toBeTruthy();
    expect(screen.getByText("deterministic planner")).toBeTruthy();
    expect(screen.getAllByText("simulated").length).toBeGreaterThan(0);
    expect(screen.queryByText(/model offline/i)).toBeNull();
  });
});
