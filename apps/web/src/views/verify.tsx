/** Verify this yourself — the front door for somebody checking the claim.
 *
 *  **This is not a second product.** The judge demo it replaces walked a visitor through
 *  loading a fixture, recording a supplier quote and pressing "run agent": six actions
 *  whose only purpose was advancing a demo, which is exactly what a sceptical reader is
 *  trying to see past. Nothing here presses anything on Pool's behalf.
 *
 *  What it does is put somebody in a synthetic community that already has fragmented
 *  coffee demand in it, tell them plainly what is real and what is not, and then get out
 *  of the way. The interesting event is *their own declaration* — which is an ordinary
 *  member action, on the ordinary member screen, and is the only thing that causes
 *  anything.
 *
 *  The workspace is separate for two reasons that are not presentational: the curated
 *  coffee community is deliberately not part of the canonical seed, and saving a
 *  declaration here dispatches its coordination event in the same request, which would be
 *  a cost bug anywhere else (AGENTS.md §3.3).
 */
import { useEffect } from "react";
import { Health, api } from "../api";

export function Verify({
  health,
  onStart,
  onHome,
}: {
  health: Health | null;
  /** Into the ordinary product, at the one screen where a member says what they buy. */
  onStart: () => void;
  onHome: () => void;
}) {
  /* Entering the world is the whole of what this page does on arrival. Everything after
     it is the product. */
  useEffect(() => {
    api.setVerifyScope(true);
  }, []);

  return (
    <div className="stack">
      <header className="stack-sm">
        <h1 className="title">Verify this yourself</h1>
        <p className="lede">
          You are about to use Pool as a member of a synthetic community that already has
          coffee demand in it — a dozen households who buy coffee and disagree about which
          coffee. Nothing has been arranged for you.
        </p>
      </header>

      <section className="panel">
        <div className="panel-head">
          <h2>What to do</h2>
        </div>
        <div className="panel-pad stack-sm">
          <ol className="verify-steps">
            <li>
              Open <strong>What you buy</strong> and add a coffee you drink — say{" "}
              <strong>three bags a month</strong>.
            </li>
            <li>
              Say whether you would take another brand. If you would, Pool looks at what it
              can source and what other members have asked for, and asks only the questions
              whose answers would change which orders you could join.
            </li>
            <li>
              <strong>Answer them the way you actually buy.</strong> Each answer shows the
              standing demand it would let Pool combine you with, so you can see what a
              narrower answer costs you — but a preference you do not hold is not worth
              having, and Pool will not push you off one.
            </li>
            <li>Save.</li>
          </ol>
          <p className="small">
            That is the whole of it. Saving is what causes Pool to look; there is no
            &ldquo;run&rdquo; button, and pressing one would be the thing this page exists
            to avoid. When it has finished, Home will have changed — and every row that
            changed can tell you why.
          </p>
          <p className="small muted">
            <strong>What changes is a real answer, not necessarily an order.</strong> A
            narrow set of answers can leave Pool watching — there is compatible demand, but
            not enough of it under your rules to buy against, and it will say so in those
            words. A broader set exposes more of what is already standing here. Both are the
            software working; neither is arranged in advance, and nothing on this page knows
            which one you will get.
          </p>
          <p className="small muted">
            Quantity matters for the same reason. Three is suggested because it lands on a
            supplier&apos;s case boundary in this particular community — try two instead and
            Pool will tell you, truthfully, that it could assemble an order but not one you
            would be in, so it did not form it.
          </p>
          <p className="small muted">
            You will be a member of <strong>Demo University</strong>, which is the only
            community here — Pool has not asked your browser where you are and has not
            guessed, which is what makes this behave identically wherever it is opened. It
            is invented, and so is everyone in it, so nothing here implies a partnership
            with a real institution.
          </p>
          <p className="small muted">
            Nothing is one-way. Every answer stays editable afterwards, including the
            first one — narrow your rules and Pool takes you out of an order they no
            longer allow; widen them again and it puts you back.
          </p>
          <div className="row-actions">
            <button className="btn btn-primary" onClick={onStart}>
              Start — add what you buy
            </button>
            <button className="btn btn-ghost" onClick={onHome}>
              Look at Home first
            </button>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>What is real here, and what is not</h2>
        </div>
        <div className="panel-pad stack-sm">
          <ul className="verify-facts">
            <li>
              <strong>Real:</strong> the compatibility engine, the supplier maths, the case
              fitting, the landed price, the agent loop and its bounds, and every record
              you can read afterwards.
            </li>
            <li>
              <strong>Synthetic:</strong> the community, the households, the products and
              the supplier quotes. No real person or roaster is represented.
            </li>
            <li>
              <strong>Simulated:</strong> payments. No card is charged, authorised, or
              stored, and no supplier is contacted.
            </li>
            {health ? (
              <li>
                <strong>This deployment:</strong> model provider{" "}
                <code>{health.model_provider}</code>, payments{" "}
                <code>{health.payment_provider}</code>, purchasing{" "}
                <code>{health.purchase_simulated ? "simulated" : "live"}</code>, schedules{" "}
                <code>{health.schedules_enabled ? "on" : "off"}</code>.
              </li>
            ) : null}
          </ul>
          <p className="small muted">
            Your session has its own copy of this community. Nobody else can see it, and it
            is swept automatically.
          </p>
        </div>
      </section>
    </div>
  );
}
