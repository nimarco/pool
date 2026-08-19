/* One pool, as a persistent product record.
 *
 * Five tabs, in the order somebody actually asks about them: what is it, who is in it,
 * what does it cost, how do I get it, and — for anyone who wants to audit the thing —
 * what happened and what did the agent do.
 *
 * The technical evidence a judge needs lives on the last tab rather than in the
 * navigation: the coordinator's tool sequence, the deployed AgentCore run, and the
 * step-by-step lifecycle reader. It strengthens the record instead of replacing it.
 *
 * Everything numeric is read from the pool payload. `buyer_count` and `member_count` are
 * both server-computed and both shown, because after a declined card they differ and
 * that difference is a fact about the pool rather than a rounding error.
 */

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
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

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "people", label: "People" },
  { id: "economics", label: "Economics" },
  { id: "fulfilment", label: "Fulfilment" },
  { id: "activity", label: "Activity" },
];

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
  const [tab, setTab] = useState<Tab>((entry?.tab as Tab) ?? "overview");
  const tablist = useRef<HTMLElement | null>(null);
  const s = statusCopy(pool.status);
  const declined = pool.member_count - pool.buyer_count;

  /* The tab strip scrolls on a phone, and the record can be entered directly on
     Activity — so the selected tab has to bring itself into view or it is simply not
     there. */
  useEffect(() => {
    const selected = tablist.current?.querySelector<HTMLElement>('[aria-selected="true"]');
    // Guarded: not every rendering environment implements it, and a tab strip that
    // cannot self-scroll should still show its tabs.
    selected?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
  }, [tab]);

  /* Roving tab order: one stop for the whole strip, arrows between the tabs. */
  const onTabKey = (event: KeyboardEvent) => {
    const at = TABS.findIndex((t) => t.id === tab);
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    let next = -1;
    if (step !== 0) next = (at + step + TABS.length) % TABS.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = TABS.length - 1;
    if (next < 0) return;
    event.preventDefault();
    setTab(TABS[next].id);
    const buttons = tablist.current?.querySelectorAll<HTMLElement>('[role="tab"]');
    buttons?.[next]?.focus();
  };

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
            <p className="small muted" style={{ marginTop: 6 }}>
              {pool.brand ? `${pool.brand} · ` : ""}
              {pool.supplier} · collect from {pool.pickup_site}
              {pool.timing?.distribution_starts_at
                ? ` · ${shortTime(pool.timing.distribution_starts_at)}`
                : ""}
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

      <section className="grid grid-3">
        <Figure
          label="Units"
          value={`${pool.provisional_units} / ${pool.threshold_units}`}
          sub={`${pool.funded_units} units authorized · the supplier will not sell fewer than ${pool.threshold_units}`}
        />
        <Figure
          label="Buyers"
          value={String(pool.buyer_count)}
          sub={
            declined > 0
              ? `${pool.member_count} memberships on the record — ${declined} declined and kept`
              : "everyone still in"
          }
        />
        <Figure
          label={pool.is_estimate ? "Estimated saving" : "Saving against retail"}
          value={pool.savings_pct || "—"}
          accent={!pool.is_estimate}
          sub={groupSavingsCaption(pool)}
        />
      </section>

      <Meter value={pool.provisional_units} max={pool.threshold_units} />

      <nav
        className="tabs"
        role="tablist"
        aria-label="Pool sections"
        ref={tablist}
        onKeyDown={onTabKey}
      >
        {TABS.map((t) => (
          <button
            key={t.id}
            id={`pooltab-${t.id}`}
            role="tab"
            aria-selected={tab === t.id}
            aria-controls={`poolpanel-${t.id}`}
            tabIndex={tab === t.id ? 0 : -1}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div
        role="tabpanel"
        id={`poolpanel-${tab}`}
        aria-labelledby={`pooltab-${tab}`}
        className="stack"
      >
      {tab === "overview" ? <OverviewTab pool={pool} /> : null}
      {tab === "people" ? (
        <PeopleTab pool={pool} identity={identity} onRefresh={onRefresh} />
      ) : null}
      {tab === "economics" ? (
        <EconomicsTab
          pool={pool}
          myUnits={
            mine
              ? (pool.members ?? []).find((m) => m.household_id === identity.id)?.units ?? 0
              : 0
          }
        />
      ) : null}
      {tab === "fulfilment" ? (
        <FulfilmentTab pool={pool} identity={identity} onRefresh={onRefresh} />
      ) : null}
      {tab === "activity" ? (
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
      ) : null}
      </div>
    </div>
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
                        color: c.passed ? "var(--moss)" : "var(--clay)",
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
                  style={{ color: c.eligible ? "var(--moss)" : "var(--clay)", display: "flex" }}
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
                    <div className="tiny" style={{ color: "var(--clay)" }}>
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
        <section className="grid grid-3">
          <Figure
            label="Collected"
            value={`${checklist.picked_up} / ${checklist.total}`}
            accent={checklist.picked_up === checklist.total}
            sub={`${checklist.units_total} units in total`}
          />
          <Figure
            label="The host earns"
            value={String((checklist.earnings as Record<string, string>).total_display ?? "—")}
          />
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
                    color: o.state === "picked_up" ? "var(--moss)" : "var(--ink-faint)",
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
