/* The judge walkthrough — one claim, reproduced by the person reading it.
 *
 * The video can explain the whole product. This exists for the four minutes somebody
 * spends in the live app afterwards, and it has exactly one job: let a person who has
 * never seen Pool establish for themselves that the answer changes when the *world*
 * changes rather than when the demand does.
 *
 * Every control here is a door onto a mechanism that already existed, and the doors are
 * thin on purpose:
 *
 *   Set up          → POST /api/onboarding, /api/onboarding/payment-method, /api/needs
 *   Quote A / B     → POST /api/demo/supplier-sample, which is the upload endpoint's own
 *                     ingestion function reached by naming a committed sheet instead of
 *                     picking it off a disk
 *   Ask Pool        → POST /api/agent/run, the member trigger a member can already press
 *   Start over      → POST /api/demo/reset, the reseed the drawer already offers
 *
 * Nothing on this screen is precomputed. Each step reports what the server said after it
 * ran — the parse counts and digest come off the import response, and every verdict is
 * read back out of the member's own outlook. There is no branch in this file that writes
 * a conclusion, which is the property that makes the walkthrough evidence rather than a
 * slideshow with buttons.
 *
 * What it deliberately does not do: create an operations console, animate progress
 * nobody is making, or add a primary nav entry. It is a page a judge arrives at on
 * purpose and a member never sees.
 */

import { useState } from "react";
import {
  MemberView,
  NeedOutlook,
  SupplierImportResult,
  api,
  importSampleQuote,
} from "../api";
import { ActorTag, Chip, IconArrowRight, IconCheck, IconCloud, IconReplay } from "../ui";

/** The two committed sheets, in the order the argument needs them. Names only — the
 *  server owns every term inside them, and it checks these against the manifest before
 *  reading anything. */
const QUOTE_A = "riverbend-split-case.csv";
const QUOTE_B = "riverbend-case-programme.csv";

/** The product the walkthrough is about. Jasmine rice, because the seed carries six
 *  independent declarations for it and no supplier at all — so the interesting situation
 *  pre-exists and the judge's own declaration is the seventh. */
const RICE = "prod_rice_jasmine";

type StepState = "todo" | "current" | "done";

function riceOutlook(member: MemberView | null): NeedOutlook | null {
  return (member?.needs_outlook ?? []).find((o) => o.product_id === RICE) ?? null;
}

/** Which steps are finished, derived from server state rather than counted locally.
 *
 *  A local counter would survive a reload while the world behind it did not, and the
 *  first thing a judge does with an unfamiliar page is reload it. */
function progress(member: MemberView | null, hasOrder: boolean) {
  const rice = riceOutlook(member);
  const state = rice?.state ?? "";
  const declared = Boolean(rice);
  /* The evaluator's own vocabulary, and the whole sequence in four values:
     `no_supply` before any quote, `not_worth_it` once a bulk offer exists to be judged
     and is judged not worth doing, `ready` once the better terms arrive, `in_pool` once
     an order has formed. Read, never assumed — if the engine's answer changes, this
     screen's idea of where the judge is changes with it. */
  const quoteA = declared && state !== "no_supply";
  const quoteB = declared && (state === "ready" || state === "in_pool" || hasOrder);
  return { declared, quoteA, quoteB, ran: hasOrder };
}

function Step({
  n,
  title,
  state,
  children,
}: {
  n: number;
  title: string;
  state: StepState;
  children: React.ReactNode;
}) {
  return (
    <li className={`judge-step is-${state}`}>
      <span className="judge-num" aria-hidden="true">
        {state === "done" ? <IconCheck size={13} /> : n}
      </span>
      <div className="judge-body">
        <h2 className="judge-step-title">{title}</h2>
        {children}
      </div>
    </li>
  );
}

/** What the server said about a file it just read. Never a verdict — a parse result. */
function ImportReceipt({ result }: { result: SupplierImportResult }) {
  return (
    <p className="judge-receipt">
      <code>{result.filename}</code> · {result.bytes} bytes · sha256{" "}
      <code>{result.sha256.slice(0, 16)}…</code>
      <br />
      {result.rows_found} record{result.rows_found === 1 ? "" : "s"} found ·{" "}
      {result.valid} valid · {result.rejected} rejected
      {result.recorded ? "" : ` · not recorded: ${result.reason ?? result.refused ?? ""}`}
    </p>
  );
}

export function JudgeDemo({
  member,
  hasOrder,
  onBack,
  onShowcase,
  onBehindPool,
  onRefresh,
}: {
  member: MemberView | null;
  /** Whether an order the server calls this member's exists. Read, never inferred. */
  hasOrder: boolean;
  onBack: () => void;
  onShowcase: () => void;
  onBehindPool: () => void;
  /** Re-read the server after an action. Must be the caller's *world-changed* path: an
   *  import moves none of the counts the member read is keyed on, by design. */
  onRefresh: () => Promise<void> | void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [receiptA, setReceiptA] = useState<SupplierImportResult | null>(null);
  const [receiptB, setReceiptB] = useState<SupplierImportResult | null>(null);
  /* What the server answered *at the moment each step ran*.
   *
   *  These steps used to render the live outlook, which meant a finished step silently
   *  restated itself: once the order formed, the step whose whole point is that Pool
   *  refused a willing supplier began reading "already coordinating this one". A judge
   *  scrolling back to check what they had seen found it had changed underneath them.
   *  Same boundary the run reports keep — what a step found is a fact about when it ran. */
  const [saidAt, setSaidAt] = useState<Record<string, { headline: string; blocker: string }>>({});
  /* The demand as it stood when the walkthrough started.
   *
   *  Read live, this line collapses the moment the order forms: `compatible_members`
   *  counts households *not* already inside a live pool for the product, which is the
   *  right number for "how much demand is available" and completely the wrong number
   *  here — everyone who buys rice is now in the order, so the step whose whole point is
   *  "seven people already wanted this" began reading "1 people". Captured once. */
  const [demandAt, setDemandAt] = useState<{ people: number; units: number; mine: number } | null>(
    null,
  );

  /** Read this member's own outlook for rice, now, and remember it against a step. */
  const capture = async (key: string, householdId?: string) => {
    const id = householdId ?? member?.id;
    if (!id) return;
    try {
      const fresh = await api.member(id);
      const rice = (fresh.needs_outlook ?? []).find((o) => o.product_id === RICE);
      if (rice) {
        setSaidAt((was) => ({
          ...was,
          [key]: { headline: rice.headline, blocker: rice.blocker ?? "" },
        }));
      }
      if (key === "before") {
        const d = (fresh.standing_demand ?? []).find((x) => x.product_id === RICE);
        if (d) {
          setDemandAt({
            people: d.compatible_members + 1,
            units: d.compatible_units + d.my_units,
            mine: d.my_units,
          });
        }
      }
    } catch {
      /* The step still shows its parse receipt; a missed capture is not worth an error. */
    }
  };

  const rice = riceOutlook(member);
  const standing = (member?.standing_demand ?? []).find((d) => d.product_id === RICE) ?? null;
  const p = progress(member, hasOrder);

  const act = async (key: string, fn: () => Promise<unknown>) => {
    setBusy(key);
    setError(null);
    try {
      await fn();
      await onRefresh();
      /* Bring the next thing to do into view. A checklist that advances off-screen asks
         the reader to go and find their own place, and this one is being followed by
         somebody who has never seen it. Instant, not smooth: the global
         reduced-motion rule already forces `scroll-behavior: auto`, and a four-minute
         walkthrough is not the place for a scroll animation. */
      window.requestAnimationFrame(() => {
        document
          .querySelector(".judge-step.is-current")
          ?.scrollIntoView({ block: "center" });
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  };

  const setUp = () =>
    act("setup", async () => {
      const consumer = await api.completeOnboarding("A judge", "ask_me");
      await api.saveOwnPaymentMethod();
      const today = new Date();
      const due = new Date(today.getTime() + 14 * 86400000);
      await api.declareNeed({
        household_id: consumer.household_id,
        group: "rice",
        quantity: 2,
        cadence_days: 30,
        expected_next_need_date: due.toISOString().slice(0, 10),
        flexibility_days: 14,
        routine_lead_days: 7,
        min_savings_pct: 15,
        max_spend_cents: 12000,
        substitution: "exact_only",
        active: true,
      });
      await capture("before", consumer.household_id);
    });

  const startOver = () =>
    act("reset", async () => {
      setReceiptA(null);
      setReceiptB(null);
      setSaidAt({});
      setDemandAt(null);
      await api.reset();
    });

  const state = (done: boolean, current: boolean): StepState =>
    done ? "done" : current ? "current" : "todo";

  return (
    <div className="stack judge">
      <header className="row-between judge-head">
        <div>
          <button className="btn btn-sm btn-ghost" onClick={onBack}>
            Leave the walkthrough
          </button>
          <h1 className="title" style={{ marginTop: 10 }}>
            Check Pool&apos;s central claim yourself
          </h1>
          <p className="lede" style={{ maxWidth: "62ch" }}>
            Four buttons, about four minutes. Pool only coordinates a purchase when the
            numbers actually work — so the interesting thing is not that it can say yes,
            it is that it says <em>no</em> to a supplier who would sell, and changes its
            mind only when the terms change.
          </p>
        </div>
        <button className="btn btn-sm" onClick={startOver} disabled={busy !== null}>
          <IconReplay />
          {busy === "reset" ? "Resetting…" : "Reset walkthrough"}
        </button>
      </header>

      {/* Said once, at the top, in the place somebody reads before they trust anything
          below it. The footer says it on every screen as well. */}
      <div className="judge-honesty">
        <Chip>synthetic</Chip>
        <span>
          Invented people, an invented wholesaler, and simulated payments. Riverbend
          Wholesale does not exist and no card is ever charged. The software, the parser
          and the arithmetic are real.
        </span>
      </div>

      {error ? (
        <div className="banner banner-stop">
          <span>{error}</span>
        </div>
      ) : null}

      <ol className="judge-steps">
        <Step n={1} title="Become a member of the demo community" state={state(p.declared, !p.declared)}>
          {p.declared ? (
            <p className="judge-said">
              You are <strong>{member?.display_name}</strong> in Demo University, with{" "}
              <strong>2 bags of rice</strong> on your list and nothing committed. That
              declaration is the only thing anybody does in this product.
            </p>
          ) : (
            <>
              <p className="judge-note">
                No form to fill in. This calls the same three endpoints the setup screens
                call — an account, a simulated card, and one standing declaration of two
                bags of rice a month.
              </p>
              <button
                className="btn btn-primary"
                onClick={setUp}
                disabled={busy !== null}
              >
                {busy === "setup" ? "Setting up…" : "Set that up for me"}
                <IconArrowRight />
              </button>
            </>
          )}
        </Step>

        <Step
          n={2}
          title="See the demand that was already there"
          state={state(p.quoteA, p.declared && !p.quoteA)}
        >
          {p.declared && (demandAt ?? standing) ? (
            <>
              <p className="judge-said">
                <strong>
                  {(demandAt?.people ?? (standing ? standing.compatible_members + 1 : 0))} people
                  near you buy this
                </strong>{" "}
                —{" "}
                {demandAt?.units ??
                  (standing ? standing.compatible_units + standing.my_units : 0)}{" "}
                bags standing, {demandAt?.mine ?? standing?.my_units ?? 0} of them yours.
              </p>
              <p className="judge-note">
                None of those people organised anything, and none of them can see each
                other. Six of them declared rice before you arrived. What is missing is
                not demand — Pool has no verified supplier for it, which is a completely
                different problem, and most software would have shown you an empty screen.
              </p>
              <p className="judge-verdict">
                <ActorTag actor="engine" label="Pool's answer" />{" "}
                <strong>{saidAt.before?.headline ?? rice?.headline ?? "watching"}</strong>
              </p>
            </>
          ) : (
            <p className="judge-note">Finish step 1 and this fills itself in.</p>
          )}
        </Step>

        <Step
          n={3}
          title="Let a supplier quote arrive — and watch Pool refuse it"
          state={state(p.quoteB, p.quoteA && !p.quoteB)}
        >
          <p className="judge-note">
            This imports a committed CSV from <code>demo-data/</code> through the same
            endpoint an operator uploading a file uses: the bytes are parsed, the schema
            is checked, and the digest is matched against{" "}
            <code>MANIFEST.json</code> before anything is written. Edit a price and it is
            refused. <strong>Nothing about people changes</strong> — no buyer, no
            declaration, no household.
          </p>
          {p.quoteA && receiptA ? <ImportReceipt result={receiptA} /> : null}
          {p.quoteA ? (
            <p className="judge-verdict">
              <ActorTag actor="engine" label="Pool's answer" />{" "}
              <strong>{saidAt.a?.headline ?? rice?.headline}</strong>
              {saidAt.a?.blocker ? (
                <span className="judge-because"> {saidAt.a.blocker}</span>
              ) : null}
            </p>
          ) : (
            <button
              className="btn btn-primary"
              onClick={() =>
                act("a", async () => {
                  setReceiptA(await importSampleQuote(QUOTE_A));
                  await capture("a");
                })
              }
              disabled={busy !== null || !p.declared}
            >
              {busy === "a" ? "Reading the file…" : "Import quote A"}
              <IconArrowRight />
            </button>
          )}
        </Step>

        <Step
          n={4}
          title="Now let better terms arrive"
          state={state(p.ran, p.quoteB && !p.ran)}
        >
          <p className="judge-note">
            The same path, the second committed sheet. Bigger cases, a higher minimum, a
            better unit price. Both sheets stay on file — nothing is deleted to make this
            work, and the evaluator picks between them.
          </p>
          {p.quoteB && receiptB ? <ImportReceipt result={receiptB} /> : null}
          {p.quoteB ? (
            <p className="judge-verdict">
              <ActorTag actor="engine" label="Pool's answer" />{" "}
              <strong>{saidAt.b?.headline ?? rice?.headline}</strong>
            </p>
          ) : (
            <button
              className="btn btn-primary"
              onClick={() =>
                act("b", async () => {
                  setReceiptB(await importSampleQuote(QUOTE_B));
                  await capture("b");
                })
              }
              disabled={busy !== null || !p.quoteA}
            >
              {busy === "b" ? "Reading the file…" : "Import quote B"}
              <IconArrowRight />
            </button>
          )}
        </Step>

        <Step n={5} title="Ask Pool to act on it" state={state(p.ran, p.quoteB && !p.ran)}>
          {p.ran ? (
            <>
              <p className="judge-said">
                An order formed from demand that was already there. Nobody was recruited,
                nobody was messaged, and no group was created.
              </p>
              <div className="btn-row">
                <button className="btn" onClick={onBack}>
                  See it on your home screen
                  <IconArrowRight />
                </button>
              </div>
            </>
          ) : (
            <>
              <p className="judge-note">
                In the real product Pool does this by itself on the community&apos;s pool
                day. Nothing is scheduled in a demo account, so it starts when you press
                the button.
              </p>
              <button
                className="btn btn-primary"
                onClick={() => act("run", () => api.run("member_scan"))}
                disabled={busy !== null || !p.quoteB}
              >
                {busy === "run" ? "Pool is checking…" : "Ask Pool to check now"}
                <IconArrowRight />
              </button>
            </>
          )}
        </Step>
      </ol>

      <section className="panel judge-next">
        <div className="panel-pad stack-sm">
          <h2 className="section-title">Two things the four minutes could not cover</h2>
          <p className="small muted prose">
            A payment that fails and is repaired, and the evidence that the agent and the
            deterministic engine did what this page says they did.
          </p>
          <div className="btn-row">
            <button className="btn" onClick={onShowcase}>
              <IconCloud />
              The whole lifecycle, including a failure
            </button>
            <button className="btn" onClick={onBehindPool}>
              What proves it — Behind Pool
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
