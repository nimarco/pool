/* The technical view of the one action that leaves this machine.
 *
 * Pressing "Find opportunities" in the Product invokes the coordinator deployed on
 * Amazon Bedrock AgentCore Runtime, bound to this session's own workspace. This screen
 * prioritizes the stored proof of that completed invocation. A fresh invocation remains
 * available only as a collapsed, secondary auditor control.
 *
 * The honesty rule shapes the waiting state. A browser making one HTTPS request can
 * observe exactly two things: when it sent, and when it got an answer. So nothing here
 * animates a fake journey through AWS. What it shows instead is true and, for the ten
 * to twenty seconds involved, more interesting: the path the request takes, the caps it
 * runs under, and the *whole menu of tools the agent may choose from* — which the result
 * then resolves into the ones it actually chose. There is no code path that fabricates
 * a run (AGENTS.md §8).
 *
 * The result panel deliberately separates two things that look alike. The run summary is
 * the agent's account of what it did. `observed` is what the database held afterwards,
 * read back by the server from the same table it serves every other page from. Only the
 * second one is evidence.
 */

import { useEffect, useRef, useState } from "react";
import {
  DemoConfig,
  Health,
  LiveAgentResult,
  PoolExecutionProof,
  RunSummary,
} from "../api";
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
  { name: "Lambda", note: "validates the workspace and signs one runtime call" },
  { name: "Bedrock AgentCore Runtime", note: "isolated session, generated server-side" },
  { name: "Strands + Amazon Bedrock", note: "bounded model-driven tool selection" },
  { name: "Pool's typed tools", note: "the only way the model reaches any state" },
  { name: "Deterministic domain services", note: "money, policy, allocation and writes" },
  { name: "DynamoDB", note: "authoritative state in this session's partition" },
  { name: "Your browser", note: "re-reads the stored run and resulting pool" },
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
            key={`${i}-${hop.name}`}
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

/** What each effect label means, in a judge's words rather than the code's.
 *
 *  Served from `/api/health`, which serves the agent's own `TOOL_SURFACE`, so these are
 *  the same four kinds the model is handed. `record` exists because three kinds could
 *  not describe the tool surface honestly: the host search writes a candidate
 *  evaluation and opens recruiting, which is neither inert nor a commitment anyone can
 *  observe. Calling it a read — which this page did — was the inaccuracy, not the
 *  writing. */
const TOOL_EFFECT: Record<string, string> = {
  read: "reads only",
  record: "records its working state",
  act: "commits something",
  end: "ends the run",
};

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
              <span className="tiny faint">{TOOL_EFFECT[tool.kind] ?? tool.kind}</span>
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

/* ---------------------------------------------------------- stored run proof */

function StoredExecutionProof({
  proof,
}: {
  proof: PoolExecutionProof;
}) {
  const run = proof.run;
  const isLive = proof.execution.live;
  return (
    <section className="panel reveal" data-testid="stored-execution-proof">
      <div className="panel-head">
        <h3>Technical proof for this run</h3>
        <Chip tone={isLive ? "live" : "info"}>
          {isLive ? "Amazon Bedrock AgentCore · live" : run.model_provider}
        </Chip>
        <span className="spacer" />
        <ActorTag actor="agent" label="Stored causal record" />
      </div>
      <div className="panel-pad stack-sm">
        <p className="small prose">
          The server read this pool and this run back from the same workspace. The pool’s
          stored <span className="mono">created_by_run</span> value is the exact run id
          below; this is not a “latest run” guess made by the browser.
        </p>
        <div className="facts">
          <Fact
            label="Service"
            value={proof.execution.service}
          />
          <Fact label="Region" value={<span className="mono">{proof.execution.region}</span>} />
          <Fact
            label="Model provider / model"
            value={<span className="mono">{run.model_provider} / {run.model_id}</span>}
          />
          <Fact label="Run id" value={<span className="mono">{run.run_id}</span>} />
          <Fact label="Resulting pool id" value={<span className="mono">{proof.pool_id}</span>} />
          <Fact
            label="Pool created_by_run"
            value={<span className="mono">{proof.created_by_run}</span>}
          />
          <Fact label="Outcome" value={run.outcome.replace(/_/g, " ")} />
          <Fact
            label="Termination"
            value={<span className="mono">{run.termination_reason}</span>}
          />
          <Fact
            label="Authoritative readback"
            value={
              proof.workspace_readback.run_recorded &&
              proof.workspace_readback.pool_recorded &&
              proof.workspace_readback.same_workspace
                ? "run + pool present in the same workspace"
                : "not verified"
            }
          />
        </div>
      </div>
      <div className="panel-head">
        <h3>Exact tool sequence</h3>
        <span className="spacer" />
        <span className="tiny faint">read from the stored run record</span>
      </div>
      <div className="panel-pad">
        <TracePills names={run.tool_calls} />
      </div>
      <div className="panel-head">
        <h3>Request, execution, authoritative return</h3>
      </div>
      <HopChain state="done" />
    </section>
  );
}

function InvocationPanel({
  config,
  result,
  busy,
  onRun,
  again = false,
}: {
  config: DemoConfig | null;
  result: LiveAgentResult | null;
  busy: boolean;
  onRun: () => void;
  again?: boolean;
}) {
  const available = Boolean(config?.live_agent_available);
  const state = busy ? "flight" : result?.ok ? "done" : result ? "failed" : "idle";
  return (
    <div className="live-panel">
      <div className="live-head">
        <IconCloud />
        <h3 style={{ fontSize: 14.5, fontWeight: 600 }}>
          {again ? "Run the deployed coordinator again" : "Invoke the deployed coordinator"}
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
              Starts one bounded coordinator run on Amazon Bedrock AgentCore in{" "}
              <strong>{config?.region}</strong>, against this session’s own DynamoDB workspace.
            </p>
            <p className="tiny muted">
              The server owns the instruction, creates a one-use runtime session, and
              re-reads the database after AWS answers. The cap is{" "}
              {config?.max_live_per_session} live runs per visitor; only one may write a
              workspace at a time.
            </p>
            <div className="btn-row" style={{ marginTop: 4 }}>
              <button className="btn btn-primary btn-lg" onClick={onRun} disabled={busy}>
                {busy ? <span className="spinner" /> : <IconCloud />}
                {busy ? "Coordinator running on AWS" : again ? "Run again" : "Run on AgentCore"}
              </button>
              {busy ? (
                <span className="tiny muted">
                  One real request is in flight; no intermediate stage is being inferred.
                </span>
              ) : null}
            </div>
          </>
        ) : (
          <p className="small muted prose">
            This build has no AgentCore runtime configured, so no live button is offered.
            Local coordination uses the same bounded loop and typed tools with an offline
            planner in the model’s place.
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
  proof,
  standalone,
}: {
  config: DemoConfig | null;
  health: Health | null;
  result: LiveAgentResult | null;
  busy: boolean;
  onRun: () => void;
  runs: RunSummary[];
  proof: PoolExecutionProof | null;
  /** Rendered as its own destination in Showcase mode rather than inside a pool's
   *  record, where the record already supplies the context and the title. */
  standalone?: boolean;
}) {
  const available = Boolean(config?.live_agent_available);
  const tools = health?.agent_tools ?? [];
  const chosen = proof?.run.tool_calls ?? (result?.ok ? result.run.tool_calls.map((t) => t.name) : []);

  return (
    <div className="stack">
      <header className="stack-sm">
        {standalone ? (
          <h1 className="title" style={{ maxWidth: "22ch" }}>
            One Product action runs the deployed coordinator
          </h1>
        ) : (
          <h2 className="title" style={{ maxWidth: "24ch" }}>
            How Pool coordinated this
          </h2>
        )}
        {/* Deliberately a claim about the mechanism, not about the pool on screen.
            Discovery goes to AWS when the deployment has a runtime. A local fallback is
            used only after the server explicitly proves that no remote execution can
            still mutate this workspace; an ambiguous outcome stays visible as one.
            Which one answered is a fact per run, and every run below carries it. */}
        <p className="lede">
          {available
            ? `Finding an opportunity on this site invokes Pool's coordinator where it is
               deployed — on Amazon Bedrock AgentCore, against this session's own data, so
               the pool it forms is formed there. The rest of the lifecycle runs the same
               Strands loop on this server with a deterministic planner in the model's
               place, so the lifecycle is free to rehearse and repeatable. Every run below records which
               of the two answered.`
            : `Pool's coordinator runs on this server for every action you take — the real
               Strands event loop, the real tools, the real domain arithmetic, driven by a
               deterministic planner rather than a model so local rehearsal is free and
               repeatable. The same coordinator is also deployed on AWS.`}
        </p>
      </header>

      {proof ? <StoredExecutionProof proof={proof} /> : null}

      {proof ? (
        <details className="panel">
          <summary className="panel-head" style={{ cursor: "pointer" }}>
            <strong>Run again</strong>
            <span className="spacer" />
            <span className="tiny faint">secondary live invocation · spends model tokens</span>
          </summary>
          <InvocationPanel
            config={config}
            result={result}
            busy={busy}
            onRun={onRun}
            again
          />
        </details>
      ) : (
        <InvocationPanel config={config} result={result} busy={busy} onRun={onRun} />
      )}

      {result?.ok ? (
        <section className="panel reveal">
          <div className="panel-head">
            <h3>Latest live invocation response</h3>
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
          <div className="panel-head">
            <h3>What the database held afterwards</h3>
            <span className="spacer" />
            <span className="tiny faint">read back by the server, not reported by the agent</span>
          </div>
          <div className="panel-pad stack-sm">
            <div className="facts">
              <Fact
                label="Its run record, in your session's data"
                value={result.observed.run_recorded ? "present" : "not found"}
              />
              <Fact label="Pools in your session" value={result.observed.pools} />
              <Fact
                label="Pools linked to this exact run"
                value={result.observed.created_pool_ids.length > 0
                  ? result.observed.created_pool_ids.join(", ")
                  : "none"}
              />
              <Fact
                label="Run → pool link"
                value={result.observed.run_pool_links_verified ? "verified" : "not verified"}
              />
              <Fact label="People it is waiting on" value={result.observed.pending_decisions} />
            </div>
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
            the world through these typed functions and nothing else. Each one is labelled
            by what it actually writes, and a test calls every tool marked{" "}
            <em>reads only</em> against a snapshot of the whole workspace to prove the
            label — because a door described as harmless is worth exactly what the check
            behind it is worth. The ones that commit are idempotent by an explicit key,
            because agent systems retry and a repeated{" "}
            <span className="mono">create_candidate_pool</span> must not produce two pools.
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
              calls, {health.bounds.max_duplicate_tool_calls} identical calls before the next
              one is refused, and a {health.bounds.workflow_timeout_seconds}s wall clock
              checked before every model and tool call. That cooperative bound stops the
              loop between steps; it cannot interrupt a call already in progress. The
              layers that own the process provide the outer deadlines — the runtime
              invocation at 60s and Lambda at 90s. A run that hits a bound ends loudly as
              a recorded fault, never a silent truncation that looks like an answer.
            </p>
          ) : null}
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          {/* Every run this session has had, wherever it executed. A run on AWS writes
              its record to the same workspace as one that ran here, so this list is the
              audit trail rather than a local subset of it — `model_provider` on each row
              says which. */}
          <h3>Every run in this session</h3>
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
            ["Lambda Function URL", "24 allowlisted paths of 40; everything else 404s"],
            ["DynamoDB", "single table, on-demand; each visitor isolated by partition, 24 h TTL"],
            ["Bedrock AgentCore Runtime", "hosts the coordinator; AWS_IAM inbound auth, one runtime ARN; read/write on that one table, no delete"],
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
