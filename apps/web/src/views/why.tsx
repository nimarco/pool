/** Why this order? — and, underneath it, the proof.
 *
 *  One server read (`/api/needs/{id}/coordination`) behind two audiences. The member-facing
 *  half answers *what happened, and what has not happened*; the technical half answers
 *  *which provider, which tools, in what order, under what bounds*. They are the same
 *  stored rows at two levels of detail, which is the property that makes the second one
 *  evidence for the first rather than a parallel story told beside it.
 *
 *  **The words follow the provider the run recorded.** The public path executes the real
 *  Strands loop against a deterministic offline planner, so calling its iterations "model
 *  calls" would be contradicted by the provider and the zero token count printed beside
 *  them — see `vocabularyFor`.
 *
 *  **Nothing here is reconstructed from what the browser saw.** The old judge demo held its
 *  narrative in React state and lost it on reload; this component fetches, and a refresh
 *  re-reads the same rows. If the server has no event for a declaration, the honest answer
 *  is that Pool has not looked yet — not a blank screen and not an invented one.
 *
 *  Counts, never a roster. Which neighbour was excluded, and for what, is that member's
 *  business and not an answer to anybody else's question (AGENTS.md §4).
 */
import { useEffect, useState } from "react";
import { ClarificationProof, NeedCoordination, StrategyVerdict, api } from "../api";
import { Empty, Fact, IconArrowLeft } from "../ui";

/** The deterministic refusal codes, in the words a member would use.
 *
 *  A lookup rather than prose from the server: the codes are a closed set the domain
 *  owns, and translating them here keeps the API returning values instead of sentences.
 *  Anything unmapped falls back to the code itself, which is ugly and true. */
const BLOCKER_COPY: Record<string, string> = {
  not_cheaper: "the group would have paid more than buying alone",
  below_minimum: "not enough of the demand could be bought together",
  no_bulk_offer: "no supplier quotes this one in bulk",
  no_retail_baseline: "there is no shelf price to compare against",
  no_compatible_demand: "nobody else's preferences allow this one",
  quote_stale: "the supplier quote was too old to rely on",
  routing_unavailable: "travel times could not be established",
};

/** Why somebody else's demand could not join, in their terms rather than the schema's. */
const EXCLUSION_COPY: Record<string, string> = {
  exact_product_required: "asked for one specific product and this is not it",
  required_attribute_mismatch: "buy something this does not match — decaf, or ground",
  excluded_attribute_value: "ruled this kind of coffee out",
  attribute_unverified: "buy something Pool has not confirmed the details of",
  product_not_allowed: "listed the products they will accept, and this is not on it",
  outside_radius: "live too far from the pickup point",
  timing_not_eligible: "do not need any yet",
  already_in_pool: "are already in an order for this",
};

function blockerCopy(code: string): string {
  return BLOCKER_COPY[code] ?? code.replace(/_/g, " ");
}

/** The refusal as a chip, in two or three words.
 *
 *  A separate table from `BLOCKER_COPY` because it answers a different question. The
 *  sentence completes "…but {x}"; the chip is what the eye lands on before reading
 *  anything, and has to survive being read alone beside the numbers that caused it. */
const BLOCKER_CHIP: Record<string, string> = {
  not_cheaper: "Costs more",
  below_minimum: "Not enough demand",
  no_bulk_offer: "No bulk supplier",
  no_retail_baseline: "No price to compare",
  no_compatible_demand: "Nothing compatible",
  quote_stale: "Quote too old",
  routing_unavailable: "No route",
};

function blockerChip(code: string): string {
  return BLOCKER_CHIP[code] ?? "Not worth doing";
}

/** Pluralise the unit the member actually declared.
 *
 *  This used to be the literal string "bags" everywhere on this page, which is wrong for
 *  every declaration that is not coffee: the paper-towels refusal read "7 bags were
 *  available against a 48-bag minimum" beside a Home row that correctly said packs. The
 *  noun travels from the caller, which is the only place that knows it — the coordination
 *  payload carries quantities, not the word for them. */
function units(n: number, unit: string): string {
  return `${n} ${n === 1 ? unit : `${unit}s`}`;
}

/** What to call the thing that drove the loop, derived from the run's stored provider.
 *
 *  Not cosmetic. The public `/verify` run executes the real Strands loop against the
 *  **deterministic offline planner** — the same tools, the same bounds, the same guarded
 *  writes, and no model at all. Calling its iterations "model calls" beside a provider
 *  reading `offline` and a token count reading zero is a claim the same panel disproves
 *  two lines further down, and it is the sort of thing a sceptical reader is entitled to
 *  treat as evidence about everything else on the page.
 *
 *  So the vocabulary comes from `run.model_provider`, which is what the coordinator
 *  actually recorded (`agent/coordinator._build_model`). Where a word works for both —
 *  *control plane*, *chose* — it is preferred over a word that has to be switched.
 */
interface Vocabulary {
  /** The subject: what a reader should picture making the choices. */
  actor: string;
  /** The label above the iteration count. */
  iterations: string;
  /** The label above the token count. */
  tokens: string;
  /** Whether tokens were spendable at all on this path. */
  offline: boolean;
}

const OFFLINE: Vocabulary = {
  actor: "The offline planner",
  iterations: "Planner iterations",
  tokens: "Model tokens",
  offline: true,
};

const LIVE: Vocabulary = {
  actor: "The model",
  iterations: "Model iterations",
  tokens: "Tokens",
  offline: false,
};

function vocabularyFor(provider: string | undefined): Vocabulary {
  return provider === "offline" || provider === "" || provider === undefined
    ? OFFLINE
    : LIVE;
}

export function WhyThisOrder({
  needId,
  productName,
  unit,
  onBack,
}: {
  needId: string;
  /** What the member called it, for the heading. The server names the *bought* product. */
  productName: string;
  /** The singular noun this declaration is counted in — "bag", "pack", "tub". Passed by
   *  the caller because the coordination payload carries quantities and not the word for
   *  them, and a hardcoded "bags" is wrong on every row that is not coffee. */
  unit: string;
  onBack: () => void;
}) {
  const [data, setData] = useState<NeedCoordination | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [proof, setProof] = useState(false);

  useEffect(() => {
    let live = true;
    void api
      .needCoordination(needId)
      .then((d) => live && setData(d))
      .catch((e) => live && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      live = false;
    };
  }, [needId]);

  if (error) return <Empty>{error}</Empty>;
  if (!data) return <Empty>Loading…</Empty>;

  const order = data.order;
  const investigated = data.investigated ?? [];
  const considered = data.considered ?? [];
  const refused = investigated.filter((v) => !v.viable);
  const chosen = data.chosen ?? null;
  const exclusions = Object.entries(data.exclusion_codes ?? {}).filter(([, n]) => n > 0);
  /* How much demand stood behind each option before anything was costed, joined onto the
     verdict it produced. Two payload fields describing one option: the listing carries
     the headcount, the evaluation carries the arithmetic, and splitting them across two
     cards made the reader hold six numbers to compare two products. */
  const standingFor = new Map(considered.map((o) => [o.strategy_id, o]));
  /* Options the run listed but never costed. When every option was costed the verdicts
     below are a superset of the listing, and printing both is the same table twice. */
  const uncosted = considered.filter(
    (o) => !investigated.some((v) => v.strategy_id === o.strategy_id),
  );

  return (
    <div className="stack">
      <button className="btn btn-sm btn-ghost self-start" onClick={onBack}>
        <IconArrowLeft />
        Back
      </button>

      <header className="stack-sm">
        <h1 className="title">{order ? "Why this order?" : "Why not yet?"}</h1>
        <p className="small muted">
          {productName}
          {refused.length > 0 && chosen ? " · more demand isn't cheaper" : ""}
        </p>
      </header>

      {!data.event ? (
        <Empty>Pool has not looked at this one yet.</Empty>
      ) : (
        <>
          {/* An order this save did not form, but which the save put the member back
              into. Said first and said plainly: the sections below describe what *this*
              run did, which was correctly nothing, and without this the page would read
              as though the order on their Home screen had no cause. */}
          {order && !order.formed_by_this_run ? (
            <div className="banner">
              <span>
                <strong>Back in this order.</strong> Your rules allow {order.product}{" "}
                again. The reasoning below is the earlier run&apos;s.
              </span>
            </div>
          ) : null}

          {/* The comparison. What each option cost, side by side and in the same slots,
              so two products can be told apart without reading either of them.

              This replaced two cards that between them printed the demand behind an
              option, then a sentence saying none of it had a price yet, then the same
              option again with the price. The headcount now sits on the verdict it
              produced, which is the only place it was ever an argument. */}
          <section className="panel">
            <div className="panel-head">
              <h2>{order ? "What Pool worked out" : "What Pool found"}</h2>
            </div>
            <div className="panel-pad stack-sm">
              {investigated.length === 0 ? (
                <p className="small muted">
                  Nothing new to assemble — the order you are in already serves this.
                </p>
              ) : null}
              {investigated.map((verdict) => (
                <Verdict
                  key={verdict.evaluation_id}
                  verdict={verdict}
                  unit={unit}
                  standing={standingFor.get(verdict.strategy_id) ?? null}
                  selected={Boolean(chosen && chosen.strategy_id === verdict.strategy_id)}
                />
              ))}
              {uncosted.length > 0 ? (
                <p className="small muted">
                  {uncosted.length === 1 ? "One further option was" : `${uncosted.length} further options were`}{" "}
                  listed and not costed: {uncosted.map((o) => o.product).join(", ")}.
                </p>
              ) : null}
            </div>
          </section>

          {/* Who could not join, and what has not happened. Both load-bearing, both
              closed: a page that ends in four disclaimers every single time trains the
              reader to stop at the third card. Counts, never a roster. */}
          {exclusions.length > 0 ? (
            <details className="panel why-fold">
              <summary>
                <span>Who could not join</span>
                <span className="small muted">
                  {exclusions.reduce((n, [, c]) => n + c, 0)} people
                </span>
              </summary>
              <div className="panel-pad stack-sm">
                <ul className="why-exclusions">
                  {exclusions.map(([code, count]) => (
                    <li key={code}>
                      <strong>{count}</strong>{" "}
                      {count === 1 ? "person" : "people"}{" "}
                      {EXCLUSION_COPY[code] ?? code.replace(/_/g, " ")}
                    </li>
                  ))}
                </ul>
                <p className="small muted">No preferences were bent to make this work.</p>
              </div>
            </details>
          ) : null}

          <details className="panel why-fold">
            <summary>
              <span>Nothing has been charged, ordered or assigned</span>
            </summary>
            <div className="panel-pad">
              <ul className="why-not-yet">
                <li>No card has been charged, and none has been authorised.</li>
                <li>Nobody has agreed to collect and hand out the order yet.</li>
                {order ? (
                  <li>
                    The exact price comes later, once somebody has taken that job — the
                    figure above is an estimate.
                  </li>
                ) : null}
                <li>Nothing has been ordered from the supplier.</li>
              </ul>
            </div>
          </details>

          {/* 5. The proof, one layer down and closed by default. */}
          <section className="panel">
            <div className="panel-head">
              <h2>Technical proof for this run</h2>
              <span className="spacer" />
              <button
                className="btn btn-sm"
                onClick={() => setProof((p) => !p)}
                aria-expanded={proof}
              >
                {proof ? "Hide" : "Show"}
              </button>
            </div>
            {proof ? <Proof data={data} /> : null}
          </section>
        </>
      )}
    </div>
  );
}

/** One option and what it cost, as numbers in fixed slots.
 *
 *  This was a paragraph, and the paragraph was wrong. It opened
 *  "{matched} bags were available against a {minimum}-bag minimum, so there was plenty"
 *  on **every** refusal — including `below_minimum`, where the whole refusal is that
 *  there was not nearly enough. Seven packs against a minimum of forty-eight were
 *  described to the member as plenty, on the one screen whose job is an honest no.
 *
 *  The fix is structural rather than a better sentence. What is worth reading differs by
 *  blocker: a below-minimum refusal is a quantity pair, a not-cheaper refusal is a money
 *  pair, and everything else has no figures to show because none were reached. The slots
 *  say which is which, so the same two positions can be compared down a column without
 *  reading either row. */
function Verdict({
  verdict,
  unit,
  standing,
  selected,
}: {
  verdict: StrategyVerdict;
  unit: string;
  /** The listing row this verdict came from, for the headcount behind the demand. */
  standing: { compatible_declarations: number } | null;
  /** Whether this is the option the run actually formed an order from. */
  selected: boolean;
}) {
  /* A price pair is only shown when one was reached. `$0.00` is the payload's way of
     saying "never costed", and printing it beside a real baseline would read as free. */
  const priced = verdict.all_in_display !== "$0.00";
  const shortOfMinimum = verdict.matched_units < verdict.minimum_units;

  return (
    <div
      className={`why-verdict${verdict.viable ? " is-ok" : " is-no"}${
        selected ? " is-chosen" : ""
      }`}
    >
      <div className="why-verdict-head">
        <strong>{verdict.product}</strong>
        <span className={`chip ${verdict.viable ? "chip-ok" : "chip-warn"}`}>
          {verdict.viable
            ? selected
              ? `Saves ${verdict.net_savings_display}`
              : "Worth doing"
            : blockerChip(verdict.blocker_code)}
        </span>
        {/* Which one Pool actually took. The saving on the chip implied it and the green
            edge implied it, and between two cards a stranger reads in about two seconds
            neither of them says it. A viable option that was *not* taken shows "Worth
            doing" and no tag, which is the distinction this page exists to draw. */}
        {selected ? <span className="why-chosen">Chosen</span> : null}
      </div>

      <div className="stat-row">
        {/* Quantity first when quantity is the answer, money first when money is. */}
        {verdict.viable || !shortOfMinimum ? (
          <>
            <Figure
              label="together"
              value={priced ? verdict.all_in_display : units(verdict.matched_units, unit)}
            />
            <Figure
              label={priced ? "buying separately" : "supplier minimum"}
              value={
                priced
                  ? verdict.retail_baseline_display
                  : units(verdict.minimum_units, unit)
              }
            />
            {verdict.viable ? (
              <Figure
                label="you all save"
                value={verdict.net_savings_pct}
                tone="ok"
              />
            ) : null}
          </>
        ) : (
          <>
            <Figure label="declared" value={units(verdict.matched_units, unit)} />
            <Figure label="required" value={units(verdict.minimum_units, unit)} />
          </>
        )}
      </div>

      <p className="tiny faint">
        {verdict.viable
          ? `${units(verdict.selected_units, unit)} · ${verdict.cases} full ${
              verdict.cases === 1 ? "case" : "cases"
            } of ${verdict.case_units} · nothing left over`
          : standing
            ? `${units(verdict.matched_units, unit)} standing from ${standing.compatible_declarations} people — ${blockerCopy(verdict.blocker_code)}`
            : blockerCopy(verdict.blocker_code)}
      </p>
    </div>
  );
}

function Figure({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "ok";
}) {
  return (
    <div className={`stat${tone ? ` is-${tone}` : ""}`}>
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

/** The clarification plan submitted with this declaration revision.
 *
 *  Its own run, its own provider, its own budget — planning happens while somebody is
 *  still deciding and coordination happens after they have decided — so it gets its own
 *  vocabulary rather than borrowing the coordination run's. On the public path both are
 *  the offline planner; on a deployment configured for Bedrock either could be live, and
 *  the words follow whichever actually ran.
 *
 *  The plan is read by the id the coordination event froze when the declaration was
 *  saved, so this is the plan that came with *this* revision — not whichever plan is
 *  newest now. What the server checked when it stored the reference: this member, this
 *  product, this Community, and that these answers could have come from the questions
 *  this plan asked.
 */
function ClarificationProofBlock({ proof }: { proof: ClarificationProof }) {
  const words = vocabularyFor(proof.model_provider);
  const ran = Boolean(proof.run_id);
  return (
    <div className="stack-sm">
      <h3 className="small">What Pool decided to ask, before any of this</h3>
      <div className="facts">
        <Fact label="Plan" value={<code>{proof.plan_id}</code>} />
        <Fact label="Run" value={<code>{proof.run_id || "none"}</code>} />
        <Fact
          label="Provider"
          value={
            proof.model_id
              ? `${proof.model_provider} · ${proof.model_id}`
              : "not run in this workspace"
          }
        />
        <Fact
          label={words.tokens}
          value={`${proof.input_tokens} in · ${proof.output_tokens} out`}
        />
        {/* A superseded plan is still the right answer for an older revision, and saying
            so is the point: the world has moved since, and the record has not. */}
        <Fact label="Plan status" value={proof.status} />
      </div>
      <ul className="proof-evals">
        <li>
          <strong>Approved:</strong>{" "}
          {proof.offered.map((q) => (
            <code key={q}>{q} </code>
          ))}
        </li>
        <li>
          <strong>Asked, in this order:</strong>{" "}
          {proof.asked.length === 0 ? (
            <span className="muted">nothing</span>
          ) : (
            proof.asked.map((q) => <code key={q}>{q} </code>)
          )}
        </li>
      </ul>
      <p className="small muted">
        {ran ? (
          <>
            A separate, earlier run, with its own budget. {words.actor} selected which of
            the approved questions were worth asking and in what order — a subset of the
            list above it, and it cannot write one that is not on it.
          </>
        ) : (
          <>
            No planning run happened in this workspace, so every approved question was
            asked in the schema&apos;s own order.
          </>
        )}{" "}
        What each answer <em>means</em> was decided by nothing in this table: every answer
        maps to a fixed rule in <code>services/needs.policy_from_answers</code>, curated
        under{" "}
        <code>
          {proof.family} v{proof.schema_version}
        </code>
        .
      </p>
    </div>
  );
}

function Proof({ data }: { data: NeedCoordination }) {
  const run = data.run;
  const words = vocabularyFor(run?.model_provider);
  return (
    <div className="panel-pad stack-sm">
      {/* The five facts a sceptical reader is here for, before anything else. Everything
          below the fold in this panel is still present and still exact — what changed is
          that three paragraphs and eleven identifiers no longer stand between the reader
          and the outcome, the provider and the token count. */}
      <div className="facts">
        <Fact label="Outcome" value={run?.outcome ?? ""} />
        {/* Provider first among the rest, and never abbreviated away: it is what decides
            whether any of the words around it may say "model". */}
        <Fact label="Provider" value={`${run?.model_provider} · ${run?.model_id}`} />
        <Fact
          label={words.tokens}
          value={`${run?.input_tokens ?? 0} in · ${run?.output_tokens ?? 0} out`}
        />
        <Fact
          label={words.iterations}
          value={`${run?.iterations ?? 0} of ${run?.bounds.max_iterations ?? 0} allowed`}
        />
      </div>

      <div className="stack-sm">
        <h3 className="small">Tools called, in order</h3>
        <ol className="proof-tools">
          {(run?.tool_calls ?? []).map((call, i) => (
            <li key={`${call.name}-${i}`}>
              <code>{call.name}</code>
              {call.ok ? null : <span className="small muted"> — refused</span>}
            </li>
          ))}
        </ol>
      </div>

      <div className="stack-sm">
        <h3 className="small">Deterministic verdicts</h3>
        <ul className="proof-evals">
          {(data.investigated ?? []).map((v) => (
            <li key={v.evaluation_id}>
              {v.product} · <strong>{v.viable ? "viable" : v.blocker_code}</strong> ·
              matched {v.matched_units}/{v.minimum_units} · {v.cases}×{v.case_units} cases
              · surplus {v.surplus_units} · {v.net_savings_display} ({v.net_savings_pct})
            </li>
          ))}
        </ul>
      </div>

      {/* Identifiers, bounds and the three paragraphs that qualify them. Diagnostic
          value is unchanged — every field is still rendered and still copyable — but a
          judge reading the panel for the first time gets the verdict before the ledger. */}
      <details className="proof-more">
        <summary className="small">Identifiers, bounds and how to read this</summary>
        <div className="stack-sm" style={{ marginTop: 12 }}>
          <div className="facts">
            <Fact label="Coordination event" value={<code>{data.event?.event_id}</code>} />
            <Fact label="Run" value={<code>{run?.run_id}</code>} />
            <Fact label="Objective" value={run?.objective ?? ""} />
            <Fact label="Ended" value={run?.termination_reason ?? ""} />
            <Fact
              label="Options offered"
              value={`${(data.considered ?? []).length}, cap ${run?.bounds.max_strategy_listings ?? 0} listing`}
            />
            {/* Which run was shown the listing above. Named only when it is not this one,
                because "the listing this run received" is the ordinary case and labelling
                it every time would imply the two can drift apart more often than they do.
                The listing itself is stored as it was transmitted, so it is what that run
                saw rather than what the same options would say today. */}
            {data.evidence_run_id && data.evidence_run_id !== run?.run_id ? (
              <Fact label="Listing shown to" value={<code>{data.evidence_run_id}</code>} />
            ) : null}
            <Fact
              label="Options costed"
              value={`${(data.investigated ?? []).length} of ${run?.bounds.max_strategy_evaluations ?? 0} allowed`}
            />
            <Fact
              label="Orders formed"
              value={`${data.order ? 1 : 0} of ${run?.bounds.max_strategy_pool_creations ?? 0} allowed`}
            />
            <Fact label="Order" value={<code>{data.order?.pool_id ?? "none"}</code>} />
            <Fact
              label="Order formed by"
              value={
                data.order
                  ? data.order.formed_by_this_run
                    ? "this run"
                    : <code>{data.order.created_by_run}</code>
                  : "—"
              }
            />
          </div>

          <ul className="proof-evals">
            {(data.investigated ?? []).map((v) => (
              <li key={v.evaluation_id}>
                <code>{v.evaluation_id}</code> · {v.product}
              </li>
            ))}
          </ul>

          {words.offline ? (
            <p className="small muted">
              <strong>This run used the deterministic offline planner.</strong> It is the
              real Strands loop, the real tool surface and the real bounds, with a planner
              in place of a model — which is why the token counts above are zero and why
              you can reproduce this run exactly. No model was called and none could have
              been: the function serving this page has no permission to call one. Live
              model execution is a separate, explicitly requested action that goes through
              Bedrock AgentCore Runtime, and it records its own provider here when it is
              the one that ran.
            </p>
          ) : null}

          <p className="small muted">
            {words.actor} chose which option to investigate and moved on when the first was
            refused. It never computed a price, decided who was compatible, or supplied a
            member, a quantity or a supplier term — every one of those came from
            deterministic code, and the tool it calls to form an order takes two identifiers
            and nothing else.
          </p>
          <p className="small muted">
            The options above are stored as they were handed to that run, not looked up
            again now. The same option can be offered to a later run with different numbers
            behind it — somebody else declares, an order forms — and a record that re-read
            them today would be today&apos;s listing wearing an older date.
          </p>

          {data.clarification ? (
            <ClarificationProofBlock proof={data.clarification} />
          ) : null}

          <p className="small muted">
            Synthetic community, simulated payments, no supplier contacted. The software is
            real; the people and the money are not.
          </p>
        </div>
      </details>
    </div>
  );
}
