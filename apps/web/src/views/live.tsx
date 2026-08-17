/* The one action that leaves this machine.
 *
 * Everything else on this site runs deterministically on the server, which is
 * deliberate: a demo that needs a paid model call to render a page is a demo that
 * breaks in front of someone. This screen is the exception, and it is the exception
 * that proves the agent is real — a genuine invocation of Pool's coordinator deployed
 * on Amazon Bedrock AgentCore Runtime.
 *
 * The honesty rule shapes the waiting state. A browser making one HTTPS request can
 * observe exactly two things: when it sent, and when it got an answer. So nothing here
 * animates a fake journey through AWS. What it shows instead is true and, for the ten
 * to twenty seconds involved, more interesting: the path the request takes, the caps it
 * runs under, and the *whole menu of tools the agent may choose from* — which the result
 * then resolves into the ones it actually chose. There is no code path that fabricates
 * a run (AGENTS.md §8).
 */

import { useEffect, useRef, useState } from "react";
import { DemoConfig, Health, LiveAgentResult, RunSummary } from "../api";
import {
  ActorTag,
  Block,
  Chip,
  Empty,
  Fact,
  Figure,
  IconCheck,
  IconCloud,
  IconDot,
  Trace,
  TracePills,
} from "../ui";

/* ------------------------------------------------------------------ the path */

/** The hops a live invocation makes, in order. This is the deployed architecture, not
 *  a guess: the browser calls the demo Lambda, whose execution role signs
 *  `InvokeAgentRuntime` against one runtime ARN, and the runtime runs the same
 *  coordinator this repository's tests drive. */
const HOPS = [
  { name: "Your browser", note: "no AWS credential, ever" },
  { name: "Lambda Function URL", note: "signs the call with its execution role" },
  { name: "Bedrock AgentCore Runtime", note: "isolated session, generated server-side" },
  { name: "Strands agent loop", note: "bounded: iterations, tool calls, wall clock" },
  { name: "Amazon Bedrock", note: "model inference" },
  { name: "Pool's typed tools", note: "the only way the model reaches any state" },
];

function HopChain({ state }: { state: "idle" | "flight" | "done" | "failed" }) {
  return (
    <div className="hops">
      {HOPS.map((hop, i) => {
        // Only the first hop's completion is observable from here: the browser knows it
        // sent. Everything below it is where the request *is*, not something this page
        // watched happen — so in flight they read as pending, and they resolve only when
        // a real answer comes back through all of them. A failure leaves them unresolved
        // rather than guessing which hop broke; the reason underneath says what AWS
        // reported.
        const done = state === "done" || (state !== "idle" && i === 0);
        const active = state === "flight" && i > 0;
        return (
          <div
            key={hop.name}
            className={`hop${done ? " done" : ""}${active ? " active" : ""}`}
          >
            <span className="hop-mark">
              {done ? <IconCheck /> : active ? <span className="spinner" /> : <IconDot />}
            </span>
            <span className="hop-name">{hop.name}</span>
            <span className="hop-note">{hop.note}</span>
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------- elapsed */

function Elapsed({ running }: { running: boolean }) {
  const [ms, setMs] = useState(0);
  const start = useRef(0);

  useEffect(() => {
    if (!running) return undefined;
    start.current = performance.now();
    setMs(0);
    const id = window.setInterval(() => setMs(performance.now() - start.current), 100);
    return () => window.clearInterval(id);
  }, [running]);

  if (!running) return null;
  return <span className="elapsed">{(ms / 1000).toFixed(1)}s elapsed</span>;
}

/* -------------------------------------------------------------- tool catalogue */

/** The menu, with whatever the agent picked marked. Before a run this is "here are the
 *  twelve doors"; after one it is "here is the sequence it opened, in order". */
function ToolCatalogue({
  tools,
  chosen,
}: {
  tools: { name: string; kind: string }[];
  chosen: string[];
}) {
  const order = new Map<string, number[]>();
  chosen.forEach((name, i) => {
    order.set(name, [...(order.get(name) ?? []), i + 1]);
  });
  return (
    <div className="rows" style={{ borderTop: "1px solid var(--rule)" }}>
      {tools.map((tool) => {
        const picks = order.get(tool.name) ?? [];
        return (
          <div
            key={tool.name}
            className="row"
            style={{ paddingInline: 0, opacity: chosen.length && picks.length === 0 ? 0.42 : 1 }}
          >
            <div className="row-body">
              <span className="mono" style={{ fontSize: 13, fontWeight: 600 }}>
                {tool.name}
              </span>{" "}
              <span className="tiny faint">
                {tool.kind === "read"
                  ? "reads only"
                  : tool.kind === "act"
                    ? "commits something"
                    : "ends the run"}
              </span>
            </div>
            <div className="row-tail">
              {picks.length > 0 ? (
                <span className="mono" style={{ color: "var(--moss)", fontSize: 12 }}>
                  called {picks.map((p) => `#${p}`).join(", ")}
                </span>
              ) : chosen.length > 0 ? (
                <span className="tiny faint">not chosen</span>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ---------------------------------------------------------------------- view */

/** The technical evidence for one coordination, shown inside a pool's record.
 *
 * It is not a page in the product's navigation. A student buying protein powder has no
 * use for a Bedrock model id; a judge deciding whether the agent is real has nothing but
 * use for it. So it hangs off the pool it explains. */
export function AgentExecution({
  config,
  health,
  result,
  busy,
  onRun,
  runs,
  standalone,
}: {
  config: DemoConfig | null;
  health: Health | null;
  result: LiveAgentResult | null;
  busy: boolean;
  onRun: () => void;
  runs: RunSummary[];
  /** Rendered as its own destination in Showcase mode rather than inside a pool's
   *  record, where the record already supplies the context and the title. */
  standalone?: boolean;
}) {
  const available = Boolean(config?.live_agent_available);
  const tools = health?.agent_tools ?? [];
  const chosen = result?.ok ? result.run.tool_calls.map((t) => t.name) : [];
  const state = busy ? "flight" : result?.ok ? "done" : result ? "failed" : "idle";

  return (
    <div className="stack">
      <header className="stack-sm">
        {standalone ? (
          <h1 className="title" style={{ maxWidth: "22ch" }}>
            One button on this site actually leaves it
          </h1>
        ) : (
          <h2 className="title" style={{ maxWidth: "24ch" }}>
            How Pool coordinated this
          </h2>
        )}
        <p className="lede">
          Pool's coordinator runs on this server for every action you take — the real
          Strands event loop, the real tools, the real domain arithmetic, driven by a
          deterministic planner rather than a model so the demo is free and cannot break.
          The same coordinator is also deployed on AWS, and you can make it run there.
        </p>
      </header>

      <section className="live-panel">
        <div className="live-head">
          <IconCloud />
          <h3 style={{ fontSize: 14.5, fontWeight: 600 }}>
            Invoke the deployed agent on Amazon Bedrock AgentCore Runtime
          </h3>
          <span style={{ marginLeft: "auto", display: "flex", gap: 10, alignItems: "center" }}>
            <Elapsed running={busy} />
            {available ? <Chip tone="live">live</Chip> : <Chip>not on this deployment</Chip>}
          </span>
        </div>

        <div className="panel-pad stack-sm">
          {available ? (
            <>
              <p className="small">
                Runs Pool's coordinator as deployed in <strong>{config?.region}</strong> —
                a real model, the real Strands loop, the real typed tools, inside a runtime
                session generated here and used once.
              </p>
              <p className="tiny muted">
                It works from its own copy of the community and leaves your pool alone.
                That is a property of the deployment rather than a demo choice: the runtime
                is configured to hold no shared state, so each invocation is isolated from
                every other one and from this session. What it proves is that the
                coordination you have been driving is the same code, running on AWS.
              </p>
              <p className="tiny muted">
                Capped at {config?.max_live_per_session} runs per visitor because it
                spends model tokens. The client sends an action name, never a prompt: the
                server owns the instruction, so a stranger with this URL cannot write the
                agent's orders.
              </p>
              <div className="btn-row" style={{ marginTop: 4 }}>
                <button className="btn btn-primary btn-lg" onClick={onRun} disabled={busy}>
                  {busy ? <span className="spinner" /> : <IconCloud />}
                  {busy ? "Waiting for AWS…" : "Run the deployed agent"}
                </button>
                {busy ? (
                  <span className="tiny muted">
                    Typically ten to twenty seconds. Nothing below is affected either way.
                  </span>
                ) : null}
              </div>
            </>
          ) : (
            <p className="small muted prose">
              This build has no AgentCore runtime configured, so the button is not offered
              rather than being offered and failing. The deployed public demo has it
              switched on; a local run keeps the same architecture below, with an offline
              planner in the model's place and no AWS call at all.
            </p>
          )}
        </div>

        <HopChain state={state} />

        {result && !result.ok ? (
          <div className="panel-pad">
            <div className="banner banner-warn">
              <span>{result.reason}</span>
            </div>
          </div>
        ) : null}
      </section>

      {result?.ok ? (
        <section className="panel reveal">
          <div className="panel-head">
            <h3>{result.service}</h3>
            <Chip tone="ok">{result.run.outcome.replace(/_/g, " ")}</Chip>
            <span className="spacer" />
            <ActorTag actor="agent" label="Chosen by the model" />
          </div>
          <div className="panel-pad stack-sm">
            <div className="grid grid-3">
              <Figure
                label="Time inside the agent"
                value={`${result.run.duration_ms ?? 0} ms`}
                small
                sub="measured by the runtime itself"
              />
              <Figure
                label="Time inside AWS"
                value={`${result.wall_ms} ms`}
                small
                sub="the Lambda's own measurement of the invocation"
              />
              <Figure
                label="Tokens in / out"
                value={`${result.run.input_tokens ?? 0} / ${result.run.output_tokens ?? 0}`}
                small
                sub="what this single run cost in model usage"
              />
            </div>
            <div className="facts">
              <Fact label="Runtime" value={<span className="mono">{result.runtime}</span>} />
              <Fact label="Region" value={<span className="mono">{result.region}</span>} />
              <Fact label="Model" value={<span className="mono">{result.run.model_id}</span>} />
              <Fact label="Iterations" value={result.run.iterations} />
              <Fact
                label="Stopped because"
                value={<span className="mono">{result.run.termination_reason}</span>}
              />
              <Fact label="People it asked" value={result.run.hitl_decisions_created} />
            </div>
          </div>
          <div className="panel-head">
            <h3>What it chose to do, in order</h3>
          </div>
          <Trace calls={result.run.tool_calls} />
          <div className="panel-pad">
            <p className="tiny muted">{result.note}</p>
          </div>
        </section>
      ) : null}

      <section className="panel">
        <div className="panel-head">
          <h3>{chosen.length > 0 ? "The twelve doors, and the ones it opened" : "What the agent may reach"}</h3>
          <span className="spacer" />
          <span className="tiny faint">served from the running agent's own tool list</span>
        </div>
        <div className="panel-pad">
          <p className="small muted prose" style={{ marginBottom: 14 }}>
            The model has no shell, no query language, and no generic mutation. It reaches
            the world through these typed functions and nothing else. Reads cannot change
            anything; the ones that commit are idempotent by an explicit key, because
            agent systems retry and a repeated <span className="mono">create_candidate_pool</span>{" "}
            must not produce two pools.
          </p>
          {tools.length === 0 ? (
            <Empty>The tool catalogue was not available from this server.</Empty>
          ) : (
            <ToolCatalogue tools={tools} chosen={chosen} />
          )}
          {health ? (
            <p className="tiny muted" style={{ marginTop: 14 }}>
              Every run is bounded inside the event loop, not by asking the model nicely:{" "}
              {health.bounds.max_iterations} iterations, {health.bounds.max_tool_calls} tool
              calls, {health.bounds.max_duplicate_tool_calls} identical calls before it is
              treated as a loop, {health.bounds.workflow_timeout_seconds}s wall clock. A run
              that hits one ends loudly as a recorded fault, never a silent truncation that
              looks like an answer.
            </p>
          ) : null}
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>Runs on this server</h3>
          <span className="spacer" />
          <span className="tiny faint">
            no model reasoning text is stored, and tool arguments are kept as hashes
          </span>
        </div>
        {runs.length === 0 ? (
          <Empty>Nothing has run yet in this session.</Empty>
        ) : (
          <div className="rows">
            {runs.map((r) => (
              <div key={r.run_id} className="row">
                <div className="row-body">
                  <div className="row-title">
                    {r.trigger.replace(/_/g, " ")}
                    <Chip tone={r.outcome.startsWith("pool") ? "ok" : "info"}>
                      {r.outcome.replace(/_/g, " ")}
                    </Chip>
                  </div>
                  <div className="tiny muted">
                    {r.iterations} iterations · {r.termination_reason} · {r.model_provider}
                    {r.duration_ms !== null ? ` · ${r.duration_ms} ms` : ""} ·{" "}
                    {r.input_tokens ?? 0}/{r.output_tokens ?? 0} tokens
                  </div>
                  <TracePills names={r.tool_calls} />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <Block title="What is running where">
        <div className="arch">
          {[
            ["React app", "one Lambda serves it from the same origin as the API — no CORS, no bucket"],
            ["Lambda Function URL", "23 allowlisted paths of 45; everything else 404s"],
            ["DynamoDB", "single table, on-demand; each visitor isolated by partition, 24 h TTL"],
            ["Bedrock AgentCore Runtime", "hosts the coordinator; AWS_IAM inbound auth, one runtime ARN"],
            ["Amazon Bedrock", "model inference, reached through Strands"],
            ["CloudWatch", "structured run records correlated by run id, 14-day retention"],
          ].map(([name, role]) => (
            <div key={name} className="arch-tier">
              <span className="arch-name">{name}</span>
              <span className="arch-role">{role}</span>
            </div>
          ))}
        </div>
      </Block>
    </div>
  );
}
