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
              Informal bulk buys make one organiser guess demand, front money, chase replies
              and absorb leftovers. Pool reverses the job: members state recurring needs,
              then an agent finds and coordinates a viable order.
            </p>
            <p className="small muted prose" style={{ marginTop: 14 }}>
              Built for existing communities; campuses are the first wedge, not a domain
              assumption.
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
          <h2>Nobody creates the group</h2>
          <p>
            Members declare recurring needs independently; Pool finds the overlap. There is
            no create-a-group or invite flow.
          </p>
        </article>
        <article className="claim">
          <h2>Somebody still has to carry the box</h2>
          <p>
            Pool ranks willing fulfillers on job facts and pays the best eligible fit. Every
            unit is sold before the host collects it.
          </p>
        </article>
        <article className="claim">
          <h2>The price includes everything</h2>
          <p>
            Buyers see merchandise, host pay, processing and Pool's fee against retail. If
            fair host pay erases the saving, no pool forms.
          </p>
        </article>
      </section>

      <section className="grid grid-2">
        <div className="block">
          <h2 className="section-title" style={{ marginBottom: 12 }}>
            Why this needs an agent
          </h2>
          <p className="small muted prose">
            The agent chooses what to investigate, who to ask and how to recover as buyer,
            host and supplier conditions change.
          </p>
          <div style={{ marginTop: 16 }}>
            <ActorKey />
          </div>
          <p className="small muted prose" style={{ marginTop: 12 }}>
            The model decides <em>what to do</em>; deterministic code decides every cent,
            quantity, eligibility check and lifecycle transition.
          </p>
          <details className="inset" style={{ marginTop: 12 }}>
            <summary className="small">
              <strong>Implementation boundary</strong>
            </summary>
            <p className="small muted prose" style={{ marginTop: 10 }}>
              The pure domain layer performs no I/O and imports no adapter. The model reaches
              application state only through twelve typed tools, so it cannot author a price.
            </p>
          </details>
          <div className="btn-row" style={{ marginTop: 14 }}>
            <button className="btn btn-sm" onClick={onOpenTechnical}>
              See it run on AWS
              <IconArrowRight />
            </button>
          </div>
        </div>

        <div className="block">
          <h2 className="section-title" style={{ marginBottom: 12 }}>
            What is real, and what is not
          </h2>
          <div className="stack-sm">
            <p className="small">
              <Chip tone="ok">real</Chip> Strands, matching, case arithmetic, host ranking,
              authorization state, decline recovery and pickup credentials run end to end;
              state is stored/read back and code computes every number. No payout, real
              supplier-order or refund rail exists.
              {live ? (
                <>
                  {" "}
                  One Product action also invokes AgentCore/Bedrock in {demoConfig?.region}.
                </>
              ) : null}
            </p>
            <p className="small">
              <Chip tone="warn">synthetic</Chip> Community, members and supplier catalogue;
              Demo University is invented and no wholesale relationship exists.
            </p>
            <p className="small">
              <Chip tone="warn">simulated</Chip> Payments and supplier order; no card is
              charged, no goods exist, and purchase records are labelled simulated.
            </p>
            {health ? (
              <details className="inset">
                <summary className="tiny muted">
                  Environment detail
                </summary>
                <p className="tiny mono muted" style={{ marginTop: 8 }}>
                  store {health.repository} · model {health.model_provider} · payments{" "}
                  {health.payment_provider}/{health.payment_mode} · purchase{" "}
                  {health.purchase_simulated ? "simulated" : health.purchase_executor} ·
                  background schedules {health.schedules_enabled ? "on" : "off"}
                </p>
              </details>
            ) : null}
          </div>
        </div>
      </section>

      <details className="block">
        <summary className="section-title">
          Who this is for
        </summary>
        <p className="small muted prose" style={{ marginTop: 12 }}>
          A Community is Pool's local trust-and-density boundary: campus, apartment block,
          workplace, neighbourhood or school. Pool makes bulk pricing accessible without one
          member fronting the capital, storage and coordination; membership is per Community,
          verification is pluggable, and Pool never asks for an institution password.
        </p>
      </details>
    </div>
  );
}
