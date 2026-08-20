/* One pool, as a persistent product record.
 *
 * Two halves, and the order between them is the whole design. First the five questions a
 * member actually has — what do I get, what do I pay, where and when do I collect it,
 * what happens next, does Pool need anything from me. Then the record: who is in it, what
 * it costs line by line, the host and every deterministic check, collection, and the
 * technical proof. All of it shut.
 *
 * It used to be a five-tab strip whose first tab put `Units 24 / 16`, `0 units
 * authorized` and `View all 11 deterministic checks` in front of a member who wanted to
 * know what they were paying — while Home, one click earlier, had already said "Your 2
 * bags · about $17.53 instead of $22.98 buying alone". The record was less use to its own
 * reader than the summary that linked to it. Nothing was removed: a deep link still opens
 * exactly one section, which is how "see it run on AWS" lands on the evidence.
 *
 * Everything numeric is read from the pool payload. `buyer_count` and `member_count` are
 * both server-computed and both shown, because after a declined card they differ and
 * that difference is a fact about the pool rather than a rounding error.
 */

import React, { useEffect, useState } from "react";
import {
  ActivityEvent,
  Checklist,
  Credential,
  DemoConfig,
  Health,
  LiveAgentResult,
  PoolView,
  RunSummary,
  ScenarioResult,
  api,
  money,
  shortTime,
  statusCopy,
} from "../api";
import {
  ActorGlyph,
  ActorTag,
  Block,
  Chip,
  Empty,
  ExecutionPath,
  Figure,
  IconArrowLeft,
  IconCheck,
  IconCross,
  IconDot,
  LedgerLine,
  CaseFit,
  Meter,
  ProofIdentity,
  TracePills,
} from "../ui";
import { groupSavingsCaption } from "../labels";
import { Feed } from "./community";
import { AgentExecution } from "./live";
import { RunView } from "./run";

type Tab = "overview" | "people" | "economics" | "fulfilment" | "activity";


export function PoolRecord({
  pool,
  runs,
  activity,
  identity,
  mine,
  entry,
  scenario,
  scenarioMs,
  running,
  health,
  demoConfig,
  live,
  liveBusy,
  onBack,
  onRefresh,
  onRunLive,
  onRunScenario,
}: {
  pool: PoolView;
  runs: RunSummary[];
  activity: ActivityEvent[];
  identity: { id: string; display_name: string };
  /** Whether this order is this member's, as the server answered it. Null when nothing
   *  has answered yet — a state where saying nothing is correct and guessing is not. */
  mine: boolean | null;
  /** Where to land. Lets "see it run on AWS" open the evidence directly instead of the
   *  record's front page. */
  entry?: { tab?: string; deep?: string };
  scenario: ScenarioResult | null;
  scenarioMs: number | null;
  running: boolean;
  health: Health | null;
  demoConfig: DemoConfig | null;
  live: LiveAgentResult | null;
  liveBusy: boolean;
  onBack: () => void;
  onRefresh: () => void;
  onRunLive: () => void;
  /** Only the showcase and the demo controls may start the scripted lifecycle: it
   *  replays a different world, and offering it from an ordinary pool record invited a
   *  member to "start the community over" from inside their own order. */
  onRunScenario?: () => void;
}) {
  const s = statusCopy(pool.status);
  const declined = pool.member_count - pool.buyer_count;
  /** Which record section a deep link asked for. Opens that disclosure; everything else
   *  stays shut, which is the whole point of the region. */
  const opened = (entry?.tab as Tab) ?? null;
  const myUnits = mine
    ? ((pool.members ?? []).find((m) => m.household_id === identity.id)?.units ?? 0)
    : 0;

  return (
    <div className="stack">
      <header className="stack-sm">
        <div>
          <button className="btn btn-sm btn-ghost" onClick={onBack}>
            <IconArrowLeft />
            Back
          </button>
        </div>
        <div className="row-between">
          <div>
            <h1 className="title">{pool.product_name}</h1>
            {/* Supplier only. The pickup point and the window used to be repeated here
                and again under "Where you collect it" two inches below — the same fact,
                twice, in one frame. */}
            <p className="small muted" style={{ marginTop: 6 }}>
              {pool.brand ? `${pool.brand} · ` : ""}
              {pool.supplier}
            </p>
          </div>
          <div className="stack-xs" style={{ alignItems: "flex-end" }}>
            <Chip tone={s.tone}>{s.label}</Chip>
            {/* Whose order this is, said on the record itself. Home was already careful
                about it and this page was not, so one click undid the care: `Buyers 6 —
                everyone still in` reads as a roster somebody is on. The answer is the
                server's (`services/relevance.py`), never inferred from the member list. */}
            {mine === null ? null : (
              <span className={mine ? "scope-mine" : "scope-theirs"}>
                {mine ? "You are in this order" : "You are not in this order"}
              </span>
            )}
          </div>
        </div>
      </header>

      {pool.failure_reason ? (
        <div className="banner banner-warn">
          <span>{pool.failure_reason}</span>
        </div>
      ) : null}

      <YourOrder pool={pool} mine={mine} myUnits={myUnits} />

      {/* The record. Five questions get answered above; everything else is here, shut,
          because a member asking "what am I paying" should not have to walk past eleven
          deterministic checks to find out. A judge arriving on a deep link gets the one
          section they asked for already open, and can open the rest without navigating.
          This replaced a five-tab strip in which the consumer's first screen carried
          `View all 11 deterministic checks`. */}
      <section className="stack-sm record">
        <h2 className="section-title">Everything recorded about this order</h2>
        <RecordSection
          id="people"
          title="Who is in it"
          hint={`${pool.buyer_count} ${pool.buyer_count === 1 ? "buyer" : "buyers"}${declined > 0 ? ` · ${declined} declined and kept on the record` : ""}`}
          open={opened === "people"}
        >
          <PeopleTab pool={pool} identity={identity} onRefresh={onRefresh} />
        </RecordSection>
        <RecordSection
          id="economics"
          title="What it costs, line by line"
          hint="merchandise, host pay, card processing and Pool's fee"
          open={opened === "economics"}
        >
          <EconomicsTab pool={pool} myUnits={myUnits} />
        </RecordSection>
        <RecordSection
          id="overview"
          title="The host, the pickup point, and every check Pool ran"
          hint={
            pool.viability
              ? `${pool.viability.checks.length} deterministic checks · ${pool.viability.viable ? "all passing" : `${pool.viability.failed.length} blocking`}`
              : "host selection and collection"
          }
          open={opened === "overview"}
        >
          <OverviewTab pool={pool} />
        </RecordSection>
        <RecordSection
          id="fulfilment"
          title="Collection"
          hint="one-time credentials, and the handoff checklist"
          open={opened === "fulfilment"}
        >
          <FulfilmentTab pool={pool} identity={identity} onRefresh={onRefresh} />
        </RecordSection>
        <RecordSection
          id="activity"
          title="Activity and technical proof"
          hint="the run that formed it, its tool sequence, and the AgentCore identifiers"
          open={opened === "activity"}
        >
          <ActivityTab
            pool={pool}
            entryDeep={entry?.deep}
            runs={runs}
            activity={activity}
            scenario={scenario}
            scenarioMs={scenarioMs}
            running={running}
            health={health}
            demoConfig={demoConfig}
            live={live}
            liveBusy={liveBusy}
            onRunLive={onRunLive}
            onRunScenario={onRunScenario}
          />
        </RecordSection>
      </section>
    </div>
  );
}

/* --------------------------------------------------------------- your order */

/** What happens next, in the member's terms, keyed off the deterministic status.
 *
 *  One sentence per lifecycle state, and each one says who is holding it — because
 *  "finding a host" is Pool working and "needs your approval" is the member holding it,
 *  and a member cannot act on the difference unless the screen states it. */
function nextStep(pool: PoolView): { next: string; needsYou: string } {
  const host = pool.host?.display_name;
  switch (pool.status) {
    case "forming":
      return {
        next: "Pool is still gathering compatible demand near you. Nothing is committed.",
        needsYou: "Nothing yet — Pool will ask if this becomes worth doing.",
      };
    case "host_recruiting":
    case "host_selected":
      return {
        next: "Pool ranked the people willing to carry it and offered the job to the best fit. A host has to accept before the price is exact.",
        needsYou: "Nothing right now. The amount above can still move, so Pool has not asked you to commit.",
      };
    case "final_offer":
    case "funding":
    case "recovering":
      return {
        next: `${host ? `${host} accepted the job, so ` : ""}the exact amount is settled and Pool needs your approval before anything is charged.`,
        needsYou: "Yes — approve the exact amount. Pool asks because you chose “ask me first”.",
      };
    case "locked":
    case "purchase_ready":
      return {
        next: "Every check passed and your card is authorized for the exact amount. Pool is placing one bulk order.",
        needsYou: "Nothing — Pool has what it needs.",
      };
    case "purchased":
      return {
        next: `The order is placed. ${host ? `${host} collects it` : "Your host collects it"} and opens the pickup window.`,
        needsYou: "Nothing yet — you will get a one-time code when collection opens.",
      };
    case "distributing":
      return {
        next: "Collection is open. Show your one-time code at the pickup point.",
        needsYou: "Yes — collect your order inside the window.",
      };
    case "completed":
      return {
        next: "Collected and reconciled. Nothing is outstanding.",
        needsYou: "Nothing. This one is done.",
      };
    default:
      return {
        next: "This order is not moving forward.",
        needsYou: "Nothing — your declaration stays standing and Pool keeps watching.",
      };
  }
}

/** The five questions a member actually has, answered before anything else.
 *
 *  What am I getting · what am I paying · where and when do I collect · what happens
 *  next · does Pool need anything from me. Home already answered them in this voice
 *  ("Your 2 bags · about $17.53 instead of $22.98 buying alone") and the record it
 *  linked to opened on `Units 24 / 16`, `0 units authorized` and an em dash where the
 *  price belongs. The pool-level arithmetic is still here — it moved one line down,
 *  underneath the answer it supports. */
function YourOrder({
  pool,
  mine,
  myUnits,
}: {
  pool: PoolView;
  mine: boolean | null;
  myUnits: number;
}) {
  const me = mine
    ? (pool.members ?? []).find((m) => m.units === myUnits && m.state !== "withdrawn")
    : undefined;
  const cost = me?.final_cost_display || me?.estimated_cost_display || "";
  const provisional = Boolean(cost) && !me?.final_cost_display;
  const alone = me?.baseline_display || "";
  const step = nextStep(pool);
  const startsAt = pool.timing?.distribution_starts_at ?? "";
  const unit = myUnits === 1 ? pool.unit : `${pool.unit}s`;

  return (
    <section className="panel your-order">
      <div className="panel-pad stack-sm">
        <div className="your-grid">
          <div>
            <span className="figure-label">
              {mine === false ? "The order" : "What you get"}
            </span>
            <p className="your-value">
              {mine === false
                ? `${pool.provisional_units} ${pool.unit}s`
                : `${myUnits} ${unit}`}
            </p>
            {mine === false ? (
              <p className="tiny faint">
                Your own units are still standing — this one filled without them.
              </p>
            ) : null}
          </div>
          <div>
            <span className="figure-label">
              {provisional ? "What you pay, about" : "What you pay"}
            </span>
            <p className="your-value">{cost || "not settled yet"}</p>
            {alone && cost ? (
              <p className="tiny faint">
                instead of {alone} buying alone
                {me?.savings_pct ? ` · ${me.savings_pct} less` : ""}
              </p>
            ) : (
              <p className="tiny faint">{groupSavingsCaption(pool)}</p>
            )}
          </div>
          <div>
            <span className="figure-label">Where you collect it</span>
            <p className="your-value your-value-sm">{pool.pickup_site}</p>
            <p className="tiny faint">
              {startsAt ? shortTime(startsAt) : "window opens once the order is placed"}
            </p>
          </div>
        </div>

        <div className="your-next">
          <p className="small">
            <strong>What happens next.</strong> {step.next}
          </p>
          <p className="small muted">
            <strong>Does Pool need anything from you?</strong> {step.needsYou}
          </p>
        </div>

        {/* The pool-level arithmetic, kept and demoted. It is the reason the price above
            exists, so it sits under it rather than over it. */}
        <div className="your-group">
          <Meter value={pool.provisional_units} max={pool.threshold_units} />
          <p className="tiny faint">
            {pool.provisional_units} {pool.unit}s together with {pool.buyer_count}{" "}
            {pool.buyer_count === 1 ? "buyer" : "buyers"} — the supplier will not sell
            fewer than {pool.threshold_units}.
            {pool.funded_units > 0
              ? ` ${pool.funded_units} authorized so far.`
              : " Nothing is authorized yet."}
          </p>
        </div>
      </div>
    </section>
  );
}

/** One shut section of the record. `<details>` rather than a tab, so a deep link can
 *  open exactly one and a keyboard reaches all five without arrow-key convention. */
function RecordSection({
  id,
  title,
  hint,
  open,
  children,
}: {
  id: string;
  title: string;
  hint: string;
  open: boolean;
  children: React.ReactNode;
}) {
  return (
    <details className="record-section" id={`record-${id}`} open={open}>
      <summary>
        <span className="record-title">{title}</span>
        <span className="record-hint">{hint}</span>
      </summary>
      <div className="record-body stack">{children}</div>
    </details>
  );
}

/* ------------------------------------------------------------------ overview */

function OverviewTab({ pool }: { pool: PoolView }) {
  return (
    <div className="stack">
      <section className="grid grid-2">
        <div className="panel panel-pad">
          <h2 className="section-title" style={{ marginBottom: 12 }}>
            Who is carrying it
          </h2>
          {pool.host ? (
            <>
              <div className="display" style={{ fontSize: 26 }}>
                {pool.host.display_name}
              </div>
              <p className="small muted" style={{ marginTop: 6 }}>
                {pool.host.handled_orders} orders · {pool.host.supplier_distance_km} km round
                trip · earns <strong>{pool.host.reward_display}</strong>
              </p>
              <p className="tiny faint" style={{ marginTop: 6 }}>
                Included in buyer economics and recorded on the simulated transaction; no
                real payout rail exists.
              </p>
            </>
          ) : (
            <p className="small muted">
              Still recruiting. Candidates are ranked on capacity, vehicle, distance and
              the minimum pay each of them will accept — offering does not claim the job.
            </p>
          )}
        </div>
        <div className="panel panel-pad">
          <h2 className="section-title" style={{ marginBottom: 12 }}>
            Where it is collected
          </h2>
          <div className="display" style={{ fontSize: 26 }}>
            {pool.pickup_site}
          </div>
          <p className="small muted" style={{ marginTop: 6 }}>
            {pool.pickup_is_public ? "A public spot on campus" : "Not a public site"}
            {pool.pickup_permission ? ` · permission: ${pool.pickup_permission}` : ""} ·
            selected for the members who joined.
          </p>
        </div>
      </section>

      {pool.viability ? (
        <section className="panel">
          <div className="panel-head">
            <h2>Can this go ahead?</h2>
            <Chip tone={pool.viability.viable ? "ok" : "warn"}>
              {pool.viability.viable
                ? "every check passes"
                : `${pool.viability.failed.length} blocking`}
            </Chip>
            <span className="spacer" />
            <ActorTag actor="engine" label="Checked, not judged" />
          </div>
          <div className="panel-pad">
            <p className="small muted" style={{ marginBottom: 14 }}>
              Buyers, supplier, host and Pool must all pass. Every check runs, so a refusal
              returns the complete blocking list.
            </p>
            <details className="inset">
              <summary className="small">
                <strong>View all {pool.viability.checks.length} deterministic checks</strong>
              </summary>
              <div className="rows" style={{ marginTop: 10, borderTop: "1px solid var(--rule)" }}>
                {pool.viability.checks.map((c) => (
                  <div key={c.name} className="row" style={{ paddingInline: 0, gap: 11 }}>
                    <span
                      style={{
                        color: c.passed ? "var(--ink)" : "var(--stop)",
                        display: "flex",
                        marginTop: 2,
                      }}
                    >
                      {c.passed ? <IconCheck size={15} /> : <IconCross size={15} />}
                    </span>
                    <div className="row-body">
                      <span className="small" style={{ fontWeight: 600 }}>
                        {c.name.replace(/_/g, " ")}
                      </span>
                      <span className="small muted"> — {c.detail}</span>
                    </div>
                  </div>
                ))}
              </div>
            </details>
          </div>
        </section>
      ) : null}

      {pool.announcements && pool.announcements.length > 0 ? (
        <Block title="What members were told">
          <div className="rows" style={{ borderTop: "1px solid var(--rule)" }}>
            {pool.announcements.map((a) => (
              <div key={a.id} className="row" style={{ paddingInline: 0 }}>
                <div className="row-body">
                  <div className="small">{a.body}</div>
                  <div className="tiny faint">{a.author}</div>
                </div>
              </div>
            ))}
          </div>
        </Block>
      ) : null}
    </div>
  );
}

/* -------------------------------------------------------------------- people */

function PeopleTab({
  pool,
  identity,
  onRefresh,
}: {
  pool: PoolView;
  identity: { id: string; display_name: string };
  onRefresh: () => void;
}) {
  const declined = pool.member_count - pool.buyer_count;
  const [outcome, setOutcome] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const me = (pool.members ?? []).find((m) => m.household_id === identity.id);
  const alreadyCandidate = (pool.host_candidates ?? []).some(
    (c) => c.household_id === identity.id,
  );
  const recruiting = pool.status === "host_recruiting" || pool.status === "forming";
  const locked = !["forming", "host_recruiting", "host_selected", "final_offer", "funding", "recovering"].includes(
    pool.status,
  );

  const act = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(true);
    setOutcome(null);
    try {
      await fn();
      setOutcome({ ok: true, text: label });
      onRefresh();
    } catch (err) {
      setOutcome({ ok: false, text: err instanceof Error ? err.message : String(err) });
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="stack">
      <section className="panel">
        <div className="panel-head">
          <h2>Buyers</h2>
          <span className="spacer" />
          <span className="tiny faint">
            display names only · no contact, address or payment data
          </span>
        </div>
        {declined > 0 ? (
          <div className="panel-pad" style={{ paddingBottom: 0 }}>
            <p className="small muted">
              <strong>{pool.buyer_count} buying · {pool.member_count} memberships · {declined}{" "}
              declined.</strong>{" "}
              The failed membership remains in the audit record.
            </p>
          </div>
        ) : null}
        <div className="rows">
          {(pool.members ?? []).map((m) => (
            <div key={m.household_id} className="row">
              <div className="row-body">
                <div className="row-title">
                  {m.display_name}
                  {m.is_host ? <Chip tone="info">carrying it</Chip> : null}
                  {m.path === "smart_join" ? (
                    <Chip tone="ok">Pool decided for them</Chip>
                  ) : null}
                  {m.path === "human_approved" ? <Chip tone="warn">they were asked</Chip> : null}
                  {m.state === "authorization_failed" ? (
                    <Chip tone="stop">payment declined</Chip>
                  ) : null}
                </div>
                <div className="tiny muted">
                  {m.units} units · {m.travel_minutes} min walk ·{" "}
                  {m.state.replace(/_/g, " ")}
                </div>
              </div>
              <div className="row-tail">
                <div className="fact-value num">
                  {m.final_cost_display || m.estimated_cost_display}
                </div>
                <div className="tiny faint">
                  {m.savings_pct ? `${m.savings_pct} off` : "estimated"}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {me ? (
        <section className="panel panel-pad stack-sm">
          <h2 className="section-title">Your part in this</h2>
          <p className="small muted prose">
            You are in for {me.units} units at{" "}
            {me.final_cost_display || me.estimated_cost_display}
            {me.path === "smart_join"
              ? " — Pool committed on your behalf because every rule you set passed."
              : me.path === "human_approved"
                ? " — you were asked, and you said yes."
                : "."}
          </p>
          <div className="btn-row">
            {recruiting && !alreadyCandidate ? (
              <button
                className="btn btn-sm"
                disabled={busy}
                onClick={() =>
                  act("You are in the candidate set. Pool ranks everyone and offers the job to the best fit.", () =>
                    api.volunteerHost(pool.pool_id, identity.id, { has_vehicle: true }),
                  )
                }
              >
                Offer to carry this
              </button>
            ) : null}
            <button
              className="btn btn-sm btn-ghost"
              disabled={busy}
              onClick={() =>
                act("You have left this pool.", () => api.withdraw(pool.pool_id, identity.id))
              }
            >
              Leave this pool
            </button>
            {locked ? (
              <span className="tiny faint">
                Leaving is refused once the money is captured and the order placed.
              </span>
            ) : null}
          </div>
          {outcome ? (
            <div className={outcome.ok ? "banner" : "banner banner-warn"} role="status">
              <span>{outcome.text}</span>
            </div>
          ) : null}
        </section>
      ) : null}

      {pool.host_candidates && pool.host_candidates.length > 0 ? (
        <details className="panel">
          <summary className="panel-head">
            <strong>Considered for the job · {pool.host_candidates.length} candidates</strong>
            <span className="spacer" />
            <ActorTag actor="engine" label="Ranked on facts" />
          </summary>
          <div className="rows">
            {pool.host_candidates.map((c) => (
              <div key={c.household_id} className="row">
                <span
                  style={{ color: c.eligible ? "var(--ink)" : "var(--ink-faint)", display: "flex" }}
                >
                  {c.eligible ? <IconCheck /> : <IconCross />}
                </span>
                <div className="row-body">
                  <div className="row-title">
                    {c.display_name}
                    <Chip tone={c.eligible ? "ok" : "warn"}>
                      {c.eligible ? c.state.replace(/_/g, " ") : "not eligible"}
                    </Chip>
                  </div>
                  <div className="tiny muted">
                    {c.source === "standing" ? "standing host" : "offered for this pool"} ·{" "}
                    {c.supplier_distance_km} km · {c.estimated_reward_display}
                  </div>
                  {c.ineligible_reasons.length > 0 ? (
                    <div className="tiny" style={{ color: "var(--ink-faint)" }}>
                      {c.ineligible_reasons.join(" · ")}
                    </div>
                  ) : (
                    <div className="tiny mono faint">
                      {Object.entries(c.score_components)
                        .map(([k, v]) => `${k} ${v > 0 ? "+" : ""}${v}`)
                        .join("   ")}
                    </div>
                  )}
                </div>
                <div className="row-tail">
                  <div className="fact-value num">{c.score}</div>
                  <div className="tiny faint">score</div>
                </div>
              </div>
            ))}
          </div>
        </details>
      ) : null}
    </div>
  );
}

/* ----------------------------------------------------------------- economics */

function EconomicsTab({
  pool,
  myUnits,
}: {
  pool: PoolView;
  /** How many of the purchased units belong to the person reading, so the drawing can
   *  show them their own slice. Zero when they are not in this order. */
  myUnits: number;
}) {
  const e = pool.economics;
  if (!e) {
    return (
      <Empty>
        The exact price is not known yet. Host compensation is part of what buyers pay, so nothing
        is priced precisely until a host has accepted and the supplier quote has been
        re-verified.
      </Empty>
    );
  }
  return (
    <div className="stack">
      <section className="panel">
        <div className="panel-head">
          <h2>Where the money goes</h2>
          <span className="spacer" />
          <ActorTag actor="engine" label="Every figure computed" />
        </div>
        <div className="panel-pad">
          <p className="small muted" style={{ marginBottom: 14 }}>
            {e.host_is_estimated
              ? "Estimated range: host compensation is not fixed yet."
              : "Final: every component is fixed at the exact buyer offer."}
          </p>
          <div className="ledger">
            <LedgerLine label="Bulk merchandise" value={money(e.merchandise_cents)} />
            <LedgerLine
              label="Host compensation"
              value={money(e.host_compensation_cents)}
            />
            <LedgerLine label="Card processing" value={money(e.payment_processing_cents)} />
            <LedgerLine label="Pool's platform fee" value={money(e.platform_fee_cents)} />
            <LedgerLine label="All-in cost" value={money(e.all_in_cents)} kind="total" />
            <LedgerLine
              label="The same items bought alone, at retail"
              value={money(e.retail_baseline_cents)}
              kind="baseline"
            />
            <LedgerLine label="Net saving" value={money(e.net_savings_cents)} kind="gain" />
          </div>
          {/* One line, at the only place the supplier's number is the subject.
              The product above it is real — a brand a judge recognises, with its own
              photograph — and that is exactly why this has to be said here rather than
              left to the About page: a recognisable brand beside an unlabelled wholesale
              price implies a relationship that does not exist (AGENTS.md §8, §12). */}
          {pool.offer_source === "synthetic" ? (
            <p className="tiny faint" style={{ marginTop: 14 }}>
              The supplier, this quote, its case size and its minimum are invented for
              this demo. No wholesale relationship exists and no manufacturer is involved.
              Every figure above is computed from those terms by Pool's own arithmetic.
            </p>
          ) : null}
        </div>
      </section>

      <section className="grid grid-2">
        <div className="panel panel-pad">
          <h2 className="section-title" style={{ marginBottom: 12 }}>
            Nothing left over
          </h2>
          {/* Drawn before it is described. The invariant is that every purchased unit has
              a buyer, and a picture of full cases is the only version of that sentence a
              reader does not have to reconstruct. */}
          <CaseFit
            caseUnits={e.packages.case_units}
            cases={e.packages.cases}
            mine={myUnits}
            unit={pool.unit || "unit"}
          />
          <p className="small muted">
            {e.packages.cases} case{e.packages.cases === 1 ? "" : "s"} of{" "}
            {e.packages.case_units} = {e.packages.units_purchased} units for{" "}
            {e.packages.total_units} ordered.{" "}
            {e.packages.surplus_resolved
              ? "No speculative surplus."
              : `${e.packages.surplus_units} unit(s) would be unallocated, which is why this cannot lock.`}
          </p>
          {e.packages.surplus_resolved ? (
            <details style={{ marginTop: 10 }}>
              <summary className="tiny muted">
                Why exact cases matter
              </summary>
              <p className="tiny muted prose" style={{ marginTop: 8 }}>
                Pool selects the buyer set that fills whole cases exactly instead of buying
                stock nobody ordered and billing somebody for it.
              </p>
            </details>
          ) : null}
        </div>
        <details className="panel">
          <summary className="panel-head">
            <strong>Why Pool charges anything</strong>
          </summary>
          <div className="panel-pad">
            <p className="small muted">
              Pool's fee is a share of the saving it created, so no saving means no fee. If
              fair host pay erased the discount, the pool would not form. Processing is
              grossed up per buyer so the platform does not silently subsidise the charge.
            </p>
          </div>
        </details>
      </section>
    </div>
  );
}

/* ---------------------------------------------------------------- fulfilment */

function FulfilmentTab({
  pool,
  identity,
  onRefresh,
}: {
  pool: PoolView;
  identity: { id: string; display_name: string };
  onRefresh: () => void;
}) {
  const [checklist, setChecklist] = useState<Checklist | null>(null);
  const [credential, setCredential] = useState<Credential | null>(null);
  const [error, setError] = useState<string | null>(null);

  const open = pool.status === "distributing" || pool.status === "completed";

  useEffect(() => {
    if (!open) return;
    api.checklist(pool.pool_id).then(setChecklist).catch(() => setChecklist(null));
  }, [open, pool.pool_id, pool.status]);

  if (!open) {
    return (
      <Empty>
        Collection has not opened yet. It opens once the order has been placed and the
        pickup window arrives.
      </Empty>
    );
  }

  /* Whose credential this issues. A member looking at their own order should be able to
     get *their* code; falling through to whoever sorts first was an operator affordance
     wearing a member's screen. Anyone not in the pool still sees the mechanism, which is
     what the host console and the drawer exercise for everybody else. */
  const collectable = (pool.members ?? []).filter((m) => m.state !== "authorization_failed");
  const subject =
    collectable.find((m) => m.household_id === identity.id) ?? collectable[0] ?? undefined;
  const isMine = Boolean(subject && subject.household_id === identity.id);

  return (
    <div className="stack">
      {checklist ? (
        <section className="grid grid-2">
          <Figure
            label="Collected"
            value={`${checklist.picked_up} / ${checklist.total}`}
            accent={checklist.picked_up === checklist.total}
            sub={`${checklist.units_total} units in total`}
          />
          {/* Host pay is stated once on this page, under "The host, the pickup point,
              and every check Pool ran". These were separate tabs and could not collide;
              on one page they would print the same figure twice in one frame. */}
          <Figure
            label="Window"
            value={shortTime(checklist.distribution_starts_at)}
            small
            sub={`until ${shortTime(checklist.distribution_ends_at)}`}
          />
        </section>
      ) : null}

      <section className="panel">
        <div className="panel-head">
          <h2>Pickup credentials</h2>
          <span className="spacer" />
          <span className="tiny faint">one-time, hashed at rest</span>
        </div>
        <div className="panel-pad stack-sm">
          <p className="small muted prose">
            Every handoff requires a one-time buyer credential; only hashes are stored.
          </p>
          <details className="inset">
            <summary className="small">
              <strong>Credential mechanics</strong>
            </summary>
            <p className="small muted prose" style={{ marginTop: 10 }}>
              A QR token and short code are shown once in the issuing response. Reissuing
              voids the prior pair, and a host cannot mark an order collected without one.
            </p>
          </details>
          {pool.status === "completed" ? (
            <p className="small muted prose">
              Every handoff is confirmed; the server now refuses fresh credentials.
            </p>
          ) : null}
          {subject ? (
            <div className="btn-row">
              <button
                className="btn btn-sm"
                onClick={async () => {
                  try {
                    setCredential(await api.issueCredential(pool.pool_id, subject.household_id));
                    setError(null);
                    onRefresh();
                  } catch (err) {
                    setCredential(null);
                    setError(err instanceof Error ? err.message : String(err));
                  }
                }}
              >
                {isMine ? "Show my code" : `Issue ${subject.display_name}'s code`}
              </button>
            </div>
          ) : null}
          {error ? (
            <div className="banner" role="status">
              <span>
                Refused by the server: <strong>{error}</strong>. A credential is bound to
                one uncollected allocation and works exactly once.
              </span>
            </div>
          ) : null}
          {credential ? (
            <div className="inset">
              <div className="fact-label">One-time code</div>
              <div
                className="display"
                style={{ fontSize: 34, letterSpacing: "0.18em", marginTop: 4 }}
              >
                {credential.code}
              </div>
              <p className="tiny muted" style={{ marginTop: 6 }}>
                Works once.{" "}
                {credential.replaced_previous ? "The code issued before this is now void." : ""}
              </p>
            </div>
          ) : null}
        </div>
      </section>

      {checklist ? (
        <section className="panel">
          <div className="panel-head">
            <h2>Orders</h2>
          </div>
          <div className="rows">
            {checklist.orders.map((o) => (
              <div key={o.household_id} className="row">
                <span
                  style={{
                    color: o.state === "picked_up" ? "var(--ink)" : "var(--ink-faint)",
                    display: "flex",
                  }}
                >
                  {o.state === "picked_up" ? <IconCheck /> : <IconDot />}
                </span>
                <div className="row-body">
                  <div className="row-title">{o.display_name}</div>
                  <div className="tiny muted">
                    {o.units} units · {o.state.replace(/_/g, " ")}
                    {o.via ? ` · confirmed by ${o.via}` : ""}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ activity */

function ActivityTab({
  pool,
  entryDeep,
  runs,
  activity,
  scenario,
  scenarioMs,
  running,
  health,
  demoConfig,
  live,
  liveBusy,
  onRunLive,
  onRunScenario,
}: {
  pool: PoolView;
  entryDeep?: string;
  runs: RunSummary[];
  activity: ActivityEvent[];
  scenario: ScenarioResult | null;
  scenarioMs: number | null;
  running: boolean;
  health: Health | null;
  demoConfig: DemoConfig | null;
  live: LiveAgentResult | null;
  liveBusy: boolean;
  onRunLive: () => void;
  /** Only the showcase and the demo controls may start the scripted lifecycle: it
   *  replays a different world, and offering it from an ordinary pool record invited a
   *  member to "start the community over" from inside their own order. */
  onRunScenario?: () => void;
}) {
  const [deep, setDeep] = useState<"none" | "walkthrough" | "execution">(
    (entryDeep as "walkthrough" | "execution") ?? "none",
  );
  const proof = pool.execution_proof;
  const sameWorkspaceReadback = Boolean(
    proof?.workspace_readback.run_recorded &&
      proof.workspace_readback.pool_recorded &&
      proof.workspace_readback.same_workspace,
  );

  if (deep === "walkthrough" && scenario) {
    return (
      <div className="stack">
        <div className="btn-row">
          <button className="btn btn-sm btn-ghost" onClick={() => setDeep("none")}>
            <IconArrowLeft />
            Back to activity
          </button>
        </div>
        <RunView
          scenario={scenario}
          roundTripMs={scenarioMs}
          running={running}
          onRun={onRunScenario}
          onOpenPool={() => setDeep("none")}
          onLive={() => setDeep("execution")}
          embedded
        />
      </div>
    );
  }

  if (deep === "execution") {
    return (
      <div className="stack">
        <div className="btn-row">
          <button className="btn btn-sm btn-ghost" onClick={() => setDeep("none")}>
            <IconArrowLeft />
            Back to activity
          </button>
        </div>
        <AgentExecution
          config={demoConfig}
          health={health}
          result={live}
          busy={liveBusy}
          onRun={onRunLive}
          runs={runs}
          proof={pool.execution_proof}
        />
      </div>
    );
  }

  return (
    <div className="stack">
      <section className="grid grid-side">
        <div className="panel panel-pad stack-sm">
          <div className="row-between">
            <h2 className="section-title">Technical proof for this run</h2>
            {proof ? (
              <Chip tone={proof.execution.live ? "live" : "info"}>
                {proof.execution.live ? "AgentCore live" : proof.run.model_provider}
              </Chip>
            ) : null}
          </div>
          {proof ? (
            <>
              <ProofIdentity
                runId={proof.run.run_id}
                poolId={proof.pool_id}
                createdByRun={proof.created_by_run}
                sameWorkspace={sameWorkspaceReadback}
              />
              <div>
                <div className="fact-label" style={{ marginBottom: 6 }}>
                  Selected tool sequence
                </div>
                <TracePills names={proof.run.tool_calls} ordered />
              </div>
              <ExecutionPath live={proof.execution.live} />
            </>
          ) : (
            <p className="tiny faint">
              This pool has no server-verified run relationship to display.
            </p>
          )}
          <div className="btn-row push">
            <button className="btn btn-sm" onClick={() => setDeep("execution")}>
              Open complete proof
            </button>
          </div>
        </div>

        <div className="panel panel-pad stack-sm">
          <h2 className="section-title">How this pool happened</h2>
          <p className="small muted">
            Thirteen recorded stages from discovery through decline, repair, lock and
            handover.
          </p>
          {!scenario ? (
            <p className="tiny faint">
              {onRunScenario
                ? "Replays Demo University from the beginning in the showcase's own copy of the community, and records every stage. Your own account is not touched."
                : "Available from Showcase and from Demo controls, where it replays the community from the beginning in its own copy."}
            </p>
          ) : null}
          <div className="btn-row push">
            {scenario ? (
              <button className="btn btn-sm" onClick={() => setDeep("walkthrough")}>
                Open the walkthrough
              </button>
            ) : onRunScenario ? (
              <button className="btn btn-sm" onClick={onRunScenario} disabled={running}>
                {running ? "Running…" : "Run the full lifecycle"}
              </button>
            ) : null}
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>What happened to this pool</h2>
          <span className="spacer" />
          <span className="actor-key">
            <span className="actor actor-agent">
              <ActorGlyph actor="agent" />
              Pool acted
            </span>
            <span className="actor actor-human">
              <ActorGlyph actor="human" />A person answered
            </span>
          </span>
        </div>
        <Feed events={activity} limit={12} />
      </section>

      <p className="tiny faint">
        Audit records keep trigger, tools, iterations, termination and tokens — no model
        reasoning text; tool arguments are hashed.
      </p>
    </div>
  );
}
