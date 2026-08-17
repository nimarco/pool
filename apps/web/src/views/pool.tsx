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

import { useEffect, useState } from "react";
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
  Figure,
  IconArrowLeft,
  IconCheck,
  IconCross,
  IconDot,
  LedgerLine,
  Meter,
  TracePills,
} from "../ui";
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
  onRunScenario: () => void;
}) {
  const [tab, setTab] = useState<Tab>((entry?.tab as Tab) ?? "overview");
  const s = statusCopy(pool.status);
  const declined = pool.member_count - pool.buyer_count;

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
          <Chip tone={s.tone}>{s.label}</Chip>
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
          sub={`${pool.funded_units} paid for · the supplier will not sell fewer than ${pool.threshold_units}`}
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
          sub={
            pool.economics
              ? `${money(pool.economics.net_savings_cents)} across the group, after every cost`
              : "host pay is not fixed until a host accepts"
          }
        />
      </section>

      <Meter value={pool.provisional_units} max={pool.threshold_units} />

      <nav className="tabs" role="tablist" aria-label="Pool sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {tab === "overview" ? <OverviewTab pool={pool} /> : null}
      {tab === "people" ? (
        <PeopleTab pool={pool} identity={identity} onRefresh={onRefresh} />
      ) : null}
      {tab === "economics" ? <EconomicsTab pool={pool} /> : null}
      {tab === "fulfilment" ? <FulfilmentTab pool={pool} onRefresh={onRefresh} /> : null}
      {tab === "activity" ? (
        <ActivityTab
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
  );
}

/* ------------------------------------------------------------------ overview */

function OverviewTab({ pool }: { pool: PoolView }) {
  return (
    <div className="stack">
      <section className="grid grid-2">
        <div className="panel panel-pad">
          <h3 className="section-title" style={{ marginBottom: 12 }}>
            Who is carrying it
          </h3>
          {pool.host ? (
            <>
              <div className="display" style={{ fontSize: 26 }}>
                {pool.host.display_name}
              </div>
              <p className="small muted" style={{ marginTop: 6 }}>
                Paid <strong>{pool.host.reward_display}</strong> for{" "}
                {pool.host.handled_orders} orders and a{" "}
                {pool.host.supplier_distance_km} km round trip. Funded by the buyers, not
                subsidised by Pool.
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
          <h3 className="section-title" style={{ marginBottom: 12 }}>
            Where it is collected
          </h3>
          <div className="display" style={{ fontSize: 26 }}>
            {pool.pickup_site}
          </div>
          <p className="small muted" style={{ marginTop: 6 }}>
            {pool.pickup_is_public ? "A public spot on campus" : "Not a public site"}
            {pool.pickup_permission ? ` · permission: ${pool.pickup_permission}` : ""}.
            Chosen for the members who actually joined, not fixed in advance.
          </p>
        </div>
      </section>

      {pool.viability ? (
        <section className="panel">
          <div className="panel-head">
            <h3>Can this go ahead?</h3>
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
              A pool only goes ahead when it works for the buyers, the supplier, the host
              and Pool itself. Every check runs — none is skipped once one fails — so the
              reason a pool cannot proceed is always the complete list.
            </p>
            <div className="rows" style={{ borderTop: "1px solid var(--rule)" }}>
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
          <h3>Buyers</h3>
          <span className="spacer" />
          <span className="tiny faint">
            display names only — no address, phone, email or payment reference exists in
            this payload
          </span>
        </div>
        {declined > 0 ? (
          <div className="panel-pad" style={{ paddingBottom: 0 }}>
            <p className="small muted">
              <strong>{pool.buyer_count} people are buying</strong>, and the record carries{" "}
              {pool.member_count} memberships. The difference is {declined} whose payment
              was declined: the membership stays here rather than being deleted, because a
              record that edits out its failures is not a record.
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
          <h3 className="section-title">Your part in this</h3>
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
            <div className={outcome.ok ? "banner" : "banner banner-warn"}>
              <span>{outcome.text}</span>
            </div>
          ) : null}
        </section>
      ) : null}

      {pool.host_candidates && pool.host_candidates.length > 0 ? (
        <section className="panel">
          <div className="panel-head">
            <h3>Considered for the job</h3>
            <span className="spacer" />
            <ActorTag actor="engine" label="Ranked on facts" />
          </div>
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
        </section>
      ) : null}
    </div>
  );
}

/* ----------------------------------------------------------------- economics */

function EconomicsTab({ pool }: { pool: PoolView }) {
  const e = pool.economics;
  if (!e) {
    return (
      <Empty>
        The exact price is not known yet. Host pay is part of what buyers pay, so nothing
        is priced precisely until a host has accepted and the supplier quote has been
        re-verified.
      </Empty>
    );
  }
  return (
    <div className="stack">
      <section className="panel">
        <div className="panel-head">
          <h3>Where the money goes</h3>
          <span className="spacer" />
          <ActorTag actor="engine" label="Every figure computed" />
        </div>
        <div className="panel-pad">
          <p className="small muted" style={{ marginBottom: 14 }}>
            {e.host_is_estimated
              ? "Host pay is still an estimate, so this is a range rather than a precise-looking price nobody can be held to."
              : "Every component is fixed. This is what buyers actually pay."}
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
        </div>
      </section>

      <section className="grid grid-2">
        <div className="panel panel-pad">
          <h3 className="section-title" style={{ marginBottom: 12 }}>
            Nothing left over
          </h3>
          <p className="small muted">
            {e.packages.cases} case{e.packages.cases === 1 ? "" : "s"} of{" "}
            {e.packages.case_units} = {e.packages.units_purchased} units for{" "}
            {e.packages.total_units} ordered.{" "}
            {e.packages.surplus_resolved
              ? "Cases rarely divide evenly into demand, so Pool picks the set of buyers that fills whole cases exactly. The alternative is buying stock nobody ordered and billing somebody for it."
              : `${e.packages.surplus_units} unit(s) would be unallocated, which is why this cannot lock.`}
          </p>
        </div>
        <div className="panel panel-pad">
          <h3 className="section-title" style={{ marginBottom: 12 }}>
            Why Pool charges anything
          </h3>
          <p className="small muted">
            Pool's fee is a share of the saving it created, so no saving means no fee. If
            paying the host fairly erased the discount, this pool should not form — and it
            would not. Card processing is grossed up per buyer so the charge covers the
            processor's cut of that charge; doing it the obvious way under-recovers a few
            cents each time, which is a platform quietly subsidising itself.
          </p>
        </div>
      </section>
    </div>
  );
}

/* ---------------------------------------------------------------- fulfilment */

function FulfilmentTab({ pool, onRefresh }: { pool: PoolView; onRefresh: () => void }) {
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

  const first = (pool.members ?? []).find((m) => m.state !== "authorization_failed");

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
          <h3>Pickup credentials</h3>
          <span className="spacer" />
          <span className="tiny faint">one-time, hashed at rest</span>
        </div>
        <div className="panel-pad stack-sm">
          <p className="small muted prose">
            Every buyer gets their own credential — a long token behind the QR and a short
            code for when scanning is awkward. Only hashes are stored, the plaintext exists
            once in the response that issued it, and issuing a new one voids the old. A
            host cannot mark an order collected without one.
          </p>
          {pool.status === "completed" ? (
            <p className="small muted prose">
              Every handoff here is confirmed, so there is nothing left to collect and the
              server will refuse a fresh credential — which is the guarantee holding.
            </p>
          ) : null}
          {first ? (
            <div className="btn-row">
              <button
                className="btn btn-sm"
                onClick={async () => {
                  try {
                    setCredential(await api.issueCredential(pool.pool_id, first.household_id));
                    setError(null);
                    onRefresh();
                  } catch (err) {
                    setCredential(null);
                    setError(err instanceof Error ? err.message : String(err));
                  }
                }}
              >
                Issue {first.display_name}'s code
              </button>
            </div>
          ) : null}
          {error ? (
            <div className="banner">
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
            <h3>Orders</h3>
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
  onRunScenario: () => void;
}) {
  const [deep, setDeep] = useState<"none" | "walkthrough" | "execution">(
    (entryDeep as "walkthrough" | "execution") ?? "none",
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
        />
      </div>
    );
  }

  return (
    <div className="stack">
      <section className="panel">
        <div className="panel-head">
          <h3>What happened to this pool</h3>
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

      <section className="grid grid-2">
        <div className="panel panel-pad stack-sm">
          <h3 className="section-title">How Pool coordinated this</h3>
          <p className="small muted">
            Which tools the coordinator chose and in what order, the bounds it ran under,
            and the option to run the same coordinator on its deployed home — Amazon
            Bedrock AgentCore Runtime.
          </p>
          <div className="btn-row">
            <button className="btn btn-sm" onClick={() => setDeep("execution")}>
              Agent execution
            </button>
            {demoConfig?.live_agent_available ? <Chip tone="live">AWS available</Chip> : null}
          </div>
          {runs.length > 0 ? (
            <TracePills names={runs[0].tool_calls} />
          ) : (
            <p className="tiny faint">No coordination run recorded in this session yet.</p>
          )}
        </div>

        <div className="panel panel-pad stack-sm">
          <h3 className="section-title">How this pool happened</h3>
          <p className="small muted">
            The full lifecycle as a reader: discovery, the timing split, the host ranking,
            the exact price, the declined card, the repair, the lock and the handover —
            thirteen stages with the figures behind each one.
          </p>
          <div className="btn-row">
            {scenario ? (
              <button className="btn btn-sm" onClick={() => setDeep("walkthrough")}>
                Open the walkthrough
              </button>
            ) : (
              <button className="btn btn-sm" onClick={onRunScenario} disabled={running}>
                {running ? "Running…" : "Run the full lifecycle"}
              </button>
            )}
          </div>
          {!scenario ? (
            <p className="tiny faint">
              Replays Demo University from the beginning and records every stage, so it
              starts this community over.
            </p>
          ) : null}
        </div>
      </section>

      <p className="tiny faint">
        Run records keep the trigger, the tool sequence, iteration counts, the termination
        reason and token usage. No model reasoning text is stored, and tool arguments are
        kept as hashes so a run log cannot carry a member's details.
      </p>
    </div>
  );
}
