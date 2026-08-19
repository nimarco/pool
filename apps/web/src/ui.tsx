/* Shared primitives.
 *
 * Two rules govern everything in this file:
 *   - Nothing here computes a displayed value. Every figure originates on the server;
 *     these components select, label and set it (AGENTS.md §5). `money()` and `pct()`
 *     format integers the server sent — they do not derive.
 *   - Nothing identifying is renderable. The payloads carry display names and no
 *     address, phone, email or payment reference, so there is nothing to leak.
 *
 * The actor grammar is the one invention worth explaining. Every action Pool takes is
 * attributable to exactly one of three parties, and the whole technical argument of the
 * project is *which* one:
 *
 *   agent   — the Strands loop chose to do this
 *   engine  — deterministic code computed this and it could not have been otherwise
 *   human   — a person was asked, and answered
 *
 * Making that a shape and a colour, repeated everywhere, is cheaper for a reader than
 * any amount of prose about AI/deterministic boundaries.
 */

import React from "react";

/* ------------------------------------------------------------------- actors */

export type Actor = "agent" | "engine" | "human";

const ACTOR_COPY: Record<Actor, string> = {
  agent: "Agent decided",
  engine: "Computed",
  human: "Person asked",
};

/** Diamond, square, circle — distinguishable without colour, which matters both for
 *  colour-blind readers and for a video that gets re-encoded. */
export function ActorGlyph({ actor }: { actor: Actor }) {
  return (
    <svg className="actor-glyph" viewBox="0 0 10 10" aria-hidden="true" fill="currentColor">
      {actor === "agent" ? <path d="M5 0 10 5 5 10 0 5Z" /> : null}
      {actor === "engine" ? <rect x="0.6" y="0.6" width="8.8" height="8.8" rx="1.2" /> : null}
      {actor === "human" ? <circle cx="5" cy="5" r="4.6" /> : null}
    </svg>
  );
}

export function ActorTag({ actor, label }: { actor: Actor; label?: string }) {
  return (
    <span className={`actor actor-${actor}`}>
      <ActorGlyph actor={actor} />
      {label ?? ACTOR_COPY[actor]}
    </span>
  );
}

/** The legend. Shown once per surface that uses the grammar, never twice. */
export function ActorKey() {
  return (
    <div className="actor-key">
      <span className="actor actor-agent">
        <ActorGlyph actor="agent" />
        The agent chose to do this
      </span>
      <span className="actor actor-engine">
        <ActorGlyph actor="engine" />
        Deterministic code computed it
      </span>
      <span className="actor actor-human">
        <ActorGlyph actor="human" />A person was asked
      </span>
    </div>
  );
}

/* -------------------------------------------------------------------- icons */

/** One stroke weight, one grid, no emoji anywhere in the product. */
function Icon({ children, size = 16 }: { children: React.ReactNode; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={{ flex: "none" }}
    >
      {children}
    </svg>
  );
}

export const IconCheck = ({ size }: { size?: number }) => (
  <Icon size={size}>
    <path d="M3 8.5 6.2 12 13 4.5" />
  </Icon>
);
export const IconCross = ({ size }: { size?: number }) => (
  <Icon size={size}>
    <path d="M4 4l8 8M12 4l-8 8" />
  </Icon>
);
export const IconDot = ({ size }: { size?: number }) => (
  <Icon size={size}>
    <circle cx="8" cy="8" r="3.2" />
  </Icon>
);
export const IconArrowLeft = ({ size }: { size?: number }) => (
  <Icon size={size}>
    <path d="M12 8H4M7.5 4 4 8l3.5 4" />
  </Icon>
);
export const IconArrowRight = ({ size }: { size?: number }) => (
  <Icon size={size}>
    <path d="M4 8h8M8.5 4 12 8l-3.5 4" />
  </Icon>
);
export const IconPlay = ({ size }: { size?: number }) => (
  <Icon size={size}>
    <path d="M5 3.4 12.4 8 5 12.6Z" />
  </Icon>
);
export const IconReplay = ({ size }: { size?: number }) => (
  <Icon size={size}>
    <path d="M13 8a5 5 0 1 1-1.6-3.7" />
    <path d="M13 2.2V5h-2.8" />
  </Icon>
);
export const IconCloud = ({ size }: { size?: number }) => (
  <Icon size={size}>
    <path d="M4.6 12.5a2.9 2.9 0 0 1-.3-5.8 3.9 3.9 0 0 1 7.5-.9 2.85 2.85 0 0 1 .3 5.6l-.4.1z" />
  </Icon>
);

/* ------------------------------------------------------------------- pieces */

export function Chip({
  tone = "neutral",
  children,
}: {
  tone?: "ok" | "warn" | "info" | "stop" | "live" | "neutral";
  children: React.ReactNode;
}) {
  const cls =
    tone === "neutral" ? "chip" : `chip chip-${tone === "stop" ? "stop" : tone}`;
  return <span className={cls}>{children}</span>;
}

/* ------------------------------------------------------------------ elapsed */

/** A real clock, started when the caller says the request went out.
 *
 *  This is the one piece of progress information a browser genuinely has during a
 *  remote invocation, so it is the one piece shown. Lives here rather than in the
 *  technical view because the Product's wait needs it too, and two copies of a timer
 *  would be two chances to disagree about what "elapsed" means. */
export function Elapsed({ running }: { running: boolean }) {
  const [ms, setMs] = React.useState(0);
  const start = React.useRef(0);

  React.useEffect(() => {
    if (!running) return undefined;
    start.current = performance.now();
    setMs(0);
    const id = window.setInterval(() => setMs(performance.now() - start.current), 100);
    return () => window.clearInterval(id);
  }, [running]);

  if (!running) return null;
  return <span className="elapsed">{(ms / 1000).toFixed(1)}s elapsed</span>;
}

/** A truthful wait state for one bounded coordinator invocation.
 *
 * The honesty rule shapes everything here. A browser making one HTTPS request can
 * observe exactly two things: that it sent, and when it got an answer. So the three
 * rows below are not a progress bar with three steps — they are *one observed fact*,
 * *one unobservable interval named for what it contains*, and *one thing that has not
 * happened yet*. Only the first is ever marked complete before a response arrives, and
 * the caption says so on screen rather than in a comment nobody reads.
 *
 * The deployment's own architecture (eight hops, IAM posture, bounds) is real evidence
 * and it lives on the technical view. Putting it on a member's home screen would make
 * the consumer product into an operations console for the fifteen seconds that matter
 * most (AGENTS.md §1 "build it like a real product"), so what appears here is the
 * shortest true description of where the request went. */
export function CoordinatorWait({
  live,
  region,
  objective,
}: {
  live: boolean;
  region?: string | null;
  /** What this run was asked about, when the caller knows it *before* the run starts.
   *
   *  Permitted here precisely because it is not a claim about progress: the objective is
   *  derived from the member's own stored declarations before anything is invoked, so
   *  naming it is describing the request rather than narrating work nobody can see. */
  objective?: string;
}) {
  return (
    <div className="wait" role="status" aria-live="polite">
      <div className="wait-head">
        <IconCloud />
        <strong>
          Pool&apos;s coordinator is running
          {live ? " on Amazon Bedrock AgentCore" : " in this workspace"}
        </strong>
        <span className="spacer" />
        <Elapsed running />
      </div>
      <p className="wait-lede">
        {objective ? `${objective} ` : ""}
        {live
          ? `One bounded run${region ? `, in ${region},` : ""} against this session’s own DynamoDB workspace.`
          : "One bounded run is reading the Community’s standing needs."}
      </p>
      <div className="wait-steps">
        <span className="wait-step done">
          <IconCheck size={14} />
          Request sent from your browser
        </span>
        <span className="wait-step pending">
          <span className="spinner" />
          {live
            ? "AgentCore → Strands → Pool’s typed tools → DynamoDB"
            : "Strands loop → Pool’s typed tools → the store"}
        </span>
        <span className="wait-step">
          <IconDot size={14} />
          An answer, and whatever it wrote
        </span>
      </div>
      <p className="wait-note">
        Only the first line is something this page watched happen. Nothing in between is
        animated as if it were.
      </p>
    </div>
  );
}

export function Figure({
  label,
  value,
  sub,
  accent,
  small,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: boolean;
  small?: boolean;
}) {
  return (
    <div>
      <div className="figure-label">{label}</div>
      <div
        className={`figure-value${small ? " sm" : ""}${accent ? " figure-accent" : ""}`}
      >
        {value}
      </div>
      {sub ? <div className="figure-sub">{sub}</div> : null}
    </div>
  );
}

export function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="fact-label">{label}</div>
      <div className="fact-value">{value}</div>
    </div>
  );
}

export function Meter({ value, max }: { value: number; max: number }) {
  const filled = max > 0 ? Math.min(1, value / max) : 0;
  return (
    <div className="meter" role="img" aria-label={`${value} of ${max} units`}>
      <div
        className={`meter-fill${filled < 1 ? " short" : ""}`}
        style={{ transform: `scaleX(${filled})` }}
      />
    </div>
  );
}

export function Empty({ children, center }: { children: React.ReactNode; center?: boolean }) {
  return <p className={`empty${center ? " empty-center" : ""}`}>{children}</p>;
}

/** A titled block. `level` keeps the document outline honest where the block is nested
 *  inside another section rather than sitting directly under the page title. */
export function Block({
  title,
  aside,
  level = 2,
  children,
}: {
  title: string;
  aside?: React.ReactNode;
  level?: 2 | 3 | 4;
  children: React.ReactNode;
}) {
  const Heading = `h${level}` as "h2" | "h3" | "h4";
  return (
    <section className="block">
      <div className="row-between" style={{ marginBottom: 12 }}>
        <Heading className="section-title">{title}</Heading>
        {aside}
      </div>
      {children}
    </section>
  );
}

export function LedgerLine({
  label,
  value,
  kind,
}: {
  label: string;
  value: string;
  kind?: "total" | "gain" | "baseline";
}) {
  return (
    <div className={`ledger-line${kind ? ` ${kind}` : ""}`}>
      <span className="label">{label}</span>
      <span className="value">{value}</span>
    </div>
  );
}

/** The agent's tool sequence, exactly as recorded. */
export function Trace({
  calls,
}: {
  calls: { name: string; ok: boolean; summary?: string }[];
}) {
  if (calls.length === 0) {
    return <Empty>No tools were called on this run.</Empty>;
  }
  return (
    <div className="trace">
      {calls.map((call, i) => (
        <div key={`${call.name}-${i}`} className={`trace-step${call.ok ? "" : " refused"}`}>
          <span className="trace-idx">{String(i + 1).padStart(2, "0")}</span>
          <span className="trace-name">{call.name}</span>
          {/* The tool's own returned payload, truncated by the server. Left raw
              because a paraphrase of a tool result is exactly the thing this
              architecture exists to avoid — and raw output is better evidence. */}
          <span className="trace-summary" title={call.summary}>
            {call.ok ? call.summary : `refused — ${call.summary}`}
          </span>
        </div>
      ))}
    </div>
  );
}

export function TracePills({ names, ordered }: { names: string[]; ordered?: boolean }) {
  if (names.length === 0) return null;
  return (
    <div className={`trace-inline${ordered ? " ordered" : ""}`}>
      {names.map((name, i) => (
        <span key={`${name}-${i}`} className="trace-pill">
          {name}
        </span>
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------- provenance */

/** The same-run relationship, rendered once and used everywhere it is claimed.
 *
 *  Every string here is a server value passed straight through; the component adds no
 *  fact and hides none. What it adds is alignment: the run id and the pool's
 *  `created_by_run` are set on consecutive rows in the same column, so two identifiers
 *  being equal is something a judge can *see* at recording scale rather than something
 *  they have to read a caption to learn. The verdict below it is the server's
 *  authoritative readback of the same workspace the browser is reading. */
export function ProofIdentity({
  runId,
  poolId,
  createdByRun,
  sameWorkspace,
}: {
  runId: string;
  poolId: string;
  createdByRun: string;
  sameWorkspace: boolean;
}) {
  const matches = createdByRun === runId;
  return (
    <div className="provenance">
      <div className="prov-row linked">
        <span className="prov-label">Run id</span>
        <span className="prov-value token">{runId}</span>
      </div>
      <div className="prov-row linked">
        <span className="prov-label">Pool created_by_run</span>
        <span className="prov-value token">
          {createdByRun}
          <Chip tone={matches ? "ok" : "stop"}>
            {matches ? "matches run id" : "mismatch"}
          </Chip>
        </span>
      </div>
      <div className="prov-row">
        <span className="prov-label">Resulting pool id</span>
        <span className="prov-value token">{poolId}</span>
      </div>
      <p className="prov-verdict">
        <span className={sameWorkspace ? "ok" : "bad"}>
          {sameWorkspace ? <IconCheck size={15} /> : <IconCross size={15} />}
        </span>
        <span>
          <strong>Authoritative same-workspace readback</strong> ·{" "}
          {sameWorkspace ? "verified · run + pool present" : "not verified"}
        </span>
      </p>
    </div>
  );
}

/** The request's path through the deployment, set as evidence rather than as a note. */
export function ExecutionPath({ live }: { live: boolean }) {
  return (
    <span className="path">
      {live
        ? "browser → Lambda → AgentCore → Bedrock / Strands → typed tools → DynamoDB → browser"
        : "browser → server → Strands planner → typed tools → database → browser"}
    </span>
  );
}
