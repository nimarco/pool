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

export function Block({
  title,
  aside,
  children,
}: {
  title: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="block">
      <div className="row-between" style={{ marginBottom: 12 }}>
        <h3 className="section-title">{title}</h3>
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

export function TracePills({ names }: { names: string[] }) {
  if (names.length === 0) return null;
  return (
    <div className="trace-inline">
      {names.map((name, i) => (
        <span key={`${name}-${i}`} className="trace-pill">
          {name}
        </span>
      ))}
    </div>
  );
}
