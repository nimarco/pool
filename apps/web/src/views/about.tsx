/* What Pool is — the argument, kept out of the way.
 *
 * A member using Pool does not need the thesis explained to them; they need their next
 * restock and the question Pool is asking. A judge landing cold on a URL needs exactly
 * the opposite. So the pitch lives here, one click from the environment indicator and
 * from the footer, rather than as a landing page the product has to get past.
 *
 * This is also where the three-actor grammar is defined. The glyphs appear throughout
 * the product; a legend that only existed inside the lifecycle reader was a legend most
 * people would never reach.
 */

import { ConvergenceFigure } from "../brand";
import { DemoConfig, Health } from "../api";
import {
  ActorKey,
  Block,
  Chip,
  IconArrowLeft,
  IconArrowRight,
  IconCloud,
  IconPlay,
} from "../ui";

export function About({
  health,
  demoConfig,
  memberCount,
  needCount,
  onBack,
  onOpenTechnical,
  onRun,
  running,
}: {
  health: Health | null;
  demoConfig: DemoConfig | null;
  memberCount: number | null;
  needCount: number | null;
  /** Product mode: a way back to the member's own screens. */
  onBack?: () => void;
  onOpenTechnical: () => void;
  /** Showcase mode: the original landing-page action, which runs the whole lifecycle. */
  onRun?: () => void;
  running?: boolean;
}) {
  const live = Boolean(demoConfig?.live_agent_available);
  return (
    <div className="stack">
      {onBack ? (
        <div>
          <button className="btn btn-sm btn-ghost" onClick={onBack}>
            <IconArrowLeft />
            Back to Pool
          </button>
        </div>
      ) : null}

      <section className="hero" style={{ paddingBlock: "10px 0" }}>
        <div className="hero-grid">
          <div>
            <h1>
              Ten people wanted the same thing. Nobody organised anything.{" "}
              <em>Pool noticed.</em>
            </h1>
            <p className="hero-lede">
              Every campus already runs this by hand — <em>“I can get 50 of these way
              cheaper, message me if you want one.”</em> Someone guesses the demand, fronts
              hundreds of dollars, answers thirty messages, and eats the leftovers. It
              happens once and stops. Pool runs the job in reverse: people say what they
              routinely buy, and an agent finds the group, the supplier and somebody to
              collect it — then does the coordination that made people quit.
            </p>
            {onRun ? (
              <div className="btn-row" style={{ marginTop: 26 }}>
                <button className="btn btn-primary btn-lg" onClick={onRun} disabled={running}>
                  <IconPlay />
                  {running ? "Running the lifecycle…" : "Run the full lifecycle"}
                </button>
                <button className="btn btn-lg" onClick={onOpenTechnical}>
                  <IconCloud />
                  See what runs on AWS
                </button>
              </div>
            ) : null}
            {memberCount && needCount ? (
              <p className="tiny faint" style={{ marginTop: 14 }}>
                The community you are looking at has {memberCount} members and {needCount}{" "}
                standing needs, and not one group among them.
              </p>
            ) : null}
          </div>
          <ConvergenceFigure />
        </div>
      </section>

      <section className="claims">
        <article className="claim">
          <h3>Nobody creates the group</h3>
          <p>
            That single inversion is the whole product. Members declare a recurring need
            once — protein every six weeks, coffee every month — and then forget about it.
            Pool watches for the moment several of those independently line up into
            something worth buying together. If this ever becomes “create a group and
            invite your friends”, the idea is gone: organising is precisely the labour
            being automated.
          </p>
        </article>
        <article className="claim">
          <h3>Somebody still has to carry the box</h3>
          <p>
            A bulk order is not a database write. Pool recruits a paid fulfiller from
            standing hosts <em>and</em> from the pool's own members, ranks them on
            capacity, vehicle, distance and the minimum pay they will accept, and offers
            the job to the best fit. They are not a reseller taking a risk — every unit is
            sold before it is bought.
          </p>
        </article>
        <article className="claim">
          <h3>The price includes everything</h3>
          <p>
            Merchandise, host pay, card processing and Pool's own fee, all on one screen,
            measured against what these people would have paid alone. Pool's fee is a
            share of the saving, so no saving means no fee. If paying the host fairly
            erases the discount, the pool should not form — and it does not. That is a
            correct outcome, not a bug.
          </p>
        </article>
      </section>

      <section className="grid grid-2">
        <div className="block">
          <h3 className="section-title" style={{ marginBottom: 12 }}>
            Why this needs an agent
          </h3>
          <p className="small muted prose">
            The work is not shopping. It is noticing that a group could exist, deciding
            whether it is worth forming, finding someone to collect it, pricing it exactly,
            asking only the people who need asking, repairing it when a card is declined,
            and knowing when to stop and do nothing. That is judgement under changing
            conditions across three parties — and it is exactly the labour that makes the
            informal version collapse.
          </p>
          <div style={{ marginTop: 16 }}>
            <ActorKey />
          </div>
          <p className="small muted prose" style={{ marginTop: 12 }}>
            Those three marks appear throughout Pool. The model decides <em>what to do</em>;
            deterministic code decides <em>what is true</em> — every cent, quantity,
            eligibility check and lifecycle transition. A language model should never be
            the source of a price somebody is charged, so structurally it cannot be: the
            pure domain layer performs no I/O and imports no adapter, and the model reaches
            it only through twelve typed tools.
          </p>
          <div className="btn-row" style={{ marginTop: 14 }}>
            <button className="btn btn-sm" onClick={onOpenTechnical}>
              See it run on AWS
              <IconArrowRight />
            </button>
          </div>
        </div>

        <div className="block">
          <h3 className="section-title" style={{ marginBottom: 12 }}>
            What is real, and what is not
          </h3>
          <div className="stack-sm">
            <p className="small">
              <Chip tone="ok">real</Chip> The coordination lifecycle demonstrated here is
              functional end to end. The Strands loop, the demand matching, the case
              arithmetic, the host ranking, the payment authorisation state machine, the
              recovery after a decline, the one-time pickup credentials — all of it
              genuinely runs, application state is stored and read back, and every number
              you see was computed by that code. What is not built is everything after the
              coordination: no payout rail, no supplier ordering, no refunds.
              {live ? (
                <>
                  {" "}
                  So is the deployed agent: one action really invokes Pool's coordinator on
                  Amazon Bedrock AgentCore Runtime in {demoConfig?.region}.
                </>
              ) : null}
            </p>
            <p className="small">
              <Chip tone="warn">synthetic</Chip> The community, the members and the
              supplier catalogue. Demo University is invented and no wholesale relationship
              exists.
            </p>
            <p className="small">
              <Chip tone="warn">simulated</Chip> Money and the supplier order. No card is
              charged, no goods exist, and every purchase record is flagged as simulated
              wherever it appears. The environment is synthetic precisely so a stranger can
              run the complete lifecycle without anyone being charged.
            </p>
            {health ? (
              <p className="tiny mono muted">
                store {health.repository} · model {health.model_provider} · payments{" "}
                {health.payment_provider}/{health.payment_mode} · purchase{" "}
                {health.purchase_simulated ? "simulated" : health.purchase_executor} ·
                background schedules {health.schedules_enabled ? "on" : "off"}
              </p>
            ) : null}
          </div>
        </div>
      </section>

      <Block title="Who this is for">
        <p className="small muted prose">
          A <strong>community</strong> is the trust-and-density boundary Pool coordinates
          inside: a campus, an apartment block, a workplace, a neighbourhood, a school.
          Campuses are the first polished case because they have overlapping recurring
          needs, walkable distances, public pickup points and a predictable weekly rhythm —
          not because the model is university-shaped. Bulk pricing normally favours whoever
          can afford a larger purchase up front and has somewhere to put it; pooling is a
          way to reach that price without each person carrying the capital, the quantity,
          the storage and the coordination alone. Membership is per community, verification
          is pluggable, and Pool never asks anyone for their institution's password.
        </p>
      </Block>
    </div>
  );
}
