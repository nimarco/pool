/** Why this order? — and, underneath it, the proof.
 *
 *  One server read (`/api/needs/{id}/coordination`) behind two audiences. The member-facing
 *  half answers *what happened, and what has not happened*; the technical half answers
 *  *which model, which tools, in what order, under what bounds*. They are the same stored
 *  rows at two levels of detail, which is the property that makes the second one evidence
 *  for the first rather than a parallel story told beside it.
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
import { NeedCoordination, StrategyVerdict, api } from "../api";
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

function Proof({ data }: { data: NeedCoordination }) {
  const run = data.run;
  return (
    <div className="panel-pad stack-sm">
      <div className="facts">
        <Fact label="Coordination event" value={<code>{data.event?.event_id}</code>} />
        <Fact label="Run" value={<code>{run?.run_id}</code>} />
        <Fact label="Model" value={`${run?.model_provider} · ${run?.model_id}`} />
        <Fact label="Objective" value={run?.objective ?? ""} />
        <Fact label="Outcome" value={run?.outcome ?? ""} />
        <Fact label="Ended" value={run?.termination_reason ?? ""} />
        <Fact
          label="Model calls"
          value={`${run?.iterations ?? 0} of ${run?.bounds.max_iterations ?? 0} allowed`}
        />
        <Fact
          label="Tokens"
          value={`${run?.input_tokens ?? 0} in · ${run?.output_tokens ?? 0} out`}
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
        <p className="small muted">
          The model chose which option to investigate and moved on when the first was
          refused. It never computed a price, decided who was compatible, or supplied a
          member, a quantity or a supplier term — every one of those came from
          deterministic code, and the tool it calls to form an order takes two identifiers
          and nothing else.
        </p>
      </div>

      {data.clarification ? (
        <div className="stack-sm">
          <h3 className="small">What Pool decided to ask, before any of this</h3>
          <div className="facts">
            <Fact label="Plan" value={<code>{data.clarification.plan_id}</code>} />
            <Fact label="Run" value={<code>{data.clarification.run_id || "none"}</code>} />
            <Fact
              label="Model"
              value={
                data.clarification.model_id
                  ? `${data.clarification.model_provider} · ${data.clarification.model_id}`
                  : "not run in this workspace"
              }
            />
            <Fact
              label="Tokens"
              value={`${data.clarification.input_tokens} in · ${data.clarification.output_tokens} out`}
            />
          </div>
          <ul className="proof-evals">
            <li>
              <strong>Approved:</strong>{" "}
              {data.clarification.offered.map((q) => (
                <code key={q}>{q} </code>
              ))}
            </li>
            <li>
              <strong>Asked, in this order:</strong>{" "}
              {data.clarification.asked.length === 0 ? (
                <span className="muted">nothing</span>
              ) : (
                data.clarification.asked.map((q) => (
                  <code key={q}>{q} </code>
                ))
              )}
            </li>
          </ul>
          <p className="small muted">
            A separate, earlier run, with its own budget. The model chose which of the
            approved questions were worth asking and in what order — a subset of the list
            above it, and it cannot write one that is not on it. What each answer{" "}
            <em>means</em> was decided by nothing in this table: every answer maps to a
            fixed rule in <code>services/needs.policy_from_answers</code>, curated under{" "}
            <code>
              {data.clarification.family} v{data.clarification.schema_version}
            </code>
            .
          </p>
        </div>
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
