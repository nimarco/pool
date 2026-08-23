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
  onBack,
}: {
  needId: string;
  /** What the member called it, for the heading. The server names the *bought* product. */
  productName: string;
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

  return (
    <div className="stack">
      <button className="btn btn-sm btn-ghost self-start" onClick={onBack}>
        <IconArrowLeft />
        Back
      </button>

      <header className="stack-sm">
        <h1 className="title">{order ? "Why this order?" : "Why no order yet?"}</h1>
        <p className="lede">
          You said you buy {productName}. Pool looked for other people near you who buy
          something close enough, and worked out whether buying together was actually
          worth it.
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
            <section className="panel">
              <div className="panel-head">
                <h2>You are back in this order</h2>
              </div>
              <div className="panel-pad stack-sm">
                <p className="small">
                  Your rules allow <strong>{order.product}</strong> again, so Pool put you
                  back into the order it had taken you out of — the same one, not a new
                  one. It was worked out by an earlier run, and the reasoning below is
                  that run&apos;s.
                </p>
                <p className="small muted">
                  Nothing was charged and nothing was committed. Your place is provisional
                  and you will be asked before anything is.
                </p>
              </div>
            </section>
          ) : null}

          {/* 1. What Pool considered. Options, before any of them was costed. */}
          <section className="panel">
            <div className="panel-head">
              <h2>What Pool considered</h2>
            </div>
            <div className="panel-pad stack-sm">
              <p className="small">
                {considered.length === 0
                  ? "Nothing this time — the order you are in already served this, so there was nothing new to assemble."
                  : `Nobody buys the identical bag, so there was more than one order Pool could have assembled. It found ${considered.length}.`}
              </p>
              <ul className="why-options">
                {considered.map((option) => (
                  <li key={option.strategy_id}>
                    <strong>{option.product}</strong>
                    <span className="small muted">
                      {" "}
                      — {option.compatible_units} bags standing from{" "}
                      {option.compatible_declarations} people, against a supplier minimum of{" "}
                      {option.lowest_supplier_minimum_units}
                    </span>
                  </li>
                ))}
              </ul>
              {considered.length > 0 ? (
                <p className="small muted">
                  At this point none of them had a price. Clearing a supplier&apos;s
                  minimum is necessary and nowhere near enough.
                </p>
              ) : null}
            </div>
          </section>

          {/* 2. What was actually costed, and what each answer was. */}
          <section className="panel">
            <div className="panel-head">
              <h2>What Pool worked out</h2>
            </div>
            <div className="panel-pad stack-sm">
              {investigated.map((verdict) => (
                <Verdict key={verdict.evaluation_id} verdict={verdict} />
              ))}
              {refused.length > 0 && chosen ? (
                <p className="small muted">
                  The one with the most demand behind it is the one that did not work. That
                  only became clear after the full cost — fulfilment and card processing
                  included — was worked out.
                </p>
              ) : null}
            </div>
          </section>

          {/* 3. Who could not join, in aggregate. Never a roster. */}
          {exclusions.length > 0 ? (
            <section className="panel">
              <div className="panel-head">
                <h2>Who could not join</h2>
              </div>
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
                <p className="small muted">
                  Nobody&apos;s preferences were bent to make this work. Pool never widens
                  what somebody agreed to.
                </p>
              </div>
            </section>
          ) : null}

          {/* 4. What has NOT happened. Load-bearing, so it is a section rather than a note. */}
          <section className="panel">
            <div className="panel-head">
              <h2>What has not happened</h2>
            </div>
            <div className="panel-pad">
              <ul className="why-not-yet">
                <li>No card has been charged, and none has been authorised.</li>
                <li>Nobody has agreed to collect and hand out the order yet.</li>
                <li>
                  The exact price comes later, once somebody has taken that job — the
                  figure above is an estimate.
                </li>
                <li>Nothing has been ordered from the supplier.</li>
              </ul>
            </div>
          </section>

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

function Verdict({ verdict }: { verdict: StrategyVerdict }) {
  return (
    <div className={`why-verdict${verdict.viable ? " is-ok" : " is-no"}`}>
      <div className="why-verdict-head">
        <strong>{verdict.product}</strong>
        <span className={`chip ${verdict.viable ? "chip-ok" : "chip-warn"}`}>
          {verdict.viable ? "Worth doing" : "Not worth doing"}
        </span>
      </div>
      {verdict.viable ? (
        <p className="small">
          {verdict.selected_units} bags for {verdict.cases} full{" "}
          {verdict.cases === 1 ? "case" : "cases"} of {verdict.case_units}, nothing left
          over. {verdict.all_in_display} all in, against {verdict.retail_baseline_display}{" "}
          buying separately — {verdict.net_savings_display} saved,{" "}
          {verdict.net_savings_pct}.
        </p>
      ) : (
        <p className="small">
          {verdict.matched_units} bags were available against a {verdict.minimum_units}-bag
          minimum, so there was plenty — but {blockerCopy(verdict.blocker_code)}.{" "}
          {verdict.all_in_display !== "$0.00" ? (
            <>
              {verdict.all_in_display} all in, against {verdict.retail_baseline_display}{" "}
              buying separately.
            </>
          ) : null}
        </p>
      )}
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
      <div className="facts">
        <Fact label="Coordination event" value={<code>{data.event?.event_id}</code>} />
        <Fact label="Run" value={<code>{run?.run_id}</code>} />
        {/* Provider first, and never abbreviated away: it is what decides whether any
            of the words around it may say "model". */}
        <Fact label="Provider" value={`${run?.model_provider} · ${run?.model_id}`} />
        <Fact label="Objective" value={run?.objective ?? ""} />
        <Fact label="Outcome" value={run?.outcome ?? ""} />
        <Fact label="Ended" value={run?.termination_reason ?? ""} />
        <Fact
          label={words.iterations}
          value={`${run?.iterations ?? 0} of ${run?.bounds.max_iterations ?? 0} allowed`}
        />
        <Fact
          label={words.tokens}
          value={`${run?.input_tokens ?? 0} in · ${run?.output_tokens ?? 0} out`}
        />
      </div>

      {words.offline ? (
        <p className="small muted">
          <strong>This run used the deterministic offline planner.</strong> It is the real
          Strands loop, the real tool surface and the real bounds, with a planner in place
          of a model — which is why the token counts above are zero and why you can
          reproduce this run exactly. No model was called and none could have been: the
          function serving this page has no permission to call one. Live model execution
          is a separate, explicitly requested action that goes through Bedrock AgentCore
          Runtime, and it records its own provider here when it is the one that ran.
        </p>
      ) : null}

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
      </div>

      {data.clarification ? (
        <ClarificationProofBlock proof={data.clarification} />
      ) : null}

      <div className="stack-sm">
        <h3 className="small">Deterministic verdicts</h3>
        <ul className="proof-evals">
          {(data.investigated ?? []).map((v) => (
            <li key={v.evaluation_id}>
              <code>{v.evaluation_id}</code> · {v.product} ·{" "}
              <strong>{v.viable ? "viable" : v.blocker_code}</strong> · matched{" "}
              {v.matched_units}/{v.minimum_units} · {v.cases}×{v.case_units} cases ·
              surplus {v.surplus_units} · {v.net_savings_display} ({v.net_savings_pct})
            </li>
          ))}
        </ul>
      </div>

      <div className="facts">
        <Fact
          label="Options offered"
          value={`${(data.considered ?? []).length}, cap ${run?.bounds.max_strategy_listings ?? 0} listing`}
        />
        {/* Which run was shown the listing above. Named only when it is not this one,
            because "the listing this run received" is the ordinary case and labelling it
            every time would imply the two can drift apart more often than they do. The
            listing itself is stored as it was transmitted, so it is what that run saw
            rather than what the same options would say today. */}
        {data.evidence_run_id && data.evidence_run_id !== run?.run_id ? (
          <Fact
            label="Listing shown to"
            value={<code>{data.evidence_run_id}</code>}
          />
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

      <p className="small muted">
        Synthetic community, simulated payments, no supplier contacted. The software is
        real; the people and the money are not.
      </p>
    </div>
  );
}
