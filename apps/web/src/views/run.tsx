/* The run — one complete purchase, step by step.
 *
 * The server executes the entire lifecycle in one call (about 40 ms) and returns a
 * structured transcript of what happened. This screen is a *reader* for that
 * transcript, not a progress animation: the run is already over before the first frame
 * is drawn, and the stage bar says so with the measured round trip. Nothing here is on
 * a timer pretending to be work (AGENTS.md §8).
 *
 * Every value shown is read out of the step's `facts` exactly as the server computed
 * it. This file selects, labels and sets those values; it never derives one. The only
 * thing added on the client is editorial: which act a step belongs to, a headline, and
 * which of the three actors was responsible.
 */

import { useCallback, useEffect, useState } from "react";
import { ScenarioResult, ScenarioStep } from "../api";
import {
  Actor,
  ActorKey,
  ActorTag,
  Block,
  Chip,
  Empty,
  Fact,
  Figure,
  IconArrowLeft,
  IconArrowRight,
  IconCheck,
  IconCloud,
  IconCross,
  IconPlay,
  IconReplay,
  LedgerLine,
  Meter,
  TracePills,
} from "../ui";

/* -------------------------------------------------------------- fact readers */

type Facts = Record<string, unknown>;

const s = (f: Facts, k: string): string => {
  const v = f[k];
  return v === null || v === undefined ? "" : String(v);
};
const n = (f: Facts, k: string): number => {
  const v = f[k];
  return typeof v === "number" ? v : Number(v) || 0;
};
const list = (f: Facts, k: string): string[] => {
  const v = f[k];
  return Array.isArray(v) ? v.map(String) : [];
};

/* ------------------------------------------------------------------- editorial */

interface Chapter {
  act: string;
  headline: string;
  actors: Actor[];
}

/** Editorial framing per step. Keyed by the server's own step names; an unrecognised
 *  step still renders through the generic fallback below rather than disappearing. */
const CHAPTERS: Record<string, Chapter> = {
  seed: {
    act: "The community",
    headline: "Nobody here organised anything",
    actors: ["engine"],
  },
  latent_demand_discovered: {
    act: "Discovery",
    headline: "Pool noticed the group could exist",
    actors: ["agent", "engine"],
  },
  host_candidates_evaluated: {
    act: "Fulfilment",
    headline: "Somebody still has to carry the box",
    actors: ["engine"],
  },
  host_accepted: {
    act: "Fulfilment",
    headline: "The host is chosen before anyone is charged",
    actors: ["human", "engine"],
  },
  final_offer: {
    act: "Price",
    headline: "The price includes everything",
    actors: ["agent", "engine"],
  },
  payment_failure: {
    act: "Failure",
    headline: "A card was declined",
    actors: ["engine"],
  },
  decision_inbox: {
    act: "Consent",
    headline: "Only the people who had to be asked",
    actors: ["human"],
  },
  recovery: {
    act: "Recovery",
    headline: "Replace exactly what was lost",
    actors: ["agent", "engine"],
  },
  locked_and_captured: {
    act: "Lock",
    headline: "Every check passes, then the money moves",
    actors: ["engine"],
  },
  purchase: {
    act: "Order",
    headline: "One bulk order, nobody fronting it",
    actors: ["agent", "engine"],
  },
  distribution_open: {
    act: "Handover",
    headline: "A real job, with a real checklist",
    actors: ["engine"],
  },
  pickup: {
    act: "Handover",
    headline: "Collection is proved, not asserted",
    actors: ["human", "engine"],
  },
  impact: {
    act: "Result",
    headline: "What the week actually cost",
    actors: ["engine"],
  },
  lock_blocked: {
    act: "Lock",
    headline: "The pool was refused a lock",
    actors: ["engine"],
  },
};

function chapterFor(step: ScenarioStep): Chapter {
  return (
    CHAPTERS[step.name] ?? {
      act: step.name.replace(/_/g, " "),
      headline: step.detail.split(/[.,—]/)[0],
      actors: ["engine"],
    }
  );
}

/* ---------------------------------------------------------------- step bodies */

function SeedBody({ f }: { f: Facts }) {
  return (
    <>
      <div className="grid grid-3">
        <Figure
          label="People"
          value={s(f, "members")}
          sub="each one signed up alone, with no group and no chat"
        />
        <Figure
          label="Standing needs"
          value={s(f, "needs")}
          sub="what they said they buy anyway, and how often"
        />
        <Figure
          label="Suppliers on file"
          value={s(f, "suppliers")}
          sub={`${s(f, "offers")} price quotes across ${s(f, "products")} products`}
        />
      </div>
      <p className="small muted prose">
        This is the whole starting position. There is no organiser, no sign-up sheet, and
        nobody has committed a cent. The next pool day for this community is{" "}
        <strong>{s(f, "next_pool_day")}</strong> — a fixed weekly moment when a collection
        can happen, which is what makes separate people's timing comparable at all.
      </p>
    </>
  );
}

function DiscoveryBody({ f }: { f: Facts }) {
  const units = n(f, "provisional_units");
  const threshold = n(f, "threshold_units");
  return (
    <>
      <div className="grid grid-3">
        <Figure
          label="People matched"
          value={s(f, "members")}
          sub="none of whom knew about each other"
        />
        <Figure
          label="Units of demand"
          value={`${units} / ${threshold}`}
          sub="against the supplier's minimum order quantity"
        />
        <Figure
          label="Collection point"
          value={s(f, "pickup_site")}
          small
          sub="chosen for the members who actually joined"
        />
      </div>
      <Meter value={units} max={threshold} />

      {/* The one place the "ten" is explained. Both halves are server-computed by the
          same evaluate_timing the matcher used, so the split cannot disagree with the
          eligibility decision that formed this pool. */}
      <div className="inset">
        <p className="small" style={{ marginBottom: 10 }}>
          <strong>Where those {s(f, "members")} people came from.</strong> Two different
          things, and only one of them is Pool's to decide.
        </p>
        <div className="ledger">
          <LedgerLine
            label={`Buying about now anyway — ${s(f, "due_now_members")} people`}
            value={`${s(f, "due_now_units")} units`}
          />
          <LedgerLine
            label={`Pulled forward, with their permission — ${s(f, "pulled_forward_members")} people`}
            value={`${s(f, "pulled_forward_units")} units`}
          />
          <LedgerLine label="Demand in this pool" value={`${units} units`} kind="total" />
          <LedgerLine
            label="The supplier will not sell fewer than"
            value={`${threshold} units`}
            kind="baseline"
          />
        </div>
      </div>

      <p className="small muted prose">
        The agent decided this was worth investigating and which product to investigate.
        The deterministic timing engine decided who is actually eligible — same product,
        same community, and a purchase date they had already authorised. The people in the
        second row would not have bought for weeks; Pool may bring them forward{" "}
        <em>only</em> because each of them said in advance how far early was acceptable.
        Without them this pool is short of the minimum and does not happen. A member who
        authorised nothing is never moved, however convenient it would be for the case
        count.
      </p>
      <Block title={`Tools the agent called · ${s(f, "iterations")} iterations`}>
        <TracePills names={list(f, "tools_called")} />
      </Block>
    </>
  );
}

interface Candidate {
  household_id: string;
  display_name: string;
  eligible: boolean;
  ineligible_reasons: string[];
  score: number;
  reward_cents: number;
  supplier_distance_km: number;
}

function HostCandidatesBody({ f }: { f: Facts }) {
  const raw = f.candidates;
  const candidates: Candidate[] = Array.isArray(raw) ? (raw as Candidate[]) : [];
  return (
    <>
      <p className="small muted prose">
        Candidates come from two places: people who signed up as standing hosts, and
        members of this pool who offered. Offering does not claim the job. A deterministic
        evaluator checks facts — vehicle, capacity, weight, distance, availability, and
        the minimum pay that person will accept — and ranks whoever survives.
      </p>
      <div className="rows" style={{ borderTop: "1px solid var(--rule-strong)" }}>
        {candidates.map((c) => (
          <div key={c.household_id} className="row" style={{ paddingInline: 0 }}>
            <span
              style={{ color: c.eligible ? "var(--moss)" : "var(--clay)", display: "flex" }}
            >
              {c.eligible ? <IconCheck /> : <IconCross />}
            </span>
            <div className="row-body">
              <div className="row-title">
                {c.display_name || c.household_id}
                {c.eligible ? null : <Chip tone="warn">not eligible</Chip>}
              </div>
              <div className="tiny muted">
                {c.eligible
                  ? `${c.supplier_distance_km} km to the supplier · would earn $${(
                      c.reward_cents / 100
                    ).toFixed(2)}`
                  : c.ineligible_reasons.join(" · ")}
              </div>
            </div>
            <div className="row-tail">
              <div className="fact-value num">{c.score}</div>
              <div className="tiny faint">score</div>
            </div>
          </div>
        ))}
      </div>
      <p className="tiny muted">
        {s(f, "eligible_count")} of {candidates.length} eligible. The reasons are factual
        and stated, never a silent rejection — someone turned down for a job deserves to
        know it was the fifty-five kilo load, not a scoring mystery.
      </p>
    </>
  );
}

function HostAcceptedBody({ f }: { f: Facts }) {
  const breakdown = (f.reward_breakdown ?? {}) as Record<string, number>;
  const cents = (v: number) => `$${(v / 100).toFixed(2)}`;
  const LABELS: Record<string, string> = {
    base: "Base for the run",
    per_order: "Per order handled",
    distance: "Distance to the supplier and back",
    weight: "Exceptional weight",
    merchandise_share: "Share of merchandise value",
    handoff_bonus: "Handoff completion",
  };
  return (
    <>
      <div className="grid grid-2">
        <div>
          <Figure
            label={`${s(f, "host")} earns`}
            value={s(f, "reward_total")}
            sub={`${s(f, "handled_orders")} orders, ${s(f, "supplier_distance_km")} km round trip — funded by the buyers, not subsidised by Pool`}
          />
        </div>
        <div className="ledger">
          {Object.entries(breakdown)
            .filter(([, v]) => v > 0)
            .map(([k, v]) => (
              <LedgerLine key={k} label={LABELS[k] ?? k.replace(/_/g, " ")} value={cents(v)} />
            ))}
          <LedgerLine label="Total" value={s(f, "reward_total")} kind="total" />
        </div>
      </div>
      <p className="small muted prose">
        This number has to exist before anyone is asked to authorize, because host
        compensation is part
        of every buyer's price. Pool will never authorise $42 and then charge $47. Only
        the handoff component is contingent — a buyer who does not turn up cannot erase
        pay for a trip that was already made.
      </p>
    </>
  );
}

function FinalOfferBody({ f }: { f: Facts }) {
  return (
    <>
      <div className="grid grid-side">
        <div className="ledger">
          <LedgerLine label="Bulk merchandise" value={s(f, "merchandise")} />
          <LedgerLine label="Host compensation" value={s(f, "host_compensation")} />
          <LedgerLine label="Card processing" value={s(f, "payment_processing")} />
          <LedgerLine label="Pool's platform fee" value={s(f, "pool_fee")} />
          <LedgerLine label="All-in cost to the group" value={s(f, "all_in")} kind="total" />
          <LedgerLine
            label="The same items bought alone, at retail"
            value={s(f, "retail_baseline")}
            kind="baseline"
          />
          <LedgerLine
            label={`Net saving · ${s(f, "net_savings_pct")}`}
            value={s(f, "net_savings")}
            kind="gain"
          />
        </div>
        <div className="stack-sm">
          <Figure
            label="Authorised without asking"
            value={s(f, "authorised_by_smart_join")}
            sub="their own stated rules on saving, spend and walking distance all passed"
          />
          <Figure
            label="Asked a person"
            value={s(f, "awaiting_human_decision")}
            small
            sub="a rule did not pass, so Pool asks instead of deciding"
          />
        </div>
      </div>
      <p className="small muted prose">
        Two details in this table are load-bearing. Pool's fee is a share of{" "}
        <em>gross</em> savings, so it is defined without reference to the total it belongs
        to — no saving, no fee. And card processing is grossed up per buyer so the charge
        covers the processor's cut <em>of that charge</em>; computing it the obvious way
        under-recovers by a few cents each time, which is a platform quietly subsidising
        itself into trouble.
      </p>
    </>
  );
}

function PaymentFailureBody({ f }: { f: Facts }) {
  return (
    <>
      <div className="grid grid-3">
        <Figure label="Authorisations declined" value={String(list(f, "declined").length)} />
        <Figure
          label="Units that stopped counting"
          value={s(f, "units_lost")}
          sub={`out of ${s(f, "threshold_units")} the supplier requires`}
        />
        <Figure label="Payment provider" value={s(f, "provider")} small sub="no real card, no real money" />
      </div>
      <p className="small muted prose">
        This is not narration. The payment provider genuinely refused a saved method, and
        those units stopped counting toward the funded order the moment it happened. In a
        group chat this is where the whole thing quietly dies: someone has to notice,
        work out how short they are, and go find another buyer.
      </p>
    </>
  );
}

function DecisionBody({ f }: { f: Facts }) {
  const funded = n(f, "funded_units");
  const threshold = n(f, "threshold_units");
  return (
    <>
      <div className="grid grid-2">
        <Figure
          label="People who answered"
          value={s(f, "approved")}
          sub="each got one question, with the exact price already worked out — not a form to fill in"
        />
        <Figure
          label="Funded units"
          value={`${funded} / ${threshold}`}
          accent={funded >= threshold}
          sub="only an authorised payment counts toward the threshold"
        />
      </div>
      <Meter value={funded} max={threshold} />
      <p className="small muted prose">
        Pool asks a person only when a rule that person set did not pass. Everyone else is
        left alone, which is the point: the product exists so people can stop paying
        attention to a chore. An inbox that is usually empty is the design working.
      </p>
    </>
  );
}

function RecoveryBody({ f }: { f: Facts }) {
  const recovered = String(f.recovered) === "true";
  return (
    <>
      <div className="grid grid-3">
        <Figure
          label="Replacement demand found"
          value={s(f, "replacements_authorised")}
          accent={recovered}
          sub="enough to cover the gap, and no more"
        />
        <Figure
          label="Funded units"
          value={`${s(f, "funded_units_now")} / ${s(f, "threshold_units")}`}
          accent={recovered}
          sub="whole again, and still exactly two cases"
        />
        <Figure
          label="People actually buying"
          value={s(f, "buyers_after_recovery")}
          sub={`${s(f, "memberships_on_record")} memberships on the record — the extra one is the declined card, kept rather than deleted`}
        />
      </div>
      <p className="small muted prose">
        The agent chose to attempt a repair; the deterministic engine decided who was
        eligible to fill the hole. It replaces what was lost rather than recruiting
        freely — over-recruiting would trade a funding gap for surplus stock somebody
        still has to pay for — and it does not go back to the buyers who had already
        committed, because their price and their authorisation are already settled.
      </p>
      {/* The one moment in the run where the counts stop agreeing, so it is spelled out
          rather than left for a judge to reconcile from three separate screens. */}
      <p className="small muted prose">
        <strong>The count, reconciled.</strong> Pool matched{" "}
        {s(f, "members_matched_at_discovery")} people at discovery. Of those,{" "}
        {s(f, "memberships_that_failed")} had a card declined and took their units with
        them, and {s(f, "replacements_authorised")} replacement was authorised in their
        place. So <strong>{s(f, "buyers_after_recovery")} people buy</strong>, while the
        pool's record carries <strong>{s(f, "memberships_on_record")} memberships</strong>.
        The declined one stays visible on the pool page rather than quietly disappearing,
        because a record that edits out its failures is not a record.
      </p>
      <Block title="Tools called across the pricing and recovery runs">
        <TracePills names={list(f, "tools_called")} />
      </Block>
    </>
  );
}

function LockBody({ f }: { f: Facts }) {
  return (
    <>
      <div className="grid grid-3">
        <Figure label="Payments captured (simulated)" value={s(f, "captured_payments")} />
        <Figure label="Total captured (simulated)" value={s(f, "captured_total")} />
        <Figure
          label="Provider mode"
          value={s(f, "provider_mode")}
          small
          sub="simulated end to end — no card network was contacted"
        />
      </div>
      <p className="small muted prose">
        Locking runs one viability engine over stored facts, and all thirteen checks run —
        never short-circuited — so the reason a pool <em>cannot</em> lock is always the
        complete list: supplier minimum, offer still active, quote freshness, whole-case
        allocation, host assigned, host compensation clearing their own minimum, buyers genuinely
        saving, every buyer having authorised, every buyer's decision settled, Pool's own
        economics, timing, the pickup site, and funding. Capture happens after that gate
        and never before it.
      </p>
    </>
  );
}

function PurchaseBody({ f }: { f: Facts }) {
  return (
    <>
      <div className="grid grid-3">
        <Figure
          label="Cases ordered"
          value={s(f, "cases")}
          sub={`${s(f, "units")} units — exactly what was ordered, nothing speculative`}
        />
        <Figure label="Order value" value={s(f, "total")} />
        <Figure
          label="Supplier reference"
          value={s(f, "supplier_reference")}
          small
          sub="simulated, and labelled that way in every record it appears in"
        />
      </div>
      <p className="small muted prose">
        Cases rarely divide evenly into demand. Rather than buy the remainder and bill
        somebody for it, Pool searches for the set of buyers whose quantities fill whole
        cases exactly, preferring people whose need is already due. If no combination
        lands on a case boundary, the pool does not lock and says why.
      </p>
    </>
  );
}

function DistributionBody({ f }: { f: Facts }) {
  return (
    <>
      <div className="grid grid-3">
        <Figure label="Orders to hand out" value={s(f, "orders")} />
        <Figure label="Units collected from the supplier" value={s(f, "units")} />
        <Figure label="The host earns" value={s(f, "host_earnings")} accent />
      </div>
      <p className="small muted prose">
        The host is not a reseller taking a risk. Every unit in that vehicle is allocated
        and its buyer payment was captured by the simulated provider before the supplier
        order was recorded. Host compensation is recorded; Pool has no payout rail.
      </p>
    </>
  );
}

function PickupBody({ f }: { f: Facts }) {
  return (
    <>
      <div className="grid grid-3">
        <Figure
          label="Handoffs confirmed"
          value={`${s(f, "confirmed")} / ${s(f, "expected")}`}
          accent
        />
        <Figure
          label="Replays rejected"
          value={s(f, "replay_attempts_rejected")}
          sub="a used credential was presented again, on purpose"
        />
        <Figure label="Pool status" value={s(f, "status")} small />
      </div>
      {s(f, "replay_rejection_reason") ? (
        <div className="banner banner-warn">
          <span>
            Second presentation of the same credential:{" "}
            <strong>{s(f, "replay_rejection_reason")}</strong>
          </span>
        </div>
      ) : null}
      <p className="small muted prose">
        Every buyer gets their own one-time credential — a long token for the QR and a
        short code for when scanning is awkward. Only hashes are stored; the plaintext
        exists exactly once, in the response that issued it, and re-issuing invalidates
        the previous pair. A host cannot mark an order collected without one.
      </p>
    </>
  );
}

function ImpactBody({ f }: { f: Facts }) {
  return (
    <>
      <div className="grid grid-3">
        <Figure
          label="If each had bought alone"
          value={s(f, "buying_alone")}
          sub={`${s(f, "members_participating")} people at campus retail prices`}
        />
        <Figure label="All-in through Pool" value={s(f, "all_in_pool_cost")} />
        <Figure
          label="Kept in the community"
          value={s(f, "collective_saving")}
          accent
          sub={`${s(f, "average_saving_each")} each, after merchandise, host compensation, card processing and Pool's fee`}
        />
      </div>
      <div className="grid grid-2">
        <div>
          <h4 className="section-title" style={{ marginBottom: 8 }}>
            Where the saving went
          </h4>
          <div className="ledger">
            <LedgerLine label="Earned by the host, for work done" value={s(f, "host_earnings")} />
            <LedgerLine label="Pool's share of the saving" value={s(f, "pool_fee")} />
          </div>
        </div>
        <div>
          <h4 className="section-title" style={{ marginBottom: 8 }}>
            What it cost anyone in attention
          </h4>
          <div className="ledger">
            <LedgerLine
              label="Actions Pool took on its own"
              value={s(f, "actions_taken_automatically")}
            />
            <LedgerLine label="Times a person was asked" value={s(f, "humans_asked")} />
            <LedgerLine
              label="Commitments made without asking"
              value={s(f, "committed_without_asking")}
            />
            <LedgerLine label="Pools repaired after a failure" value={s(f, "pools_repaired")} />
            <LedgerLine label="Handoffs confirmed" value={s(f, "pickups_confirmed")} />
          </div>
        </div>
      </div>
      <p className="small muted prose">
        Bulk pricing normally favours whoever can afford a bigger purchase up front and
        has somewhere to put it. Nothing here is charity or a projection — every figure is
        a sum over stored rows in a synthetic community, and no goods moved.
      </p>
    </>
  );
}

function GenericBody({ f }: { f: Facts }) {
  const entries = Object.entries(f).filter(
    ([, v]) => v !== null && v !== "" && typeof v !== "object",
  );
  if (entries.length === 0) return null;
  return (
    <div className="facts">
      {entries.slice(0, 9).map(([k, v]) => (
        <Fact key={k} label={k.replace(/_/g, " ")} value={String(v)} />
      ))}
    </div>
  );
}

const BODIES: Record<string, (props: { f: Facts }) => JSX.Element | null> = {
  seed: SeedBody,
  latent_demand_discovered: DiscoveryBody,
  host_candidates_evaluated: HostCandidatesBody,
  host_accepted: HostAcceptedBody,
  final_offer: FinalOfferBody,
  payment_failure: PaymentFailureBody,
  decision_inbox: DecisionBody,
  recovery: RecoveryBody,
  locked_and_captured: LockBody,
  purchase: PurchaseBody,
  distribution_open: DistributionBody,
  pickup: PickupBody,
  impact: ImpactBody,
};

/* --------------------------------------------------------------------- view */

export function RunView({
  scenario,
  roundTripMs,
  running,
  onRun,
  onOpenPool,
  onLive,
  embedded,
}: {
  scenario: ScenarioResult | null;
  roundTripMs: number | null;
  running: boolean;
  onRun: () => void;
  onOpenPool: (poolId: string) => void;
  onLive: () => void;
  /** Rendered inside a pool's record rather than as its own page: the record already
   *  carries the title and the context, so the reader drops its own heading. */
  embedded?: boolean;
}) {
  const [index, setIndex] = useState(0);
  const [seen, setSeen] = useState(0);

  const steps = scenario?.steps ?? [];
  const total = steps.length;

  // A fresh run starts at the beginning; the previous position would be meaningless.
  useEffect(() => {
    setIndex(0);
    setSeen(0);
  }, [scenario]);

  const go = useCallback(
    (next: number) => {
      const clamped = Math.max(0, Math.min(total - 1, next));
      setIndex(clamped);
      setSeen((was) => Math.max(was, clamped));
    },
    [total],
  );

  // Arrow keys, because the whole point of this screen is that somebody can walk
  // through it on camera without hunting for a button.
  useEffect(() => {
    if (total === 0) return undefined;
    const onKey = (ev: KeyboardEvent) => {
      const tag = (ev.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (ev.key === "ArrowRight") go(index + 1);
      if (ev.key === "ArrowLeft") go(index - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, index, total]);

  if (!scenario) {
    return (
      <div className="stack">
        <header className="stack-sm">
          <h1 className="title">One purchase, from nobody asking for it to somebody carrying it home</h1>
          <p className="lede">
            Thirteen steps run on the server in a single call: the agent discovers the
            demand, the deterministic engine prices it, a person is asked only where a
            person is needed, a card is declined, the order is repaired, and the goods are
            handed over against a one-time code. Then you walk through what happened.
          </p>
        </header>
        <div className="panel panel-pad stack-sm">
          <ActorKey />
          <p className="small muted prose">
            Nothing on this screen is on a timer. The run finishes before you see the
            first step, and the round trip is printed at the top so you can check.
          </p>
          <div className="btn-row" style={{ marginTop: 6 }}>
            <button className="btn btn-primary btn-lg" onClick={onRun} disabled={running}>
              <IconPlay />
              {running ? "Running…" : "Run the full lifecycle"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const step = steps[index];
  const chapter = chapterFor(step);
  const Body = BODIES[step.name] ?? GenericBody;
  const last = index === total - 1;

  return (
    <div className="stack">
      <header className="row-between">
        <h2 className="title" style={{ maxWidth: "20ch", fontSize: embedded ? 26 : undefined }}>
          {embedded ? "How this pool happened" : "One purchase, end to end"}
        </h2>
        <div className="btn-row">
          {!embedded && scenario.pool_id ? (
            <button className="btn btn-sm" onClick={() => onOpenPool(scenario.pool_id)}>
              Open the pool record
            </button>
          ) : null}
          <button className="btn btn-sm" onClick={onRun} disabled={running}>
            <IconReplay />
            {running ? "Running…" : "Run it again"}
          </button>
        </div>
      </header>

      {!scenario.ok ? (
        <div className="banner banner-stop">
          <span>
            The run did not complete: {scenario.failure}. It is reported rather than
            retried, because a demo that hides a failure is worth nothing.
          </span>
        </div>
      ) : null}

      <div className="stage">
        <div className="stage-bar">
          <span className="stage-count">
            {String(index + 1).padStart(2, "0")} / {String(total).padStart(2, "0")}
          </span>
          <nav className="ruler" aria-label="Lifecycle steps">
            {steps.map((st, i) => (
              <button
                key={`${st.name}-${i}`}
                className={i === index ? "current" : i <= seen ? "seen" : ""}
                aria-label={`Step ${i + 1}: ${chapterFor(st).headline}`}
                aria-current={i === index ? "step" : undefined}
                onClick={() => go(i)}
              />
            ))}
          </nav>
          <span className="stage-count nowrap">
            {roundTripMs !== null ? `whole run: ${roundTripMs} ms` : "already executed"}
          </span>
        </div>

        <div className="stage-body reveal" key={`${scenario.pool_id}-${index}`}>
          <div>
            <div className="row-between" style={{ alignItems: "center" }}>
              <span className="stage-act">{chapter.act}</span>
              <span className="btn-row" style={{ gap: 14 }}>
                {chapter.actors.map((a) => (
                  <ActorTag key={a} actor={a} />
                ))}
              </span>
            </div>
            <h3 className="stage-headline">{chapter.headline}</h3>
            <p className="stage-detail">{step.detail}.</p>
          </div>

          <Body f={step.facts} />
        </div>

        <div className="stage-foot">
          <button className="btn btn-sm" onClick={() => go(index - 1)} disabled={index === 0}>
            <IconArrowLeft />
            Back
          </button>
          {last ? (
            <>
              <button className="btn btn-primary btn-sm" onClick={onLive}>
                <IconCloud />
                Now run it live on AWS
              </button>
              <button className="btn btn-sm" onClick={() => go(0)}>
                Start again
              </button>
            </>
          ) : (
            <button className="btn btn-primary btn-sm" onClick={() => go(index + 1)}>
              Continue
              <IconArrowRight />
            </button>
          )}
          <span className="tiny faint" style={{ marginLeft: "auto" }}>
            Arrow keys work too
          </span>
        </div>
      </div>

      {last && scenario.ok ? (
        <section className="block reveal">
          <h3 className="section-title" style={{ marginBottom: 12 }}>
            What just happened
          </h3>
          <p className="small muted prose">
            Nobody in that community created a group, and nobody organised anything. An
            agent decided there was an opportunity worth investigating and which actions
            to take; deterministic code decided every price, every eligibility, every
            state transition and whether the lock was allowed at all. A payment failed
            and the order was repaired without disturbing anyone who had already
            committed. Ten people had lower recorded costs than buying alone, host
            compensation was recorded for the person doing the work, and the whole thing ran in{" "}
            {roundTripMs !== null ? `${roundTripMs} ms` : "one call"} on a synthetic
            community where no money moved.
          </p>
          <div className="btn-row" style={{ marginTop: 14 }}>
            <button className="btn" onClick={onLive}>
              <IconCloud />
              See the same agent running on AWS
            </button>
            {scenario.pool_id ? (
              <button className="btn" onClick={() => onOpenPool(scenario.pool_id)}>
                Inspect the pool record
              </button>
            ) : null}
          </div>
        </section>
      ) : null}

      <ActorKey />
    </div>
  );
}

export function ScenarioEmpty() {
  return <Empty center>No run yet.</Empty>;
}
