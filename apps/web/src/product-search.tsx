/* Telling Pool what you buy.
 *
 * This is the first thing a member does and, for most of them, the only thing they will
 * ever do. It has to behave like a consumer app — type a few words, recognise the thing,
 * tap it — and not like the procurement form the rest of the system deserves.
 *
 * Design decisions worth keeping:
 *
 * **Recognition, not recall.** Results are cards with the actual photograph, because a
 * person identifies the tub in their cupboard by sight far faster than by reading a SKU
 * description. The internal `product_id` is sent back to the server and never shown.
 *
 * **No model on the keystroke path.** Ranking happens server-side against a bundled
 * snapshot, by a pure function. That keeps it free, instant, reproducible in a demo, and
 * — the part that actually matters — keeps a language model from being one step away
 * from deciding which product somebody is buying (AGENTS.md §3.3, §5). Interpretation
 * gets to be forgiving because the member still confirms, and because compatibility is
 * decided later from structure by `domain.substitution`.
 *
 * **Search is not a shop.** No prices, no availability, no "add to cart". Choosing a
 * product states what you buy anyway; it commits nothing and joins nothing.
 *
 * **The family comes first, because that is usually the sentence.** Typing `coffee`
 * used to return four bags of coffee and a Chobani coffee creamer, and the member's
 * only way of saying "I buy coffee" was to pick one brand and hope their neighbours had
 * picked the same one. They had not: twelve people buying coffee across three brands
 * produced no order at all, against a supplier minimum they cleared twice over. So a
 * matched family is offered as the primary answer and the exact products sit behind a
 * disclosure — available, unchanged, and one click away for somebody who means one bag.
 *
 * Naming a brand offers no family. Somebody typing `pike place` has already told Pool
 * which product they want, and putting "Coffee" above it would be the search widening
 * their authority on their behalf.
 */

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { CatalogAttribution, FamilyCandidate, ProductCandidate, api } from "./api";
import { ChosenItem, Picked } from "./chosen";
import { categoryTone, productImage, productInitials } from "./products";

/** Long enough that a fast typist makes one request per word rather than per letter,
 *  short enough that the list feels like it is keeping up. */
const DEBOUNCE_MS = 180;
const MIN_CHARS = 2;

/* --------------------------------------------------------------------- one card */

export function ProductCard({
  product,
  selected,
  onSelect,
  id,
}: {
  product: ProductCandidate;
  selected?: boolean;
  onSelect?: () => void;
  id?: string;
}) {
  const src = productImage(product.image_ref);
  const secondary = [product.variant, product.display_size].filter(Boolean).join(" · ");
  const body = (
    <>
      <span className="product-thumb" aria-hidden="true">
        {src ? (
          /* Decorative: the name beside it already says what this is, so a screen
             reader announcing the filename would be pure noise. */
          <img src={src} alt="" loading="lazy" decoding="async" />
        ) : (
          <span
            className="product-thumb-fallback"
            style={{ background: categoryTone(product.category) }}
          >
            {productInitials(product.brand, product.name)}
          </span>
        )}
      </span>
      <span className="product-text">
        {product.brand ? <span className="product-brand">{product.brand}</span> : null}
        <span className="product-name">{product.name}</span>
        {secondary ? <span className="product-meta">{secondary}</span> : null}
        {/* Why this one is near the top. Pool holds a verified bulk quote for it, which
            is a fact about this deployment rather than about the product — so it is said
            plainly instead of being an unexplained ranking. Everything else in the list
            is equally real and equally declarable; Pool simply cannot buy it in bulk
            yet, and says so rather than quietly steering. */}
        {product.sourceable ? (
          <span className="product-sourceable">Pool can source this</span>
        ) : null}
      </span>
    </>
  );

  if (!onSelect) return <div className="product-card is-static">{body}</div>;
  /* The option *is* the target. A `role="option"` may not contain an interactive
     element, and the input keeps focus throughout — the combobox owns the keyboard and
     `aria-activedescendant` says which row is current — so a nested button would both
     break the pattern and steal the caret mid-word. `onMouseDown` is where the blur is
     prevented, because it fires before focus moves. */
  return (
    <li
      id={id}
      role="option"
      aria-selected={!!selected}
      className={`product-card${selected ? " is-active" : ""}`}
      onMouseDown={(event) => event.preventDefault()}
      onClick={onSelect}
    >
      {body}
    </li>
  );
}

/* ------------------------------------------------------------------ one family */

/** A product family, offered as the thing the member probably means.
 *
 *  Deliberately says how many products it covers rather than naming one of them. The
 *  count is the reassurance — it is what makes "Coffee" read as a real choice with a
 *  known scope rather than a vague one. */
export function FamilyCard({
  family,
  selected,
  onSelect,
  id,
}: {
  family: FamilyCandidate;
  selected?: boolean;
  onSelect: () => void;
  id?: string;
}) {
  return (
    <li
      id={id}
      role="option"
      aria-selected={!!selected}
      className={`family-card${selected ? " is-active" : ""}`}
      onMouseDown={(event) => event.preventDefault()}
      onClick={onSelect}
    >
      <span
        className="family-thumb"
        aria-hidden="true"
        style={{ background: categoryTone(family.category) }}
      />
      <span className="product-text">
        <span className="family-name">{family.label}</span>
        <span className="product-meta">
          Any of {family.product_count} — Pool buys whichever works out cheapest
        </span>
        {family.sourceable ? (
          <span className="product-sourceable">Pool can source this</span>
        ) : null}
      </span>
    </li>
  );
}

/* ------------------------------------------------------------------ the search */

/** The thing the member picked, shown back to them. One component, so a family and a
 *  product cannot drift into looking like different classes of choice. */
export function ChosenCard({ item }: { item: ChosenItem }) {
  const src = productImage(item.image_ref);
  return (
    <div className="product-card is-static">
      <span className="product-thumb" aria-hidden="true">
        {src ? (
          <img src={src} alt="" loading="lazy" decoding="async" />
        ) : (
          <span
            className="product-thumb-fallback"
            style={{ background: categoryTone(item.category) }}
          >
            {item.familyCount
              ? item.label.slice(0, 2).toUpperCase()
              : productInitials(item.brand, item.label)}
          </span>
        )}
      </span>
      <span className="product-text">
        {item.brand ? <span className="product-brand">{item.brand}</span> : null}
        <span className="product-name">{item.label}</span>
        {item.familyCount ? (
          <span className="product-meta">any of {item.familyCount}</span>
        ) : null}
      </span>
    </div>
  );
}

export function ProductSearch({
  onSelect,
  onUnresolved,
  autoFocus,
}: {
  onSelect: (picked: Picked) => void;
  /** Called when somebody looked and Pool had nothing. A real product does not tell a
   *  person they cannot want something. */
  onUnresolved?: (query: string) => void;
  autoFocus?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ProductCandidate[]>([]);
  const [families, setFamilies] = useState<FamilyCandidate[]>([]);
  const [attribution, setAttribution] = useState<CatalogAttribution | null>(null);
  const [active, setActive] = useState(0);
  const [busy, setBusy] = useState(false);
  const [searched, setSearched] = useState(false);
  /* Whether the exact products are showing. Collapsed while a family matched, because
     the family is the answer and six brand cards below it is the browse experience this
     screen is trying not to be. Expanded automatically when no family matched — somebody
     who typed a brand is not being offered a shortcut, they already took one. */
  const [showProducts, setShowProducts] = useState(false);
  const listId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  /* Responses can land out of order. Only the newest query is allowed to paint, or a
     slow early request overwrites a fast later one and the list contradicts the box. */
  const latest = useRef(0);

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus();
  }, [autoFocus]);

  useEffect(() => {
    const text = query.trim();
    if (text.length < MIN_CHARS) {
      setResults([]);
      setFamilies([]);
      setSearched(false);
      setBusy(false);
      return;
    }
    const token = ++latest.current;
    setBusy(true);
    const timer = setTimeout(() => {
      api
        .searchProducts(text)
        .then((view) => {
          if (token !== latest.current) return;
          setResults(view.results);
          setFamilies(view.groups ?? []);
          setAttribution(view.attribution);
          setActive(0);
          setShowProducts((view.groups ?? []).length === 0);
          setSearched(true);
        })
        .catch(() => {
          if (token !== latest.current) return;
          setResults([]);
          setFamilies([]);
          setSearched(true);
        })
        .finally(() => {
          if (token === latest.current) setBusy(false);
        });
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query]);

  /* One flat option list, so the combobox keeps working: families first, then the exact
     products when they are showing. Expanding changes what the listbox contains rather
     than nesting a second widget inside it, which `role="listbox"` does not allow. */
  const options = useMemo<Picked[]>(
    () => [
      ...families.map((family) => ({ kind: "family" as const, family })),
      ...(showProducts
        ? results.map((product) => ({ kind: "product" as const, product }))
        : []),
    ],
    [families, results, showProducts],
  );

  const choose = useCallback(
    (picked: Picked) => {
      setQuery("");
      setResults([]);
      setFamilies([]);
      setSearched(false);
      onSelect(picked);
    },
    [onSelect],
  );

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (!options.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((i) => (i + 1) % options.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => (i - 1 + options.length) % options.length);
    } else if (event.key === "Enter") {
      event.preventDefault();
      const picked = options[active];
      if (picked) choose(picked);
    } else if (event.key === "Escape") {
      setQuery("");
      setResults([]);
      setFamilies([]);
    }
  };

  const empty =
    searched &&
    !busy &&
    results.length === 0 &&
    families.length === 0 &&
    query.trim().length >= MIN_CHARS;

  return (
    <div className="product-search">
      <label className="field field-wide">
        <span className="field-label">What do you buy?</span>
        <input
          ref={inputRef}
          className="control control-search"
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="coffee, paper towels, rice…"
          autoComplete="off"
          spellCheck={false}
          role="combobox"
          aria-expanded={options.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={
            options.length > 0 ? `${listId}-${active}` : undefined
          }
        />
      </label>

      {options.length > 0 ? (
        <ul className="product-results" id={listId} role="listbox" aria-label="What you buy">
          {options.map((option, i) =>
            option.kind === "family" ? (
              <FamilyCard
                key={`family-${option.family.group}`}
                id={`${listId}-${i}`}
                family={option.family}
                selected={i === active}
                onSelect={() => choose(option)}
              />
            ) : (
              <ProductCard
                key={option.product.product_id}
                id={`${listId}-${i}`}
                product={option.product}
                selected={i === active}
                onSelect={() => choose(option)}
              />
            ),
          )}
        </ul>
      ) : null}

      {families.length > 0 && !showProducts && results.length > 0 ? (
        <button
          className="btn btn-ghost btn-sm search-widen"
          type="button"
          onClick={() => setShowProducts(true)}
        >
          Or pick one exact product ({results.length})
        </button>
      ) : null}

      {/* Politeness matters here: the result count changes under a screen reader
          without the focus moving, so it has to be announced. */}
      <p className="sr-only" role="status" aria-live="polite">
        {busy
          ? "Searching"
          : options.length > 0
            ? [
                families.length === 1
                  ? "1 product family"
                  : families.length
                    ? `${families.length} product families`
                    : "",
                showProducts && results.length
                  ? results.length === 1
                    ? "1 product"
                    : `${results.length} products`
                  : "",
              ]
                .filter(Boolean)
                .join(", ")
            : empty
              ? "Nothing found"
              : ""}
      </p>

      {empty ? (
        <div className="inset stack-sm">
          <p className="small">
            Pool does not have <strong>{query.trim()}</strong> in its catalogue yet.
          </p>
          {onUnresolved ? (
            <>
              <p className="small muted">
                You can still tell Pool you buy it. It will not be able to price a group
                order until a supplier for it has been verified.
              </p>
              <div className="btn-row">
                <button
                  className="btn btn-sm"
                  type="button"
                  onClick={() => onUnresolved(query.trim())}
                >
                  Tell Pool anyway
                </button>
              </div>
            </>
          ) : null}
        </div>
      ) : null}

      {/* Only when a photograph or a real product name is actually on screen. The
          licence obligation travels with the catalogue rows, and a family card carries
          neither. */}
      {attribution && showProducts && results.length > 0 ? (
        <p className="tiny faint product-attribution">
          Product names and photographs from{" "}
          <a href={attribution.source_url} target="_blank" rel="noreferrer noopener">
            Open Food Facts
          </a>{" "}
          contributors · {attribution.data_license} data, {attribution.image_license} images ·
          snapshot {attribution.snapshot}
        </p>
      ) : null}
    </div>
  );
}
