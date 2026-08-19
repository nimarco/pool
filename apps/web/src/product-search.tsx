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
 */

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { CatalogAttribution, ProductCandidate, api } from "./api";
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

/* ------------------------------------------------------------------ the search */

export function ProductSearch({
  onSelect,
  onUnresolved,
  autoFocus,
}: {
  onSelect: (product: ProductCandidate) => void;
  /** Called when somebody looked and Pool had nothing. A real product does not tell a
   *  person they cannot want something. */
  onUnresolved?: (query: string) => void;
  autoFocus?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ProductCandidate[]>([]);
  const [attribution, setAttribution] = useState<CatalogAttribution | null>(null);
  const [active, setActive] = useState(0);
  const [busy, setBusy] = useState(false);
  const [searched, setSearched] = useState(false);
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
          setAttribution(view.attribution);
          setActive(0);
          setSearched(true);
        })
        .catch(() => {
          if (token !== latest.current) return;
          setResults([]);
          setSearched(true);
        })
        .finally(() => {
          if (token === latest.current) setBusy(false);
        });
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query]);

  const choose = useCallback(
    (product: ProductCandidate) => {
      setQuery("");
      setResults([]);
      setSearched(false);
      onSelect(product);
    },
    [onSelect],
  );

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (!results.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((i) => (i + 1) % results.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => (i - 1 + results.length) % results.length);
    } else if (event.key === "Enter") {
      event.preventDefault();
      const picked = results[active];
      if (picked) choose(picked);
    } else if (event.key === "Escape") {
      setQuery("");
      setResults([]);
    }
  };

  const empty = searched && !busy && results.length === 0 && query.trim().length >= MIN_CHARS;

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
          placeholder="vanilla whey, paper towels, coffee…"
          autoComplete="off"
          spellCheck={false}
          role="combobox"
          aria-expanded={results.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={
            results.length > 0 ? `${listId}-${active}` : undefined
          }
        />
      </label>

      {results.length > 0 ? (
        <ul className="product-results" id={listId} role="listbox" aria-label="Matching products">
          {results.map((p, i) => (
            <ProductCard
              key={p.product_id}
              id={`${listId}-${i}`}
              product={p}
              selected={i === active}
              onSelect={() => choose(p)}
            />
          ))}
        </ul>
      ) : null}

      {/* Politeness matters here: the result count changes under a screen reader
          without the focus moving, so it has to be announced. */}
      <p className="sr-only" role="status" aria-live="polite">
        {busy
          ? "Searching"
          : results.length > 0
            ? `${results.length} products found`
            : empty
              ? "No products found"
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

      {attribution && results.length > 0 ? (
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
