/* Needs — the only thing a member ever has to do.
 *
 * Yours first, because that is the part that is actually yours. The community's standing
 * needs sit underneath, because seeing that thirty-three of them exist and none of them
 * are organised into anything is the whole premise of the product.
 *
 * This is also the one screen where a visitor *acts as* a member rather than watching
 * one. Declaring a need is the primary user input of the entire system — everything the
 * agent later does is downstream of standing declarations nobody coordinated — so it has
 * to be performable here, not merely described. The form writes through the real API and
 * the list is re-read from the server afterwards; nothing below keeps its own copy of
 * what a need is.
 *
 * What this deliberately is not: there is no way to invite anyone, name a group, or see
 * who else wants the same thing before Pool has found them. A need is a statement about
 * one household. Adding a "buy this with your neighbours" affordance here would be the
 * product failure the whole thesis is built against.
 */

import { useCallback, useEffect, useState } from "react";
import {
  NeedDraft,
  NeedLimits,
  NeedOutlook,
  NeedRow,
  api,
  shortDateOnly,
} from "../api";
import { ChosenCard, ProductSearch } from "../product-search";
import {
  FlexibilityContext,
  NeedPreferences,
  PreferenceQuestion,
  Reconciliation,
} from "../api";
import { ChosenItem, Picked, asChosen, defaultQuantity } from "../chosen";
import { EXACT } from "../preference-answers";
import { Preferences } from "../preferences";
import { useClarification } from "../use-clarification";
import { categoryTone, productImage, productInitials } from "../products";
import { Block, Chip, CoordinatorWait, Empty, IconArrowRight } from "../ui";

/** Substitution preferences, in the member's words.
 *
 *  Each value is a `SubstitutionPolicy` the deterministic matcher reads — the model
 *  never decides two products are "close enough". The two policies that take an explicit
 *  allowlist (`approved_products`, `approved_brands`) are deliberately absent: this form
 *  collects no allowlist, and offering a setting whose data the form cannot supply would
 *  be a control that silently means nothing. */
const SUBSTITUTION: { value: string; label: string }[] = [
  { value: "exact_only", label: "This exact product only" },
  { value: "same_product_other_variant", label: "Same brand — another flavour or scent is fine" },
  { value: "structured_category_match", label: "Any equivalent product in the same category" },
];

const DAY_MS = 24 * 60 * 60 * 1000;

function isoInDays(days: number): string {
  return new Date(Date.now() + days * DAY_MS).toISOString().slice(0, 10);
}

function daysUntil(iso: string): number {
  const then = new Date(`${iso}T00:00:00`).getTime();
  return Math.max(0, Math.round((then - new Date().setHours(0, 0, 0, 0)) / DAY_MS));
}

/** How early Pool may buy, derived from the two things a member actually said.
 *
 *  "I need it by the 3rd" already carries the answer: any time between now and then is
 *  fine. So the default window is the whole of it, clamped to one restock cycle because
 *  buying more than a cycle ahead would be storing goods the household never agreed to
 *  hold (§24, MAX_FLEXIBILITY_MULTIPLE). Somebody who wants a narrower window says so in
 *  the advanced section; nothing is assumed on their behalf beyond the plain reading of
 *  the date they gave. */
function defaultFlexibility(nextNeededIso: string, cadenceDays: number): number {
  return Math.min(daysUntil(nextNeededIso), Math.max(0, cadenceDays));
}

const DEFAULT_CADENCE = 30;
const DEFAULT_NEXT_NEEDED_DAYS = 14;

function blankDraft(householdId: string): NeedDraft {
  const nextNeeded = isoInDays(DEFAULT_NEXT_NEEDED_DAYS);
  return {
    household_id: householdId,
    // Empty until a product has been chosen. The form will not submit without one, and
    // pre-selecting somebody else's first catalogue row was the old behaviour this
    // screen exists to remove.
    product_id: "",
    quantity: defaultQuantity(),
    cadence_days: DEFAULT_CADENCE,
    expected_next_need_date: nextNeeded,
    flexibility_days: defaultFlexibility(nextNeeded, DEFAULT_CADENCE),
    routine_lead_days: 7,
    min_savings_pct: 15,
    max_spend_cents: 12000,
    substitution: "exact_only",
    active: true,
  };
}

function draftFrom(need: NeedRow): NeedDraft {
  return {
    household_id: need.household_id,
    product_id: need.product_id,
    quantity: need.quantity,
    cadence_days: need.cadence_days,
    expected_next_need_date: need.expected_next_need_date,
    flexibility_days: need.flexibility_days,
    routine_lead_days: need.routine_lead_days,
    min_savings_pct: need.min_savings_pct,
    max_spend_cents: need.max_spend_cents,
    substitution: need.substitution,
    active: need.active,
  };
}

/* ------------------------------------------------------------------ the form */

function NeedForm({
  draft,
  chosen,
  limits,
  busy,
  error,
  editing,
  onChange,
  onChooseProduct,
  onClearProduct,
  onUnresolved,
  onSubmit,
  onCancel,
  onRetire,
  questions,
  preferences,
  onPreferences,
  noun,
  flexibility,
  planning,
  planned,
}: {
  draft: NeedDraft;
  /** What the member picked, as a card renders it. Null while adding, before anything
   *  has been chosen. A family and a product are both this shape by design. */
  chosen: ChosenItem | null;
  limits: NeedLimits | null;
  busy: boolean;
  error: string | null;
  editing: boolean;
  onChange: (next: NeedDraft) => void;
  onChooseProduct: (picked: Picked) => void;
  onClearProduct: () => void;
  onUnresolved: (query: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
  onRetire: () => void;
  /** What this product can be asked about, as the server says. Empty for anything
   *  outside a curated family, which is when the older control appears instead. */
  questions: PreferenceQuestion[];
  preferences: NeedPreferences | null;
  onPreferences: (next: NeedPreferences) => void;
  /** Curated consumer noun for the product's family, or empty outside one. */
  noun: string;
  /** Counted demand either side of the choice, once somebody has made it. */
  flexibility: FlexibilityContext | null;
  planning: boolean;
  planned: boolean;
}) {
  /** Whether the member has narrowed the buy-early window by hand. Until they do, it
   *  tracks the date they gave — so changing "next needed" does not silently leave a
   *  stale window behind, and touching the control does not get overwritten. */
  const [flexTouched, setFlexTouched] = useState(false);

  const set = <K extends keyof NeedDraft>(key: K, value: NeedDraft[K]) =>
    onChange({ ...draft, [key]: value });

  /** Changing the date or the cycle re-derives the window, unless it has been set. */
  const setTiming = (next: NeedDraft) =>
    onChange(
      flexTouched
        ? next
        : {
            ...next,
            flexibility_days: defaultFlexibility(
              next.expected_next_need_date,
              next.cadence_days,
            ),
          },
    );

  const maxSpend = limits ? limits.max_spend_cents / 100 : 5000;
  const unit = chosen?.unit || "units";

  /* Step one. Nothing else is worth asking until Pool knows what the thing is. */
  if (!chosen) {
    return (
      <div className="need-form stack-sm">
        <ProductSearch
          onSelect={onChooseProduct}
          onUnresolved={onUnresolved}
          autoFocus
        />
        <div className="btn-row">
          <button className="btn" type="button" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <form
      className="need-form"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <div className="chosen-product">
        <ChosenCard item={chosen} />
        {editing ? null : (
          <button className="btn btn-sm btn-ghost" type="button" onClick={onClearProduct}>
            Change
          </button>
        )}
      </div>

      <div className="field-grid">
        <label className="field">
          <span className="field-label">How many</span>
          <div className="control-suffix">
            <input
              className="control"
              type="number"
              min={1}
              max={limits?.max_quantity ?? 100}
              value={draft.quantity}
              onChange={(e) => set("quantity", Number(e.target.value))}
              required
            />
            <span className="suffix">{unit}</span>
          </div>
        </label>

        <label className="field">
          <span className="field-label">You buy this about every</span>
          <div className="control-suffix">
            <input
              className="control"
              type="number"
              min={1}
              max={limits?.max_cadence_days ?? 365}
              value={draft.cadence_days}
              onChange={(e) =>
                setTiming({ ...draft, cadence_days: Number(e.target.value) })
              }
              required
            />
            <span className="suffix">days</span>
          </div>
        </label>

        <label className="field field-wide">
          <span className="field-label">When do you next need it?</span>
          <input
            className="control"
            type="date"
            value={draft.expected_next_need_date}
            onChange={(e) =>
              setTiming({ ...draft, expected_next_need_date: e.target.value })
            }
            required
          />
          {/* The one genuinely load-bearing consequence, stated in plain words rather
              than left implicit in a number. This window is the permission the timing
              engine reads when it decides whether demand may be pulled forward (§24),
              so it is never hidden — only its exact size is. */}
          <span className="field-note">
            {draft.flexibility_days > 0
              ? `Pool may buy any time in the ${draft.flexibility_days} days before that, if it saves money.`
              : "Pool will only buy on that date — never earlier."}
          </span>
        </label>

        {/* Out of the advanced drawer, deliberately.
            This is the one setting that decides whose demand may combine with whose, and
            it is the difference between joining an order and being told nothing can be
            done. Somebody who never opens a collapsed section never sees a choice they
            have already effectively made — and for a product Pool cannot source, it is
            the *only* thing that could change the answer.

            Two shapes, and which one appears is the server's answer rather than this
            file's. A product in a curated family can be asked about *itself* — grind,
            caffeine, roast — so the member answers questions about coffee instead of
            picking a substitution policy out of a list. Everything else keeps the older
            control, because there is nothing authoritative to ask about it and inventing
            a question would be inventing a fact (§21). */}
        {questions.length > 0 || preferences ? (
          <Preferences
            questions={questions}
            value={preferences ?? EXACT}
            onChange={onPreferences}
            disabled={busy}
            noun={noun}
            flexibility={flexibility}
            loading={planning}
            planned={planned}
          />
        ) : (
          <label className="field field-wide">
            <span className="field-label">Would another product do?</span>
            <select
              className="control"
              value={draft.substitution}
              onChange={(e) => set("substitution", e.target.value)}
            >
              {SUBSTITUTION.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
            <span className="field-note">
              {chosen.sourceable === false ? (
                <>
                  Pool has no bulk supplier for this exact product yet, so it cannot form an
                  order for it on its own. Your declaration is still recorded, and widening
                  this is the only thing that would change that — your call, not Pool&apos;s.
                </>
              ) : draft.substitution === "exact_only" ? (
                "Only this exact product will ever be bought for you."
              ) : (
                "Pool may use another product that structurally matches this rule — and always tells you which."
              )}
            </span>
          </label>
        )}
      </div>

      {/* Available rather than absent. These already hold safe values, the deterministic
          engine takes the stricter of these and the member's standing policy, and nobody
          setting up a restock reminder wants to think about a savings floor first.
          Collapsing a control must never quietly change what it means (AGENTS.md §5). */}
      <details className="inset need-advanced">
        <summary className="small">
          <strong>Fine-tune when Pool may act on this need</strong>
          <span className="small faint">
            {" "}
            — never below {draft.min_savings_pct}% saving, never above $
            {(draft.max_spend_cents / 100).toFixed(2)}
          </span>
        </summary>
        <div className="field-grid" style={{ marginTop: 14 }}>
          <label className="field">
            <span className="field-label">May buy this many days early</span>
            <input
              className="control"
              type="number"
              min={0}
              max={draft.cadence_days}
              value={draft.flexibility_days}
              onChange={(e) => {
                setFlexTouched(true);
                set("flexibility_days", Number(e.target.value));
              }}
            />
            <span className="field-note">
              {draft.flexibility_days === 0
                ? "Never bought early."
                : `Never more than ${draft.flexibility_days} days ahead of when you need it.`}
            </span>
          </label>

          <label className="field">
            <span className="field-label">You normally restock this far ahead</span>
            <div className="control-suffix">
              <input
                className="control"
                type="number"
                min={0}
                max={draft.cadence_days}
                value={draft.routine_lead_days}
                onChange={(e) => set("routine_lead_days", Number(e.target.value))}
              />
              <span className="suffix">days</span>
            </div>
          </label>

          <label className="field">
            <span className="field-label">Won't join below … % saving</span>
            <input
              className="control"
              type="number"
              min={0}
              max={limits?.max_min_savings_pct ?? 90}
              value={draft.min_savings_pct}
              onChange={(e) => set("min_savings_pct", Number(e.target.value))}
            />
          </label>

          <label className="field">
            <span className="field-label">Never spend more than</span>
            <input
              className="control"
              type="number"
              min={1}
              max={maxSpend}
              step="0.01"
              value={(draft.max_spend_cents / 100).toFixed(2)}
              onChange={(e) =>
                set("max_spend_cents", Math.round(Number(e.target.value) * 100))
              }
              required
            />
            <span className="field-note">
              Checked against the exact final price, not an estimate.
            </span>
          </label>

        </div>
      </details>

      {error ? <p className="form-error">{error}</p> : null}

      <div className="btn-row">
        <button className="btn btn-primary" type="submit" disabled={busy}>
          {busy ? <span className="spinner" /> : null}
          {editing ? "Save changes" : "Add this need"}
        </button>
        <button className="btn" type="button" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
        {editing ? (
          <button className="btn btn-ghost" type="button" onClick={onRetire} disabled={busy}>
            Stop buying this
          </button>
        ) : null}
      </div>
      <p className="tiny faint">
        Saving this commits nothing and joins nothing. It tells Pool what to watch for.
      </p>
    </form>
  );
}
/** The same photograph the member picked from, at row scale. Falls back to a category
 *  tile, which is the ordinary state for curated household goods rather than an error. */
/** What changing your mind did to orders you were already in.
 *
 *  Both directions, and neither of them is a model's decision: the same compatibility
 *  evaluator that lets somebody into an order is the one that takes them out, re-run
 *  against the declaration they have just saved. It is shown because the alternative is
 *  an order silently vanishing from Home — or silently reappearing — with nothing on
 *  screen connecting either to the edit that caused it.
 *
 *  A pool past the point where leaving is free is reported as refused rather than
 *  forced. A standing preference is not a cancellation policy, and Pool does not undo a
 *  payment that has already been captured because somebody edited a checkbox.
 */
function Reconciled({ rows }: { rows: Reconciliation[] }) {
  return (
    <div className="panel-pad reconciled">
      <p className="small">
        <strong>What that changed.</strong>
      </p>
      <ul className="small muted reconciled-list">
        {rows.map((row) => (
          <li key={row.pool_id}>
            {row.restored ? (
              <>
                Your rules allow it again, so Pool put you back into the order it had
                taken you out of. Nothing is charged and nothing is committed — you will
                be asked before anything is.
              </>
            ) : row.withdrawn ? (
              <>
                Pool took you out of an order your new rules no longer allow. Nobody was
                charged, and the other members' order is unaffected.
              </>
            ) : (
              <>
                One order you are in has already been paid for and placed with the
                supplier, so Pool left it exactly as it is. Your new rules apply from the
                next one.
              </>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function NeedThumb({ need }: { need: NeedRow }) {
  const src = productImage(need.image_ref ?? "");
  return (
    <span className="need-thumb" aria-hidden="true">
      {src ? (
        <img src={src} alt="" loading="lazy" decoding="async" />
      ) : (
        <span
          className="product-thumb-fallback"
          style={{ background: categoryTone(need.category ?? "") }}
        >
          {productInitials(need.brand ?? "", need.product_name)}
        </span>
      )}
    </span>
  );
}

/* ------------------------------------------------------------------ the view */

export function Needs({
  identity,
  communityName,
  initialProduct,
  onConsumeInitialProduct,
  onFind,
  onWorldChanged,
  running,
  hasPool,
  outlook,
  liveDiscovery,
  region,
}: {
  identity: { id: string; display_name: string };
  communityName: string;
  /** A product already chosen on Home, so the member does not search twice. */
  initialProduct: Picked | null;
  onConsumeInitialProduct: () => void;
  onFind: () => void;
  /** Something a save did to the deterministic picture that this view does not own —
   *  the outlook beside every row, and whether this member is in an order at all.
   *  Re-read from the server rather than patched here. */
  onWorldChanged: () => void;
  running: boolean;
  /** What the deterministic evaluator says about each declaration *right now*.
   *
   *  Explicitly a current outlook and not a run's finding: it is recomputed on every
   *  read, creates nothing and commits nothing, and it lives here rather than on Home
   *  because Home's job before a run is to pose the question rather than answer it. The
   *  label beside it says which of the two this is, because "Pool evaluated this and
   *  declined" and "here is how it looks as things stand" are different claims. */
  outlook: NeedOutlook[];
  /** Whether *this member* is in a pool — the server's answer, not "does any pool
   *  exist in the workspace". A community order formed for ten other students is not a
   *  reason to stop offering this member the one action they have. */
  hasPool: boolean;
  liveDiscovery: boolean;
  region: string | null;
}) {
  const [needs, setNeeds] = useState<NeedRow[] | null>(null);
  const [limits, setLimits] = useState<NeedLimits | null>(null);
  const [showAll, setShowAll] = useState(false);
  /** `null` = the form is closed. A string = editing that need. "" = adding a new one. */
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<NeedDraft | null>(null);
  /** The chosen product, as a card renders it. Held beside the draft because the draft
   *  carries only the id the server needs, and the id is the one thing never shown. */
  const [chosen, setChosen] = useState<ChosenItem | null>(null);
  /** What the chosen product can be asked about, what the member answered, and what
   *  each side of the choice reaches. All of it server-owned, and the hook is the only
   *  thing that can buy a model run — see `use-clarification.ts` for the rules. */
  const clarification = useClarification(chosen?.draft.product_id);
  const { questions, preferences, noun, flexibility, planned, planId, planning } =
    clarification;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /** What the last save did to orders this member was already in. Server-decided, both
   *  directions, and shown because an edit that quietly removed somebody from an order —
   *  or quietly put them back — is a consequence they are owed. */
  const [reconciled, setReconciled] = useState<Reconciliation[]>([]);

  /** Re-reads from the server rather than patching local state with what was sent.
   *  The declaration the member sees has to be the one the store actually holds —
   *  that is the same rule the pool views follow, and it is why a rejected field
   *  cannot linger on screen looking saved. */
  const reload = useCallback(async () => {
    const view = await api.needs();
    setNeeds(view.needs);
    setLimits(view.limits);
    return view;
  }, []);

  useEffect(() => {
    reload().catch(() => setNeeds([]));
  }, [reload]);

  /* Arriving from Home with a product already picked opens the form on step two. The
     hand-off is consumed immediately so a later navigation back here starts clean. */
  useEffect(() => {
    if (!initialProduct) return;
    setError(null);
    setEditingId("");
    const item = asChosen(initialProduct);
    setChosen(item);
    setDraft({ ...blankDraft(identity.id), ...item.draft });
    onConsumeInitialProduct();
  }, [initialProduct, identity.id, onConsumeInitialProduct]);

  if (needs === null) return <Empty>Loading…</Empty>;

  const mine = needs
    .filter((n) => n.household_id === identity.id && n.active)
    .sort((a, b) => a.expected_next_need_date.localeCompare(b.expected_next_need_date));
  /* Active only, on both sides. A retired declaration is not a standing need, so
     counting it under "standing needs across the community" would overstate the very
     number this screen exists to make legible — and it is no longer demand the matcher
     will act on either. */
  const others = needs.filter((n) => n.household_id !== identity.id && n.active);
  const standing = needs.filter((n) => n.active);
  const byNeed = new Map(outlook.map((o) => [o.need_id, o]));

  const openAdd = () => {
    setError(null);
    setReconciled([]);
    setEditingId("");
    setChosen(null);
    setDraft(blankDraft(identity.id));
  };

  const openEdit = (need: NeedRow) => {
    setError(null);
    setReconciled([]);
    setEditingId(need.need_id);
    // Editing keeps the product fixed, so the card is rebuilt from what the server
    // already told us about this declaration rather than searched for again.
    // Editing keeps the choice fixed, so the card is rebuilt from what the server
    // already said about this declaration rather than searched for again — including
    // whether it was a family, which is the difference between reopening "Coffee" and
    // reopening the exemplar bag behind it.
    setChosen(
      need.declared_family
        ? {
            key: `family:${need.declared_family}`,
            label: need.product_name,
            unit: need.unit,
            category: need.category ?? "",
            brand: "",
            image_ref: "",
            familyCount: 0,
            draft: { group: need.declared_family, substitution: need.substitution },
          }
        : {
            key: `product:${need.product_id}`,
            label: need.product_name,
            unit: need.unit,
            category: need.category ?? "",
            brand: need.brand ?? "",
            image_ref: need.image_ref ?? "",
            familyCount: 0,
            draft: { product_id: need.product_id, substitution: need.substitution },
          },
    );
    setDraft(draftFrom(need));
    /* On what they said, not on defaults. The server owns the mapping in both
       directions, so this is a read rather than a reconstruction — and it is what stops
       an edit opened for an unrelated reason from quietly re-adding a requirement the
       member had dropped. */
    clarification.load(need.preferences);
  };

  const close = () => {
    setEditingId(null);
    setDraft(null);
    setChosen(null);
    setError(null);
  };

  const chooseProduct = (picked: Picked) => {
    const item = asChosen(picked);
    setChosen(item);
    // Exactly one of the two travels, because the server refuses both.
    setDraft((d) =>
      d
        ? { ...d, product_id: undefined, group: undefined, ...item.draft }
        : d,
    );
  };

  const clearProduct = () => {
    setChosen(null);
    clarification.reset();
    setDraft((d) => (d ? { ...d, product_id: undefined, group: undefined } : d));
  };


  /** Something the catalogue does not have. The server stores it with no substitute
   *  group and no supplier, so the need is real and no pool can form for it yet. */
  const recordUnresolved = async (query: string) => {
    setBusy(true);
    setError(null);
    try {
      chooseProduct({ kind: "product", product: await api.customProduct(query) });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const save = async (override?: Partial<NeedDraft>) => {
    if (!draft) return;
    /* Answers, not a policy. The server decides what they mean, and the older
       `substitution` value is dropped when they travel so there is exactly one source
       for what this member consented to.

       `planId` travels beside them as lineage: which plan put *these* questions on the
       screen. Empty when nothing was planned for this revision — reopening an edit shows
       the whole approved set, so crediting it to the last plan made would be recording a
       plan that shaped nothing. */
    const answered = preferences
      ? { preferences, substitution: undefined, clarification_plan_id: planId }
      : {};
    const payload = { ...draft, ...answered, ...override };
    setBusy(true);
    setError(null);
    try {
      const saved = editingId
        ? await api.amendNeed(editingId, payload)
        : await api.declareNeed(payload);
      setReconciled(saved.reconciled ?? []);
      await reload();
      /* The outlook beside every row, and whether this member is in an order, are the
         server's answers and both can have moved. Asking again is the only way this
         page tells the truth a second after a save. */
      onWorldChanged();
      close();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <header className="stack-sm">
        <h1 className="title">What you buy</h1>
        <p className="lede">
          Tell Pool what you restock and roughly when. Saving a need never commits money
          — it is what lets Pool notice that other people near you need the same thing.
        </p>
      </header>

      <section className="panel">
        <div className="panel-head">
          <h2>Yours</h2>
          <span className="spacer" />
          <span className="tiny faint">{identity.display_name}</span>
          {editingId === null ? (
            <button className="btn btn-sm btn-primary" onClick={openAdd}>
              Add a need
            </button>
          ) : null}
        </div>

        {editingId === "" && draft ? (
          <div className="panel-pad">
            <NeedForm
              draft={draft}
              chosen={chosen}
              limits={limits}
              busy={busy}
              error={error}
              editing={false}
              onChange={setDraft}
              onChooseProduct={chooseProduct}
              onClearProduct={clearProduct}
              onUnresolved={recordUnresolved}
              onSubmit={() => void save()}
              onCancel={close}
              onRetire={close}
              questions={questions}
              preferences={preferences}
              onPreferences={clarification.answer}
              noun={noun}
              flexibility={flexibility}
              planning={planning}
              planned={planned}
            />
          </div>
        ) : null}

        {reconciled.length > 0 ? <Reconciled rows={reconciled} /> : null}

        {mine.length === 0 && editingId !== "" ? (
          <Empty>
            Nothing declared yet. Add what you buy anyway; Pool watches from there.
          </Empty>
        ) : (
          <div className="rows">
            {mine.map((n) =>
              editingId === n.need_id && draft ? (
                <div key={n.need_id} className="row-editing">
                  <NeedForm
                    draft={draft}
                    chosen={chosen}
                    limits={limits}
                    busy={busy}
                    error={error}
                    editing
                    onChange={setDraft}
                    onChooseProduct={chooseProduct}
                    onClearProduct={clearProduct}
                    onUnresolved={recordUnresolved}
                    onSubmit={() => void save()}
                    onCancel={close}
                    onRetire={() => void save({ active: false })}
                    questions={questions}
                    preferences={preferences}
                    onPreferences={clarification.answer}
                    noun={noun}
                    flexibility={flexibility}
                    planning={planning}
                    planned={planned}
                  />
                </div>
              ) : (
                <div key={n.need_id} className="row">
                  <NeedThumb need={n} />
                  <div className="row-body">
                    <div className="row-title">
                      {n.brand ? <span className="need-brand">{n.brand}</span> : null}
                      {n.product_name}
                      {n.variant ? <span className="need-variant">{n.variant}</span> : null}
                      {n.flexibility_days > 0 ? (
                        <Chip tone="ok">may buy {n.flexibility_days}d early</Chip>
                      ) : (
                        <Chip>never early</Chip>
                      )}
                    </div>
                    <div className="tiny muted">
                      {n.quantity} {n.unit} · about every {n.cadence_days} days · you
                      normally restock {n.routine_lead_days} days ahead
                    </div>
                    <div className="tiny faint">
                      Will not join below {n.min_savings_pct}% saving, and never above{" "}
                      {n.max_spend_display}
                    </div>
                    {byNeed.get(n.need_id) ? (
                      <div className="tiny muted" style={{ marginTop: 4 }}>
                        <span className="outlook-tag">As things stand</span>{" "}
                        {byNeed.get(n.need_id)!.reason}
                      </div>
                    ) : null}
                  </div>
                  <div className="row-tail">
                    <div className="fact-value">{shortDateOnly(n.expected_next_need_date)}</div>
                    <div className="tiny faint">next needed</div>
                    <button
                      className="btn btn-sm"
                      style={{ marginTop: 8 }}
                      onClick={() => openEdit(n)}
                      disabled={editingId !== null}
                    >
                      Change
                    </button>
                  </div>
                </div>
              ),
            )}
          </div>
        )}
      </section>

      <Block
        title={`Standing needs across ${communityName}`}
        aside={
          <button className="btn btn-sm" onClick={() => setShowAll((v) => !v)}>
            {showAll ? "Hide" : `Show all ${standing.length}`}
          </button>
        }
      >
        <p className="small muted prose">
          {standing.length} independent declarations. Pool finds the overlap; members do
          not create or organise a group.
        </p>
        {!hasPool ? (
          <div className="stack-sm" style={{ marginTop: 14 }}>
            <div className="btn-row">
              <button className="btn btn-primary" onClick={onFind} disabled={running}>
                {running ? <span className="spinner" /> : null}
                {running ? "Pool is checking…" : "Ask Pool to check now"}
                {running ? null : <IconArrowRight />}
              </button>
            </div>
            {running ? <CoordinatorWait live={liveDiscovery} region={region} /> : null}
          </div>
        ) : null}
        {showAll ? (
          <div className="panel" style={{ marginTop: 16 }}>
            <div className="table-scroll">
              <table className="data">
                <thead>
                  <tr>
                    <th>Member</th>
                    <th>Product</th>
                    <th className="r">Qty</th>
                    <th>Needs it by</th>
                    <th className="r">Restock lead</th>
                    <th className="r">Will buy early</th>
                    <th className="r">Min saving</th>
                    <th className="r">Max spend</th>
                  </tr>
                </thead>
                <tbody>
                  {others.map((n) => (
                    <tr key={n.need_id}>
                      <td>{n.household_name}</td>
                      <td>{n.product_name}</td>
                      <td className="r">
                        {n.quantity} {n.unit}
                      </td>
                      <td>{shortDateOnly(n.expected_next_need_date)}</td>
                      <td className="r">{n.routine_lead_days}d</td>
                      <td className="r">{n.flexibility_days}d</td>
                      <td className="r">{n.min_savings_pct}%</td>
                      <td className="r">{n.max_spend_display}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </Block>
    </div>
  );
}
