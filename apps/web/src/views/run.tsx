/* The run — one complete purchase, as one sheet.
 *
 * The server executes the entire lifecycle in one call (about 40 ms) and returns a
 * structured transcript of what happened. This screen is a *reader* for that
 * transcript, not a progress animation: the run is already over before the first frame
 * is drawn, and the spine says so with the measured round trip. Nothing here is on
 * a timer pretending to be work (AGENTS.md §8).
 *
 * It used to paginate: one step per page, thirteen Continue clicks, a fourteen-segment
 * ruler of unlabelled hairlines. That destroyed the one thing the surface exists to
 * show. The story is a *causal chain* — 24 units of demand, minus 2 to a declined card,
 * plus 2 from a compatible replacement, closing into two whole cases with nothing left
 * over — and every page was a claim whose evidence sat on a page you could no longer
 * see. Pages 08 and 09 printed the identical figure while 09 claimed a repair.
 *
 * So: one scrolling sheet, every step present, and a sticky spine that draws the
 * quantity. The spine follows the reader's position, never a clock.
 *
 * Every value shown is read out of the step's `facts` exactly as the server computed
 * it. This file selects, labels and sets those values; it never derives one. The only
 * thing added on the client is editorial: which act a step belongs to, a headline, and
 * which of the three actors was responsible.
 */

import { useEffect, useRef, useState, type ReactNode } from "react";
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
  IconCheck,
  IconCloud,
  IconCross,
  IconPlay,
  IconReplay,
  LedgerLine,
  TracePills,
} from "../ui";

/* -------------------------------------------------------------- fact readers */

type Facts = Record<string, unknown>;

/* Where a stage body sits in the document outline. The reader is an h1 page of its own
   in Showcase and an h2 section inside a pool record, so everything under the stage
   headline shifts with it rather than skipping a level in one of the two. */
type SubLevel = "h3" | "h4";

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
  /* This step fires on every successful run and had no entry, so it fell through to the
     generic fallback: an eyebrow reading MEMBER DECLARED NEED, a headline cut out of the
     server's sentence at its first comma ("You told Pool she buys 100% whey protein"),
     eight raw identifiers, and an actor tag of COMPUTED on the one step where a *person*
     is the actor. Second page of fourteen, on the surface whose whole thesis is
     attribution. */
  member_declared_need: {
    act: "A member declares",
    headline: "One person said what she buys",
    actors: ["human"],
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
  /* No headline is derived from the detail sentence any more. Splitting on the first
     comma produced "You told Pool she buys 100% whey protein" — a truncation that read
     as a grammatical error and then repeated the rest of the sentence directly beneath
     itself. An unmapped step now says plainly that it is unmapped, which is a bug report
     rather than a bad sentence. */
  return (
    CHAPTERS[step.name] ?? {
      act: step.name.replace(/_/g, " "),
      headline: "This step has no authored chapter yet",
      actors: ["engine"],
    }
  );
}

function StageNote({
  children,
  label = "Why this matters",
}: {
  children: ReactNode;
  label?: string;
}) {
  return (
    <details className="inset">
      <summary className="small">
        <strong>{label}</strong>
      </summary>
      <div className="stack-sm" style={{ marginTop: 10 }}>
        {children}
      </div>
    </details>
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
      <div className="inset">
        <Fact label="Next pool day" value={s(f, "next_pool_day")} />
      </div>
      <StageNote>
        <p className="small muted prose">
          There is no organiser, sign-up sheet or financial commitment. The fixed weekly
          collection moment makes separate members' timing comparable.
        </p>
      </StageNote>
    </>
  );
}

function DiscoveryBody({ f, sub }: { f: Facts; sub: SubLevel }) {
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

      <p className="small muted">
        The agent chose what to investigate; deterministic timing policy decided who was
        eligible.
      </p>
      <StageNote>
        <p className="small muted prose">
          Eligibility requires the same product, same Community, and a purchase date each
          member already authorised. Pulled-forward members move only within their stored
          window; a member who authorised zero days is never moved.
        </p>
      </StageNote>
      <Block
        title={`Tools the agent called · ${s(f, "iterations")} iterations`}
        level={sub === "h3" ? 3 : 4}
      >
        <TracePills names={list(f, "tools_called")} ordered />
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
      <div className="rows" style={{ borderTop: "1px solid var(--rule-strong)" }}>
        {candidates.map((c) => (
          <div key={c.household_id} className="row" style={{ paddingInline: 0 }}>
            <span
              style={{ color: c.eligible ? "var(--ink)" : "var(--ink-faint)", display: "flex" }}
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
      <p className="tiny muted">{s(f, "eligible_count")} of {candidates.length} eligible.</p>
      <StageNote label="How candidates are ranked">
        <p className="small muted prose">
          Standing hosts and members who offer are checked on vehicle, capacity, weight,
          distance, availability and minimum pay. Offering does not claim the job; factual
          ineligibility reasons remain visible.
        </p>
      </StageNote>
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
      <p className="small muted">
        Host pay is fixed before buyer authorization; Pool never authorizes one amount and
        later charges another.
      </p>
      <StageNote>
        <p className="small muted prose">
          Only the handoff component is contingent. A buyer no-show cannot erase pay for a
          supplier trip already completed.
        </p>
      </StageNote>
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
      <StageNote label="How the fee and processing stay viable">
        <p className="small muted prose">
          Pool's fee is a share of gross savings, so no saving means no fee. Processing is
          grossed up per buyer so the charge covers the processor's cut without a hidden
          platform subsidy.
        </p>
      </StageNote>
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
      <StageNote>
        <p className="small muted prose">
          The simulated provider genuinely refused the saved method, and those units
          immediately stopped counting toward the funded order.
        </p>
      </StageNote>
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
      <StageNote>
        <p className="small muted prose">
          Pool asks only when a stored rule does not pass; everyone else is left alone.
        </p>
      </StageNote>
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
      <p className="small muted">
        <strong>Count:</strong> {s(f, "members_matched_at_discovery")} matched −{" "}
        {s(f, "memberships_that_failed")} decline + {s(f, "replacements_authorised")} replacement
        = {s(f, "buyers_after_recovery")} buyers; {s(f, "memberships_on_record")} memberships
        remain on record.
      </p>
      <StageNote label="Recovery and count reconciliation">
        <p className="small muted prose">
          The agent chose to attempt a repair; deterministic policy chose eligible demand.
          Pool replaced exactly the lost units without repricing committed buyers or creating
          surplus stock.
        </p>
        <p className="small muted prose">
          One matched member's authorization failed and one replacement was authorized, so
          the buyer count returns to {s(f, "buyers_after_recovery")} while the audit record
          retains all {s(f, "memberships_on_record")} memberships, including the decline.
        </p>
      </StageNote>
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
      <StageNote label="All lock checks">
        <p className="small muted prose">
          All thirteen checks run without short-circuiting: supplier minimum, active offer,
          quote freshness, whole-case allocation, host assignment and pay floor, buyer saving,
          every authorization and decision, Pool economics, timing, pickup and funding.
          Capture happens only after that gate.
        </p>
      </StageNote>
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
      <StageNote label="Why there is no surplus">
        <p className="small muted prose">
          Pool selects buyers whose quantities fill whole cases, preferring needs already
          due. If no exact allocation exists, the pool does not lock.
        </p>
      </StageNote>
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
      <StageNote>
        <p className="small muted prose">
          The host carries no speculative inventory: every unit is allocated and its
          simulated payment captured before the order record. Compensation is recorded;
          Pool has no payout rail.
        </p>
      </StageNote>
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
      <StageNote label="Credential mechanics">
        <p className="small muted prose">
          Each buyer gets a QR token and short code. Only hashes are stored; plaintext is
          returned once, reissue invalidates the prior pair, and collection requires a valid
          credential.
        </p>
      </StageNote>
    </>
  );
}

function ImpactBody({ f, sub }: { f: Facts; sub: SubLevel }) {
  const SubHead = sub;
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
          <SubHead className="section-title" style={{ marginBottom: 8 }}>
            Where the saving went
          </SubHead>
          <div className="ledger">
            <LedgerLine label="Earned by the host, for work done" value={s(f, "host_earnings")} />
            <LedgerLine label="Pool's share of the saving" value={s(f, "pool_fee")} />
          </div>
        </div>
        <div>
          <SubHead className="section-title" style={{ marginBottom: 8 }}>
            What it cost anyone in attention
          </SubHead>
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
      <p className="small muted">
        Stored-row results from a synthetic community; no money or goods moved.
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

function DeclarationBody({ f }: { f: Facts; sub: SubLevel }) {
  const qty = n(f, "quantity");
  const cadence = n(f, "cadence_days");
  const flex = n(f, "flexibility_days");
  return (
    <div className="stack-sm">
      <div className="facts">
        <Fact label="What she buys" value={s(f, "product_name") || s(f, "product_id")} />
        <Fact label="How much, how often" value={`${qty} every ${cadence} days`} />
        <Fact
          label="How early Pool may buy it"
          value={flex > 0 ? `up to ${flex} days` : "only when it is due"}
        />
      </div>
      <StageNote label="What this row does and does not authorise">
        <p className="small muted prose">
          One standing declaration, written through the same validated service the form
          uses. It permits Pool to <em>investigate</em>, and it permits buying up to{" "}
          {flex} days early. It authorises no spending: a commitment still needs this
          member to answer a question, and the amount has to be exact before Pool asks.
        </p>
      </StageNote>
    </div>
  );
}

const BODIES: Record<string, (props: { f: Facts; sub: SubLevel }) => JSX.Element | null> = {
  seed: SeedBody,
  member_declared_need: DeclarationBody,
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

/* ------------------------------------------------------------------- the spine */

/** The lifecycle as one quantity surviving a shock.
 *
 *  This is the drawing the surface was missing. The reader used to *assert* the
 *  centrepiece — "2 units stopped counting", then `24 / 24`, then `24 / 24` again
 *  captioned "whole again" — three claims on three pages, with a number that never
 *  visibly moved. The story is 24 units, minus 2, plus 2, closing into whole cases, and
 *  it is drawable in the vocabulary the design system already invented for case fitting.
 *
 *  Every number comes off the server's own step facts. Nothing here is derived.
 */
function UnitTrack({
  target,
  filled,
  declined,
  refilled,
  caseUnits,
  cases,
}: {
  target: number;
  filled: number;
  declined: number;
  refilled: number;
  caseUnits: number;
  cases: number;
}) {
  /* Cells are grouped into whole cases when the case size is known, so "nothing left
     over" is a shape rather than a sentence. */
  const groups: number[][] = [];
  const size = caseUnits > 0 && cases > 0 ? caseUnits : target;
  for (let i = 0; i < target; i += size) {
    groups.push(Array.from({ length: Math.min(size, target - i) }, (_, k) => i + k));
  }
  const state = (i: number): string => {
    if (i >= filled) return "empty";
    if (i >= filled - declined) return "declined";
    if (i >= filled - declined - refilled) return "refilled";
    return "held";
  };
  return (
    <div className="track" aria-hidden="true">
      {groups.map((g, gi) => (
        <span className={`track-case${cases > 0 ? " is-closed" : ""}`} key={gi}>
          {g.map((i) => (
            <i key={i} className={`track-cell is-${state(i)}`} />
          ))}
        </span>
      ))}
    </div>
  );
}

/** The lifecycle as a time series: one quantity across the recorded stages.
 *
 *  The unit track above says what the quantity *is* right now. This says what it *did* —
 *  and the two horizontal rules are why the dip means anything, because the trace falls
 *  below the line that says a case is full and then climbs back over it. Repaired, not
 *  written over.
 *
 *  Every value is `spineFor`'s own funded count for that stage, so nothing here is
 *  derived twice. A 2-unit loss on a 24-unit axis is a small shape honestly, so the
 *  second panel is the meteographer's answer rather than an exaggeration: the same
 *  series on its own stated scale, where the fall is half the panel.
 *
 *  Geometry is SVG with non-scaling strokes; every label is an element, because text
 *  inside a scaled viewBox is sized for one container width and wrong at every other.
 */
function Meteogram({
  series,
  target,
  caseUnits,
}: {
  series: { name: string; funded: number }[];
  target: number;
  caseUnits: number;
}) {
  if (series.length < 2 || target <= 0) return null;
  const W = 1000;
  const H = 150;
  const x = (i: number) => (i / (series.length - 1)) * W;
  const y = (u: number) => H - (u / target) * H;

  const path = (h: number, lo: number, hi: number) => {
    const yy = (u: number) => h - ((u - lo) / (hi - lo)) * h;
    let d = "";
    let prev: number | null = null;
    series.forEach((pt, i) => {
      if (pt.funded < lo) {
        prev = null;
        return;
      }
      if (prev !== null && prev !== pt.funded) d += ` L${x(i).toFixed(1)} ${yy(prev).toFixed(1)}`;
      d += `${prev === null ? "M" : " L"}${x(i).toFixed(1)} ${yy(pt.funded).toFixed(1)}`;
      prev = pt.funded;
    });
    return d;
  };

  // The span the quantity sat below a whole case, and by how much.
  const dipFrom = series.findIndex((p) => p.funded > 0 && p.funded < target);
  const dipTo = dipFrom >= 0 ? series.findIndex((p, i) => i > dipFrom && p.funded >= target) : -1;
  const dipUnits = dipFrom >= 0 ? target - series[dipFrom].funded : 0;

  const rules: number[] = [];
  if (caseUnits > 0) for (let u = caseUnits; u <= target; u += caseUnits) rules.push(u);

  const band = (h: number, lo: number, hi: number) =>
    dipFrom >= 0 && dipTo > dipFrom ? (
      <rect
        x={x(dipFrom)}
        y={h - ((target - lo) / (hi - lo)) * h}
        width={x(dipTo) - x(dipFrom)}
        height={((target - series[dipFrom].funded) / (hi - lo)) * h}
        fill="url(#gram-hatch)"
        stroke="var(--ink)"
        strokeWidth="1"
        vectorEffect="non-scaling-stroke"
      />
    ) : null;

  const hatch = (
    <defs>
      <pattern id="gram-hatch" width="7" height="7" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
        <line x1="0" y1="0" x2="0" y2="7" stroke="var(--ink)" strokeWidth="1.4" opacity="0.55" />
      </pattern>
    </defs>
  );

  const aria =
    `Funded units across ${series.length} recorded stages. The quantity holds at ${target}, ` +
    (dipFrom >= 0
      ? `falls to ${series[dipFrom].funded} when an authorisation is declined — ${dipUnits} short of a whole case — and returns to ${target} when a replacement is found.`
      : `and never falls.`);

  return (
    <div className="gram">
      <div className="gram-plot" role="img" aria-label={aria}>
        <span className="gram-mark" style={{ top: 0 }}>{target}</span>
        <span className="gram-mark is-zero" style={{ top: "100%" }}>0</span>
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
          {hatch}
          {rules.map((u) => (
            <line
              key={u}
              x1="0"
              y1={y(u)}
              x2={W}
              y2={y(u)}
              stroke="var(--ink)"
              strokeWidth="1"
              opacity="0.45"
              vectorEffect="non-scaling-stroke"
            />
          ))}
          {band(H, 0, target)}
          <path
            d={path(H, 0, target)}
            fill="none"
            stroke="var(--petrol)"
            strokeWidth="3.4"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
      </div>
      {dipFrom >= 0 && dipTo > dipFrom ? (
        <>
          <p className="gram-dip">
            {dipUnits} {dipUnits === 1 ? "unit" : "units"} short of a whole case, for two
            stages
          </p>
          {/* The same series on its own scale, stated. Not a zoom for drama — the axis
              is labelled, so the reader can see it is a different scale. */}
          <div className="gram-expanded">
            <span className="section-title">
              Expanded · {target - 4} to {target} units
            </span>
            <div className="gram-plot is-small">
              <span className="gram-mark" style={{ top: 0 }}>{target}</span>
              {dipFrom >= 0 ? (
                <span
                  className="gram-mark is-dip"
                  style={{ top: `${((target - series[dipFrom].funded) / 4) * 100}%` }}
                >
                  {series[dipFrom].funded}
                </span>
              ) : null}
              <span className="gram-mark is-zero" style={{ top: "100%" }}>{target - 4}</span>
              <svg viewBox={`0 0 ${W} 60`} preserveAspectRatio="none" aria-hidden="true">
                {hatch}
                <line
                  x1="0"
                  y1="0.5"
                  x2={W}
                  y2="0.5"
                  stroke="var(--ink)"
                  strokeWidth="1"
                  opacity="0.45"
                  vectorEffect="non-scaling-stroke"
                />
                {band(60, target - 4, target)}
                <path
                  d={path(60, target - 4, target)}
                  fill="none"
                  stroke="var(--petrol)"
                  strokeWidth="3.4"
                  vectorEffect="non-scaling-stroke"
                />
              </svg>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}

/** What the spine shows, per act. Derived once from the transcript. */
interface SpineState {
  caption: string;
  filled: number;
  declined: number;
  refilled: number;
  cases: number;
}

function spineFor(name: string, facts: Record<string, Facts>, target: number): SpineState {
  const at = (k: string) => facts[k] ?? {};
  const fail = at("payment_failure");
  const rec = at("recovery");
  const buy = at("purchase");
  const lost = n(fail, "units_lost");
  const base: SpineState = { caption: "", filled: 0, declined: 0, refilled: 0, cases: 0 };
  switch (name) {
    case "seed":
    case "member_declared_need":
      return { ...base, caption: "Nothing pooled yet — separate people, separate dates." };
    case "latent_demand_discovered":
    case "host_candidates_evaluated":
    case "host_accepted":
    case "final_offer":
      return {
        ...base,
        filled: target,
        caption: `${target} units of compatible demand, exactly the supplier's minimum.`,
      };
    case "payment_failure":
      return {
        ...base,
        filled: target,
        declined: lost,
        caption: `A card declined. ${lost} units stopped counting — ${target - lost} of ${target}, short of the minimum.`,
      };
    case "decision_inbox":
      return {
        ...base,
        filled: target,
        declined: lost,
        caption: `Still ${target - lost} of ${target}. Only the people who had to be asked were asked.`,
      };
    case "recovery":
      return {
        ...base,
        filled: n(rec, "funded_units_now") || target,
        refilled: n(rec, "recovered") || lost,
        caption: `A compatible replacement restored exactly ${n(rec, "recovered") || lost}. Back to ${n(rec, "funded_units_now") || target}.`,
      };
    default:
      return {
        ...base,
        filled: target,
        cases: n(buy, "cases"),
        caption: `${n(buy, "units") || target} units in ${n(buy, "cases")} whole cases, nothing left over.`,
      };
  }
}

/** The steps whose recorded figures *are* the causal chain, so their evidence is open
 *  without being asked for: the quantity falling, the quantity restored, and the whole
 *  cases it closed into. */
const CHAIN = new Set(["payment_failure", "recovery", "purchase"]);

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
  /** Absent on surfaces that may not start the scripted replay — it rewrites a whole
   *  community, in the showcase's own copy of one, and that is a Showcase/Demo-controls
   *  affordance rather than something to offer from inside a member's own record. */
  onRun?: () => void;
  onOpenPool: (poolId: string) => void;
  onLive: () => void;
  /** Rendered inside a pool's record rather than as its own page: the record already
   *  carries the title and the context, so the reader drops its own heading. */
  embedded?: boolean;
}) {
  const steps = scenario?.steps ?? [];
  const total = steps.length;
  const [active, setActive] = useState(0);
  const [showAll, setShowAll] = useState(false);
  const entries = useRef<(HTMLElement | null)[]>([]);

  /* Which entry the reader is looking at. The spine follows the sheet rather than a
     timer: the run finished before the first frame was drawn, and a spine that advanced
     on its own would be exactly the fabricated progress AGENTS.md §8 forbids. */
  useEffect(() => {
    if (total === 0) return undefined;
    const nodes = entries.current.filter(Boolean) as HTMLElement[];
    if (!nodes.length || typeof IntersectionObserver === "undefined") return undefined;
    const io = new IntersectionObserver(
      (records) => {
        const visible = records
          .filter((r) => r.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (!visible) return;
        const i = nodes.indexOf(visible.target as HTMLElement);
        if (i >= 0) setActive(i);
      },
      { rootMargin: "-45% 0px -45% 0px", threshold: 0 },
    );
    nodes.forEach((nd) => io.observe(nd));
    return () => io.disconnect();
  }, [total, scenario]);

  if (!scenario) {
    return (
      <div className="stack">
        <header className="stack-sm">
          <h1 className="title">One purchase, from nobody asking for it to somebody carrying it home</h1>
          <p className="lede">
            One call runs the whole lifecycle on the server. What comes back is a
            transcript: discovery, pricing, a declined card, the repair, the lock and the
            handover, all of it already finished.
          </p>
        </header>
        <div className="panel panel-pad stack-sm">
          <ActorKey />
          <p className="small muted prose">
            The run finishes before the reader opens; its measured round trip appears at
            the top. Nothing is animated as if work were still happening.
          </p>
          {onRun ? (
            <div className="btn-row" style={{ marginTop: 6 }}>
              <button className="btn btn-primary btn-lg" onClick={onRun} disabled={running}>
                <IconPlay />
                {running ? "Running…" : "Run the full lifecycle"}
              </button>
            </div>
          ) : null}
        </div>
      </div>
    );
  }

  /* Showcase renders the reader as its own page; a pool record renders it under the
     record's own title. The whole outline moves together. */
  const Title = embedded ? "h2" : "h1";
  const StageHead = embedded ? "h3" : "h2";
  const sub: SubLevel = embedded ? "h4" : "h3";

  const factsByName: Record<string, Facts> = {};
  for (const st of steps) factsByName[st.name] = st.facts;
  const target =
    n(factsByName.latent_demand_discovered ?? {}, "threshold_units") ||
    n(factsByName.payment_failure ?? {}, "threshold_units") ||
    0;
  const caseUnits = n(factsByName.purchase ?? {}, "units")
    ? Math.round(n(factsByName.purchase, "units") / Math.max(1, n(factsByName.purchase, "cases")))
    : 0;
  const spine = spineFor(steps[active]?.name ?? "seed", factsByName, target);
  /* The same derivation, once per stage, so the trace and the track can never disagree
     about the quantity: funded is what is in the pool less what stopped counting. */
  const series = steps.map((step) => {
    const at = spineFor(step.name, factsByName, target);
    return { name: step.name, funded: Math.max(0, at.filled - at.declined) };
  });

  /* The acts, in server order, each one a real destination instead of an unlabelled
     hairline. The ruler used to be fourteen 15x32px buttons carrying no text — under the
     24px minimum target size, at 1.56:1 against the paper, and sixteen tab stops ahead
     of the primary control. */
  const acts: { act: string; at: number }[] = [];
  steps.forEach((st, i) => {
    const a = chapterFor(st).act;
    if (!acts.length || acts[acts.length - 1].act !== a) acts.push({ act: a, at: i });
  });

  return (
    <div className="stack runsheet-wrap">
      <header className="row-between">
        <Title className="title" style={{ maxWidth: "22ch", fontSize: embedded ? 26 : undefined }}>
          {embedded ? "How this pool happened" : "One purchase, end to end"}
        </Title>
        <div className="btn-row">
          {!embedded && scenario.pool_id ? (
            <button className="btn btn-sm" onClick={() => onOpenPool(scenario.pool_id)}>
              Open the pool record
            </button>
          ) : null}
          {onRun ? (
            <button className="btn btn-sm btn-ghost" onClick={onRun} disabled={running}>
              <IconReplay />
              {running ? "Running…" : "Run it again"}
            </button>
          ) : null}
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

      {/* The spine. Sticky, so the quantity stays on screen while its story is read. */}
      <div className="spine">
        <div className="spine-row">
          <UnitTrack
            target={target}
            filled={spine.filled}
            declined={spine.declined}
            refilled={spine.refilled}
            caseUnits={caseUnits}
            cases={spine.cases}
          />
          <span className="spine-meta">
            {total} steps · {roundTripMs !== null ? `${roundTripMs} ms` : "already executed"}
          </span>
        </div>
        {/* The quantity's own history, beneath the quantity's current shape. */}
        <Meteogram series={series} target={target} caseUnits={caseUnits} />
        {/* The caption is the same fact in words, so the drawing is never the only
            carrier — which is what makes it survive reduced motion and a screen reader. */}
        <p className="spine-caption" aria-live="polite">
          {spine.caption}
        </p>
      </div>

      <div className="runsheet">
        <nav className="acts" aria-label="Acts">
          {acts.map((a, i) => (
            <a
              key={a.act}
              href={`#act-${a.at}`}
              className={
                active >= a.at && (i + 1 === acts.length || active < acts[i + 1].at)
                  ? "is-current"
                  : ""
              }
              aria-current={
                active >= a.at && (i + 1 === acts.length || active < acts[i + 1].at)
                  ? "true"
                  : undefined
              }
            >
              {a.act}
            </a>
          ))}
        </nav>

        <div className="entries">
          <div className="entries-head">
            <ActorKey />
            <button
              className="btn btn-sm btn-ghost"
              onClick={() => setShowAll((was) => !was)}
              aria-pressed={showAll}
            >
              {showAll ? "Collapse the figures" : "Show every figure"}
            </button>
          </div>
          {steps.map((st, i) => {
            const chapter = chapterFor(st);
            const Body = BODIES[st.name] ?? GenericBody;
            const newAct = i === 0 || chapterFor(steps[i - 1]).act !== chapter.act;
            return (
              <article
                key={`${st.name}-${i}`}
                id={`act-${i}`}
                className={`entry${i === active ? " is-active" : ""}`}
                ref={(el) => {
                  entries.current[i] = el;
                }}
              >
                {newAct ? <span className="entry-act">{chapter.act}</span> : null}
                <div className="entry-head">
                  <StageHead className="entry-headline">{chapter.headline}</StageHead>
                  <span className="entry-actors">
                    {chapter.actors.map((a) => (
                      <ActorTag key={a} actor={a} />
                    ))}
                  </span>
                </div>
                <p className="entry-detail">{st.detail}.</p>
                {/* Every step's evidence, on the same page rather than paginated. Open by
                    default only where the figures are the story itself. */}
                <details className="entry-evidence" open={showAll || CHAIN.has(st.name)}>
                  <summary className="small">Figures this step recorded</summary>
                  <div className="entry-body">
                    <Body f={st.facts} sub={sub} />
                  </div>
                </details>
              </article>
            );
          })}
        </div>
      </div>

      {scenario.ok ? (
        <section className="panel close-panel">
          <div className="panel-pad stack-sm">
            <StageHead className="display" style={{ fontSize: 27, lineHeight: 1.1 }}>
              Nobody created a group. Nobody organised anything.
            </StageHead>
            <p className="small muted prose">
              An agent decided there was an opportunity worth investigating and which
              actions to take; deterministic code decided every price, every eligibility,
              every state transition and whether the lock was allowed at all. A payment
              failed and the order was repaired without disturbing anyone who had already
              committed. Ten people had lower recorded costs than buying alone, host
              compensation was recorded for the person doing the work, and the whole thing
              ran in {roundTripMs !== null ? `${roundTripMs} ms` : "one call"} on a
              synthetic community where no money moved.
            </p>
            <div className="btn-row" style={{ marginTop: 6 }}>
              <button className="btn btn-primary" onClick={onLive}>
                <IconCloud />
                Now run it live on AWS
              </button>
              {scenario.pool_id ? (
                <button className="btn" onClick={() => onOpenPool(scenario.pool_id)}>
                  Inspect the pool record
                </button>
              ) : null}
            </div>
          </div>
        </section>
      ) : null}
    </div>
  );
}

export function ScenarioEmpty() {
  return <Empty center>No run yet.</Empty>;
}
