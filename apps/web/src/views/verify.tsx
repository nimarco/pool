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
 *  **Why almost all of it is behind one disclosure.** This page used to argue its case in
 *  five paragraphs above the button, and the button sat three phone screens down. Every
 *  one of those paragraphs was true and none of them was doing the job the first screen
 *  has: what this is, what to do, and where to press. The truth did not move out of the
 *  product — it moved *below the fold*, into "How this demo works", which is open to
 *  anybody in one click and is where a sceptic looks anyway. What stayed above it is the
 *  one boundary nobody should have to click for: this community is synthetic and the
 *  money is simulated.
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
    <div className="stack verify">
      <header className="stack-sm">
        <h1 className="title">Verify this yourself</h1>
        <p className="lede">
          You are joining a synthetic community that already buys coffee. Nothing here has
          been arranged for you.
        </p>
      </header>

      <ol className="verify-steps">
        <li>
          Add a coffee you drink — <strong>three bags a month</strong>.
        </li>
        <li>Say whether another brand would do.</li>
        <li>
          <strong>Answer them the way you actually buy.</strong>
        </li>
        <li>Save.</li>
      </ol>

      <div className="row-actions">
        <button className="btn btn-primary" onClick={onStart}>
          Start — add what you buy
        </button>
        <button className="btn btn-ghost" onClick={onHome}>
          Look at Home first
        </button>
      </div>

      {/* The one boundary that does not get to be a click away. Six words, above the
          fold, on first paint — and the link into the whole of it. */}
      <p className="verify-badge">
        Synthetic community · simulated payments · real software
      </p>

      <details className="panel why-fold">
        <summary>
          <span>How this demo works</span>
          <span className="small muted">what is real, and what is not</span>
        </summary>
        <div className="panel-pad stack-sm">
          <h3 className="small">What saving does</h3>
          <p className="small muted">
            Saving is what causes Pool to look; nothing on this path asks you to press
            &ldquo;run&rdquo;. Home does carry an <strong>Ask Pool to check now</strong>{" "}
            button, and on this deployment it runs the same bounded loop with the same
            deterministic planner, at zero model tokens — live model invocation is
            switched off here, so there is no control that spends one. When it has
            finished, Home will have changed, and every row that changed can tell you why.
          </p>
          <p className="small muted">
            <strong>What changes is a real answer, not necessarily an order.</strong> A
            narrow set of answers can leave Pool watching — there is compatible demand,
            but not enough of it under your rules to buy against, and it will say so in
            those words. A broader set exposes more of what is already standing here. Both
            are the software working; neither is arranged in advance, and nothing on this
            page knows which one you will get.
          </p>
          <p className="small muted">
            Quantity matters for the same reason. Three is suggested because it lands on a
            supplier&apos;s case boundary in this particular community — try two instead
            and Pool will tell you, truthfully, that it could assemble an order but not one
            you would be in, so it did not form it.
          </p>
          <p className="small muted">
            Nothing is one-way. Every answer stays editable afterwards, including the first
            one — narrow your rules and Pool takes you out of an order they no longer
            allow; widen them again and it puts you back.
          </p>

          <h3 className="small">What is real here, and what is not</h3>
          <ul className="verify-facts">
            <li>
              <strong>Real:</strong> the compatibility engine, the supplier maths, the case
              fitting, the landed price, the agent loop and its bounds, and every record
              you can read afterwards.
            </li>
            <li>
              <strong>Synthetic:</strong> the community, the households and the supplier
              quotes — no real person is represented, and the two roasters in the coffee
              story, Kestrel Roastworks and Harbourstone, are invented. Product identities
              are <strong>real</strong>: a dated Open Food Facts snapshot, credited under
              About.
            </li>
            <li>
              <strong>Simulated:</strong> payments and the supplier order. No card is
              charged, authorised, or stored, and no supplier is contacted.
            </li>
            <li>
              <strong>Demo University</strong> is the only community here, and it is
              invented — Pool has not asked your browser where you are and has not guessed,
              which is what makes this behave identically wherever it is opened. Nothing
              here implies a partnership with a real institution.
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
      </details>
    </div>
  );
}
