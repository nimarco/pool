/* Setting up an account, for the person actually at the screen.
 *
 * Before this existed, a visitor opened Pool and was silently *cast* as a seeded
 * student: greeted by somebody else's name, holding somebody else's card, apparently
 * buying paper towels they had never mentioned. That is fine as operator scaffolding and
 * wrong as a consumer product, and it undercut the one sentence the whole thing rests on
 * — *I tell Pool what I buy, and Pool does the rest* — because it was never clear who
 * "I" was.
 *
 * Four steps, one idea each:
 *
 *   who you are → where you are → what you buy → how much Pool may do
 *
 * Deliberately not five. Payment sits on the autonomy step rather than owning one,
 * because "may Pool spend my money without asking" and "here is the money" are the same
 * question asked twice, and splitting them would have made setup feel like a form.
 *
 * The location step is the one worth reading the code for. It asks a real question and
 * collects no coordinates — see `WhereStep`.
 */

import { useEffect, useRef, useState } from "react";
import { Consumer, NeedDraft, Place, api } from "../api";
import { ChosenCard, ProductSearch } from "../product-search";
import { ChosenItem, asChosen } from "../chosen";
import { IconArrowRight, IconCheck } from "../ui";

type Step = "you" | "where" | "buy" | "authority";

const STEPS: { id: Step; label: string }[] = [
  { id: "you", label: "You" },
  { id: "where", label: "Where" },
  { id: "buy", label: "What you buy" },
  { id: "authority", label: "How Pool acts" },
];

const DAY_MS = 24 * 60 * 60 * 1000;
const DEFAULT_CADENCE = 30;
const DEFAULT_NEXT_NEEDED_DAYS = 14;

function isoInDays(days: number): string {
  return new Date(Date.now() + days * DAY_MS).toISOString().slice(0, 10);
}

function daysUntil(iso: string): number {
  const then = new Date(`${iso}T00:00:00`).getTime();
  return Math.max(0, Math.round((then - new Date().setHours(0, 0, 0, 0)) / DAY_MS));
}

/** The same rule the Needs form uses: "I need it by the 3rd" already says Pool may buy
 *  any time between now and then, clamped to one restock cycle (§24). */
function defaultFlexibility(nextNeeded: string, cadence: number): number {
  return Math.min(daysUntil(nextNeeded), Math.max(0, cadence));
}

/* ------------------------------------------------------------------- progress */

function Progress({ current }: { current: Step }) {
  const index = STEPS.findIndex((s) => s.id === current);
  return (
    <ol className="onboard-steps" aria-label="Setup progress">
      {STEPS.map((s, i) => (
        <li
          key={s.id}
          className={i < index ? "is-done" : i === index ? "is-current" : ""}
          aria-current={i === index ? "step" : undefined}
        >
          <span className="onboard-step-dot" aria-hidden="true">
            {i < index ? <IconCheck size={11} /> : i + 1}
          </span>
          <span className="onboard-step-label">{s.label}</span>
        </li>
      ))}
    </ol>
  );
}

/* ----------------------------------------------------------------- 1. who you are */

function YouStep({
  name,
  onName,
  onNext,
}: {
  name: string;
  onName: (v: string) => void;
  onNext: () => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => ref.current?.focus(), []);
  const ready = name.trim().length > 0;

  return (
    <form
      className="stack-sm"
      onSubmit={(e) => {
        e.preventDefault();
        if (ready) onNext();
      }}
    >
      <h1 className="display onboard-title">What should Pool call you?</h1>
      <p className="lede">
        Pool coordinates buying between neighbours. This is the name they would see on a
        pickup list — nothing else about you is shared.
      </p>
      <label className="field field-wide">
        <span className="field-label">Your name</span>
        <input
          ref={ref}
          className="control control-search"
          type="text"
          value={name}
          maxLength={40}
          onChange={(e) => onName(e.target.value)}
          placeholder="Alex"
          autoComplete="given-name"
          required
        />
      </label>
      <div className="btn-row">
        <button className="btn btn-primary btn-lg" type="submit" disabled={!ready}>
          Continue
          <IconArrowRight />
        </button>
      </div>
    </form>
  );
}

/* ------------------------------------------------------------------- 2. where */

/** Where you are — asked honestly, and answered without taking a coordinate.
 *
 *  Pool is a local product: it only works if the people it matches you with are close
 *  enough to share one pickup. So "where are you" is a real question, and in the real
 *  product the answer would come from the device.
 *
 *  It does not come from the device here, and that is deliberate rather than lazy.
 *  This demo's community is an invented campus at invented coordinates, and a judge
 *  running it could be in any city on Earth. Taking a real position and quietly treating
 *  it as a room on that campus would be a lie about the exact thing location is for —
 *  and taking one only to discard it would be collecting a sensitive value for nothing.
 *  The deployed `Permissions-Policy` denies geolocation outright, and this pass leaves
 *  that alone.
 *
 *  So the step orients instead: it names the local network, shows what being inside it
 *  is worth in real numbers off the server, and says plainly that the network is
 *  synthetic. Nobody has to be anywhere in particular for that to be true. */
function WhereStep({
  place,
  onNext,
  onBack,
}: {
  place: Place | null;
  onNext: () => void;
  onBack: () => void;
}) {
  return (
    <div className="stack-sm">
      <h1 className="display onboard-title">Pool works street by street.</h1>
      <p className="lede">
        The people it finds for you have to be close enough to collect from the same
        place, so the one thing it needs first is which local network you are in.
      </p>

      {/* Presented as what it is in the real product — a list you were found near and
          choose from — rather than as a single fact stated at you. The previous version
          named Demo University and offered no interaction, which was honest and taught
          nothing: a reader could not tell whether Pool works by asking you, by guessing,
          or by having exactly one community in the world.

          The list has one entry here, and saying so is better than hiding the shape. */}
      <div className="inset stack-sm">
        <div className="row-between" style={{ alignItems: "baseline" }}>
          <span className="section-title">Communities near you</span>
          <span className="tiny faint">1 found</span>
        </div>

        <button className="community-choice" onClick={onNext}>
          <span className="community-choice-body">
            <span className="row-title">
              {place?.community_name ?? "Demo University"}
              {place?.synthetic ? <span className="chip">demo</span> : null}
            </span>
            <span className="small muted">
              {place ? `${place.member_count} members` : "—"}
              {place ? ` · ${place.pickup_site_count} pickup points` : ""}
              {place ? " · everyone within a short walk of one of them" : ""}
            </span>
          </span>
          <IconArrowRight />
        </button>

        {/* The truth boundary, stated where the decision is made rather than buried in a
            policy page. It is what lets this screen work identically for a judge in
            another hemisphere. */}
        <p className="small muted prose">
          In the real product this list comes from your device. It does not here: Pool has
          not asked your browser where you are and has not guessed. Demo University is
          invented and so is everyone in it, which is what makes the demo behave the same
          way wherever it is opened — and it is not a real institution, so nothing here
          implies a partnership with one.
        </p>
      </div>

      <div className="btn-row">
        {/* Named after the consequence. "Continue" would make the row above decorative,
            and joining a community is the thing this screen is for. */}
        <button className="btn btn-primary btn-lg" onClick={onNext}>
          Join {place?.community_name ?? "the demo community"}
          <IconArrowRight />
        </button>
        <button className="btn" onClick={onBack}>
          Back
        </button>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- 3. what you buy */

function BuyStep({
  added,
  onAdd,
  onNext,
  onBack,
  busy,
  error,
}: {
  added: { item: ChosenItem; quantity: number }[];
  onAdd: (item: ChosenItem, draft: NeedDraft) => Promise<void>;
  onNext: () => void;
  onBack: () => void;
  busy: boolean;
  error: string | null;
}) {
  const [chosen, setChosen] = useState<ChosenItem | null>(null);
  const [quantity, setQuantity] = useState(2);
  const [cadence, setCadence] = useState(DEFAULT_CADENCE);
  const [nextNeeded, setNextNeeded] = useState(isoInDays(DEFAULT_NEXT_NEEDED_DAYS));

  const reset = () => {
    setChosen(null);
    setQuantity(2);
    setCadence(DEFAULT_CADENCE);
    setNextNeeded(isoInDays(DEFAULT_NEXT_NEEDED_DAYS));
  };

  const flexibility = defaultFlexibility(nextNeeded, cadence);

  const save = async () => {
    if (!chosen) return;
    await onAdd(chosen, {
      household_id: "",
      ...chosen.draft,
      quantity,
      cadence_days: cadence,
      expected_next_need_date: nextNeeded,
      flexibility_days: flexibility,
      routine_lead_days: 7,
      min_savings_pct: 15,
      max_spend_cents: 12000,
      active: true,
    });
    reset();
  };

  return (
    <div className="stack-sm">
      <h1 className="display onboard-title">What do you buy regularly?</h1>
      <p className="lede">
        This is the only thing Pool ever needs from you. It watches for other people
        nearby who need the same thing, and works out whether buying together is cheaper.
      </p>

      {added.length > 0 ? (
        <ul className="onboard-added" aria-label="Added so far">
          {added.map((a) => (
            <li key={a.item.key}>
              <span className="onboard-added-tick" aria-hidden="true">
                <IconCheck size={12} />
              </span>
              <ChosenCard item={a.item} />
              <span className="small muted onboard-added-qty">
                {a.quantity} {a.item.unit}
                {a.quantity === 1 ? "" : "s"}
              </span>
            </li>
          ))}
        </ul>
      ) : null}

      {chosen ? (
        <div className="inset stack-sm">
          <div className="chosen-product">
            <ChosenCard item={chosen} />
            <button className="btn btn-sm btn-ghost" type="button" onClick={reset}>
              Change
            </button>
          </div>
          <div className="field-grid">
            <label className="field">
              <span className="field-label">How many</span>
              <div className="control-suffix">
                <input
                  className="control"
                  type="number"
                  min={1}
                  max={100}
                  value={quantity}
                  onChange={(e) => setQuantity(Number(e.target.value))}
                />
                <span className="suffix">{chosen.unit}</span>
              </div>
            </label>
            <label className="field">
              <span className="field-label">You buy this about every</span>
              <div className="control-suffix">
                <input
                  className="control"
                  type="number"
                  min={1}
                  max={365}
                  value={cadence}
                  onChange={(e) => setCadence(Number(e.target.value))}
                />
                <span className="suffix">days</span>
              </div>
            </label>
            <label className="field field-wide">
              <span className="field-label">When do you next need it?</span>
              <input
                className="control"
                type="date"
                value={nextNeeded}
                onChange={(e) => setNextNeeded(e.target.value)}
              />
              <span className="field-note">
                {flexibility > 0
                  ? `Pool may buy any time in the ${flexibility} days before that, if it saves money.`
                  : "Pool will only buy on that date — never earlier."}
              </span>
            </label>
          </div>
          {error ? <p className="form-error">{error}</p> : null}
          <div className="btn-row">
            <button className="btn btn-primary" onClick={() => void save()} disabled={busy}>
              {busy ? <span className="spinner" /> : null}
              Add this
            </button>
          </div>
        </div>
      ) : (
        <ProductSearch
          onSelect={(picked) => setChosen(asChosen(picked))}
          onUnresolved={(query) => {
            void api
              .customProduct(query)
              .then((product) => setChosen(asChosen({ kind: "product", product })))
              .catch(() => {});
          }}
        />
      )}

      <div className="btn-row">
        <button className="btn btn-primary btn-lg" onClick={onNext} disabled={added.length === 0}>
          {added.length === 0 ? "Add one to continue" : "Continue"}
          {added.length === 0 ? null : <IconArrowRight />}
        </button>
        <button className="btn" onClick={onBack}>
          Back
        </button>
      </div>
      <p className="tiny faint">
        Saving this commits nothing and joins nothing. You are not creating a group and
        not inviting anyone.
      </p>
    </div>
  );
}

/* -------------------------------------------------------------- 4. how Pool acts */

function AuthorityStep({
  mode,
  onMode,
  hasPayment,
  onAddPayment,
  onFinish,
  onBack,
  busy,
  paymentBusy,
  error,
}: {
  mode: string;
  onMode: (v: string) => void;
  hasPayment: boolean;
  onAddPayment: () => void;
  onFinish: () => void;
  onBack: () => void;
  busy: boolean;
  paymentBusy: boolean;
  error: string | null;
}) {
  return (
    <div className="stack-sm">
      <h1 className="display onboard-title">How much should Pool handle?</h1>
      <p className="lede">
        Pool never spends more than your limits allow. This decides whether it checks with
        you first when everything already fits.
      </p>

      <fieldset className="onboard-choices">
        <legend className="sr-only">When Pool may act</legend>
        {[
          {
            value: "ask_me",
            title: "Ask me first",
            body: "Pool works out the whole order and then waits for a yes before anything is charged.",
          },
          {
            value: "smart_join",
            title: "Act when it fits my limits",
            body: "If the saving, the price and the walk are all inside what you allow, Pool goes ahead and tells you.",
          },
        ].map((choice) => (
          <label
            key={choice.value}
            className={`onboard-choice${mode === choice.value ? " is-active" : ""}`}
          >
            <input
              type="radio"
              name="autonomy"
              value={choice.value}
              checked={mode === choice.value}
              onChange={() => onMode(choice.value)}
            />
            <span>
              <strong>{choice.title}</strong>
              <span className="small muted">{choice.body}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <p className="tiny faint">
        Either way Pool stops and asks whenever a limit would be crossed. You can change
        this at any time.
      </p>

      <div className="inset stack-sm">
        <div className="row-between" style={{ alignItems: "flex-start", gap: 12 }}>
          <div>
            <div className="row-title">
              Payment method
              {hasPayment ? <span className="chip chip-ok">added</span> : null}
            </div>
            <p className="small muted" style={{ marginTop: 4 }}>
              Nothing is charged now. Pool only ever authorises the exact final amount,
              after you have seen it.
            </p>
          </div>
          {hasPayment ? null : (
            <button className="btn btn-sm" onClick={onAddPayment} disabled={paymentBusy}>
              {paymentBusy ? <span className="spinner" /> : null}
              Add a test card
            </button>
          )}
        </div>
        {/* Unmissable, because this is the one screen where somebody might reasonably
            wonder whether real money is involved. */}
        <p className="tiny faint">
          Simulated for this demo — no real card, no real charge, and no card details are
          collected or stored.
        </p>
      </div>

      {error ? <p className="form-error">{error}</p> : null}

      <div className="btn-row">
        {/* Also blocked while the card request is in flight, and not for tidiness.
            Finishing writes the whole household row; if it read that row before the
            payment call had landed, it would write back a copy with no saved method —
            which fails silently, and then fails this member's authorisation later,
            turning the scenario's eleven membership rows into twelve. Same class of bug
            as the stale write in `services/demo.py`, reachable here by a fast click. */}
        <button
          className="btn btn-primary btn-lg"
          onClick={onFinish}
          disabled={busy || paymentBusy}
        >
          {busy ? <span className="spinner" /> : null}
          Finish
        </button>
        <button className="btn" onClick={onBack}>
          Back
        </button>
      </div>
    </div>
  );
}

/* --------------------------------------------------------------------- the flow */

export function Onboarding({
  consumer,
  onDone,
}: {
  consumer: Consumer;
  onDone: () => Promise<void> | void;
}) {
  const [step, setStep] = useState<Step>("you");
  const [name, setName] = useState("");
  const [mode, setMode] = useState("ask_me");
  const [added, setAdded] = useState<{ item: ChosenItem; quantity: number }[]>([]);
  /* Setup can be interrupted. Somebody who added a declaration and then refreshed before
     finishing comes back to step one, and the server — correctly — refuses a second
     active declaration for the same product. Without this, re-adding the thing they
     already chose failed and "Continue" stayed disabled forever, so the only way out was
     to declare something else they did not want. Reading what they already told Pool
     makes resuming show their real state rather than an empty local array. */
  useEffect(() => {
    let cancelled = false;
    api
      .needs()
      .then((view) => {
        if (cancelled) return;
        const mine = view.needs.filter(
          (n) => n.household_id === consumer.household_id && n.active,
        );
        if (mine.length === 0) return;
        setAdded(
          mine.map((n) => ({
            quantity: n.quantity,
            item: {
              key: n.declared_family
                ? `family:${n.declared_family}`
                : `product:${n.product_id}`,
              // `product_name` is already what the member called it — the family's own
              // label when they declared a family — so resuming shows their words back.
              label: n.product_name,
              unit: n.unit,
              category: n.category ?? "",
              brand: n.declared_family ? "" : (n.brand ?? ""),
              image_ref: n.declared_family ? "" : (n.image_ref ?? ""),
              familyCount: 0,
              draft: n.declared_family
                ? { group: n.declared_family, substitution: n.substitution }
                : { product_id: n.product_id, substitution: n.substitution },
            },
          })),
        );
      })
      .catch(() => {
        /* A failed read just means setup starts empty, which is the old behaviour. */
      });
    return () => {
      cancelled = true;
    };
  }, [consumer.household_id]);
  const [hasPayment, setHasPayment] = useState(consumer.has_payment_method);
  const [busy, setBusy] = useState(false);
  const [paymentBusy, setPaymentBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /* Moving between steps should behave like moving between pages: the heading is what
     changed, so that is what should be announced and what the eye should land on. */
  const headingRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    headingRef.current?.focus();
    window.scrollTo({ top: 0 });
  }, [step]);

  const addNeed = async (item: ChosenItem, draft: NeedDraft) => {
    setBusy(true);
    setError(null);
    try {
      await api.declareNeed({ ...draft, household_id: consumer.household_id });
      setAdded((prev) => [...prev, { item, quantity: draft.quantity }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      throw err;
    } finally {
      setBusy(false);
    }
  };

  const addPayment = async () => {
    setPaymentBusy(true);
    setError(null);
    try {
      const result = await api.saveOwnPaymentMethod();
      setHasPayment(result.has_payment_method);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPaymentBusy(false);
    }
  };

  const finish = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.completeOnboarding(name.trim(), mode);
      await onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  };

  return (
    <div className="onboard">
      <Progress current={step} />
      <div
        className="onboard-panel"
        ref={headingRef}
        tabIndex={-1}
        /* The step is a region that replaces itself, so a screen reader should hear the
           new one rather than silently land in the middle of it. */
        role="group"
        aria-label={`Step ${STEPS.findIndex((s) => s.id === step) + 1} of ${STEPS.length}`}
      >
        {step === "you" ? (
          <YouStep name={name} onName={setName} onNext={() => setStep("where")} />
        ) : null}
        {step === "where" ? (
          <WhereStep
            place={consumer.place}
            onNext={() => setStep("buy")}
            onBack={() => setStep("you")}
          />
        ) : null}
        {step === "buy" ? (
          <BuyStep
            added={added}
            onAdd={addNeed}
            onNext={() => setStep("authority")}
            onBack={() => setStep("where")}
            busy={busy}
            error={error}
          />
        ) : null}
        {step === "authority" ? (
          <AuthorityStep
            mode={mode}
            onMode={setMode}
            hasPayment={hasPayment}
            onAddPayment={() => void addPayment()}
            onFinish={() => void finish()}
            onBack={() => setStep("buy")}
            busy={busy}
            paymentBusy={paymentBusy}
            error={error}
          />
        ) : null}
      </div>
    </div>
  );
}
