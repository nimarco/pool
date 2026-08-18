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
import { NeedDraft, NeedLimits, NeedRow, ProductRow, api, shortDateOnly } from "../api";
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

function blankDraft(householdId: string, products: ProductRow[]): NeedDraft {
  return {
    household_id: householdId,
    product_id: products[0]?.product_id ?? "",
    quantity: 2,
    cadence_days: 30,
    expected_next_need_date: isoInDays(21),
    flexibility_days: 7,
    routine_lead_days: 5,
    min_savings_pct: 15,
    max_spend_cents: 4000,
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
  products,
  limits,
  busy,
  error,
  editing,
  onChange,
  onSubmit,
  onCancel,
  onRetire,
}: {
  draft: NeedDraft;
  products: ProductRow[];
  limits: NeedLimits | null;
  busy: boolean;
  error: string | null;
  editing: boolean;
  onChange: (next: NeedDraft) => void;
  onSubmit: () => void;
  onCancel: () => void;
  onRetire: () => void;
}) {
  const set = <K extends keyof NeedDraft>(key: K, value: NeedDraft[K]) =>
    onChange({ ...draft, [key]: value });
  const maxSpend = limits ? limits.max_spend_cents / 100 : 5000;

  return (
    <form
      className="need-form"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <div className="field-grid">
        <label className="field field-wide">
          <span className="field-label">What you buy</span>
          <select
            className="control"
            value={draft.product_id}
            onChange={(e) => set("product_id", e.target.value)}
            required
          >
            {products.map((p) => (
              <option key={p.product_id} value={p.product_id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span className="field-label">How many</span>
          <input
            className="control"
            type="number"
            min={1}
            max={limits?.max_quantity ?? 100}
            value={draft.quantity}
            onChange={(e) => set("quantity", Number(e.target.value))}
            required
          />
        </label>

        <label className="field">
          <span className="field-label">Every … days</span>
          <input
            className="control"
            type="number"
            min={1}
            max={limits?.max_cadence_days ?? 365}
            value={draft.cadence_days}
            onChange={(e) => set("cadence_days", Number(e.target.value))}
            required
          />
        </label>

        <label className="field">
          <span className="field-label">Next needed</span>
          <input
            className="control"
            type="date"
            value={draft.expected_next_need_date}
            onChange={(e) => set("expected_next_need_date", e.target.value)}
            required
          />
        </label>

        <label className="field">
          <span className="field-label">May buy this many days early</span>
          <input
            className="control"
            type="number"
            min={0}
            max={draft.cadence_days}
            value={draft.flexibility_days}
            onChange={(e) => set("flexibility_days", Number(e.target.value))}
          />
          <span className="field-note">
            {draft.flexibility_days === 0
              ? "Never bought early."
              : `May be bought up to ${draft.flexibility_days} days early — never earlier.`}
          </span>
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
          <span className="field-note">Checked against the exact final price, not an estimate.</span>
        </label>

        <label className="field field-wide">
          <span className="field-label">Substitutes</span>
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
        </label>
      </div>

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
    </form>
  );
}

/* ------------------------------------------------------------------ the view */

export function Needs({
  identity,
  communityName,
  onFind,
  running,
  hasPool,
  liveDiscovery,
}: {
  identity: { id: string; display_name: string };
  communityName: string;
  onFind: () => void;
  running: boolean;
  hasPool: boolean;
  liveDiscovery: boolean;
}) {
  const [needs, setNeeds] = useState<NeedRow[] | null>(null);
  const [products, setProducts] = useState<ProductRow[]>([]);
  const [limits, setLimits] = useState<NeedLimits | null>(null);
  const [showAll, setShowAll] = useState(false);
  /** `null` = the form is closed. A string = editing that need. "" = adding a new one. */
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<NeedDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** Re-reads from the server rather than patching local state with what was sent.
   *  The declaration the member sees has to be the one the store actually holds —
   *  that is the same rule the pool views follow, and it is why a rejected field
   *  cannot linger on screen looking saved. */
  const reload = useCallback(async () => {
    const view = await api.needs();
    setNeeds(view.needs);
    setProducts(view.products);
    setLimits(view.limits);
    return view;
  }, []);

  useEffect(() => {
    reload().catch(() => setNeeds([]));
  }, [reload]);

  if (needs === null) return <Empty>Loading…</Empty>;

  const mine = needs
    .filter((n) => n.household_id === identity.id && n.active)
    .sort((a, b) => a.expected_next_need_date.localeCompare(b.expected_next_need_date));
  const others = needs.filter((n) => n.household_id !== identity.id);

  const openAdd = () => {
    setError(null);
    setEditingId("");
    setDraft(blankDraft(identity.id, products));
  };

  const openEdit = (need: NeedRow) => {
    setError(null);
    setEditingId(need.need_id);
    setDraft(draftFrom(need));
  };

  const close = () => {
    setEditingId(null);
    setDraft(null);
    setError(null);
  };

  const save = async (override?: Partial<NeedDraft>) => {
    if (!draft) return;
    const payload = { ...draft, ...override };
    setBusy(true);
    setError(null);
    try {
      if (editingId) await api.amendNeed(editingId, payload);
      else await api.declareNeed(payload);
      await reload();
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
        <h1 className="title">What you buy anyway</h1>
        <p className="lede">
          Set your restock cadence and any days-early window. Saving a need never commits
          money; only that window permits Pool to bring it forward.
        </p>
      </header>

      <section className="panel">
        <div className="panel-head">
          <h3>Yours</h3>
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
              products={products}
              limits={limits}
              busy={busy}
              error={error}
              editing={false}
              onChange={setDraft}
              onSubmit={() => void save()}
              onCancel={close}
              onRetire={close}
            />
          </div>
        ) : null}

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
                    products={products}
                    limits={limits}
                    busy={busy}
                    error={error}
                    editing
                    onChange={setDraft}
                    onSubmit={() => void save()}
                    onCancel={close}
                    onRetire={() => void save({ active: false })}
                  />
                </div>
              ) : (
                <div key={n.need_id} className="row">
                  <div className="row-body">
                    <div className="row-title">
                      {n.product_name}
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
            {showAll ? "Hide" : `Show all ${needs.length}`}
          </button>
        }
      >
        <p className="small muted prose">
          {needs.length} independent declarations. Pool finds the overlap; members do not
          create or organise a group.
        </p>
        {!hasPool ? (
          <div className="stack-sm" style={{ marginTop: 14 }}>
            <div className="btn-row">
              <button className="btn btn-primary" onClick={onFind} disabled={running}>
                {running ? <span className="spinner" /> : null}
                {running ? "Coordinator running" : "Find opportunities"}
                {running ? null : <IconArrowRight />}
              </button>
            </div>
            {running ? <CoordinatorWait live={liveDiscovery} /> : null}
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
