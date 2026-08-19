# Product catalog & item discovery — investigation and design

Research pass, 2026-08-19. Findings verified against primary sources and live API probes;
every claim that rests on a probe records what was actually returned.

> **Status: implemented.** The recommendation in §7–§11 shipped on 2026-08-19 — see
> `BUILD_HISTORY.md` #0037. What was built matches this document with three deliberate
> changes, recorded here rather than quietly:
>
> 1. **The catalogue is a JSON snapshot, not SQLite.** At 295 rows, an in-process pure
>    function over a parsed list is faster than opening a database, has no build step, and
>    is trivially diffable in review. SQLite earns its place somewhere past ~10k rows.
> 2. **Household goods are curated and brand-free.** §5.3 predicted thin coverage; the
>    probe returned 0 US laundry detergents, 0 toilet papers and 1 paper towel, so five
>    household products are hand-written with no brand rather than sourced.
> 3. **The seeded products publish no GTIN.** Not anticipated here. Pool quotes a synthetic
>    price for those six, and a barcode names one specific retail package — so they carry
>    brand, product line, flavour and photograph, and claim no SKU. §14's "judgement call"
>    resolved this way instead of by labelling alone.

---

## 1. Executive verdict

**What is wrong today.** Pool's product *model* is sound. Pool's product *entry* is not. The
member-facing "what you buy" control is a `<select>` over six hand-written fictional products
(`apps/web/src/views/needs.tsx`, `services/agent/pool/data/seed.py`). There is no search, no
images, no GTIN, no synonyms, no way for a member to express anything the seed author did not
anticipate. The gap is narrow and specific: **a resolution layer between free text and
`product_id` does not exist.** Everything downstream of `product_id` — matching, substitution,
timing, economics, allocation — is well-built and should not be touched.

**The correct replacement.** Add a *product identity and resolution* layer above the existing
`Product` entity. Do not merge it into `Offer`. Concretely: a curated, locally-bundled catalog
subset derived from Open Food Facts, searched with SQLite FTS5 in-process, with pinned local
images, feeding the unchanged `product_id` contract.

**What should be real vs synthetic.** Product *identity* (name, brand, variant, GTIN, image,
category) should become **real**. Package structure, supplier offers, wholesale pricing, MOQ,
and the retail baseline must stay **synthetic and labelled**, because no lawful, reliable source
for them exists at this project's scale — and because Open Food Facts' package-size data is
demonstrably unusable (§5.1).

**Is a rewrite required?** No. `Product.from_dict` defaults every field except five
(`models.py:618`), so every new field is additive and needs **zero data migration**. The
canonical demo's product IDs, offers, and economics can remain bit-identical.

---

## 2. How the current simulation actually works

Traced from executable code, not docs.

### Where products come from
`services/agent/pool/data/seed.py:114` — a Python list of six `Product` dataclasses, invented
brands (Northfield, Voltside, Ridgeline, Clearwash, Mapleline). Written to the repository at
seed time via `repo.put_product`. There is no other product source anywhere in the codebase.

### Where images come from
**Nowhere.** A repo-wide grep for `image|photo|thumbnail|img|gtin|upc|barcode` across
`services/` and `apps/` returns zero product-related hits. The public demo's CSP is
`img-src 'self' data:` (`api/public_demo.py:123`) — remote images are actively forbidden, and
`data:` is allowed for exactly one thing: the inline SVG favicon.

### Where supplier offers come from
`seed.build_offers()` — twelve hand-written `Offer` rows, every one `OfferSource.SYNTHETIC`.
The sourcing seam (`adapters/sourcing.py`) defines a `SourcingProvider` protocol with four
implementations: `SyntheticCatalogProvider` (serves the seeded catalogue),
`DriftingCatalogProvider` (moves price on refresh, so the "quote changed" branch is testable),
`ManualVerifiedOfferProvider` (operator-entered, and *refuses* to self-re-verify), and no live
integration. `SupplierPortalProvider` is documented as future work and deliberately not stubbed.

### Which values are synthetic
Product identity, all supplier offers, retail baselines, member locations, communities, pickup
sites, payment methods. All flagged: `Supplier.synthetic`, `Household.synthetic`,
`Community.synthetic`, `OfferSource.SYNTHETIC`, `PickupPermission.DEMO`,
`VerificationMethod.DEMO`.

### Which values are computed
Everything financial. `domain/economics.py` computes package allocation (`allocate_packages`,
`fit_to_cases`), host reward, platform fee, processing gross-up, per-buyer landed cost, and
savings basis points. `domain/matching.py` computes eligibility and distance.
`domain/viability.py` runs the four-party gate. No figure shown to a human is model-authored.

### How a Need refers to a product
`NeedDeclaration.product_id: str` — a bare foreign key into the product table. One active
declaration per (household, product) is enforced in `services/needs.py:declare_need`, because
two rows would double-count demand.

### How Pool knows two members want the "same" thing
`domain/substitution.py:evaluate_compatibility` — a pure function over
`(target: Product, candidate: Product, need: NeedDeclaration)`. Five policies, strictest first:
`EXACT_ONLY` (identical id), `SAME_PRODUCT_OTHER_VARIANT` (same `brand` + same
`substitute_group`), `APPROVED_PRODUCTS` (member's explicit id allowlist), `APPROVED_BRANDS`
(same group + brand allowlist), `STRUCTURED_CATEGORY_MATCH` (same group + same `category`).
Every non-exact policy also honours a per-unit price ceiling. Unknown policies **fail closed**.

`substitute_group` is the load-bearing field, and today it is a hand-assigned string.

### How the canonical demo stays deterministic
Fixed entity IDs make seeding idempotent. Needs are rebuilt relative to `date.today()` so the
scenario never expires. Two members (`hh_sandoval`, `hh_kowalski`) are given wide
`earliest_acceptable_purchase_date` windows so the pull-forward mechanic reliably fires;
`hh_villanueva` is placed in the inner ring with a card seeded to decline
(`DECLINING_METHOD = "pm_sim_declines_demo"`), so the payment-recovery branch executes every run
rather than occasionally. `tests/test_demo_scenario.py` runs the whole lifecycle offline and
asserts the step sequence — it reads savings from computed facts rather than pinning a dollar
figure, so the arithmetic is free to be whatever it is.

---

## 3. Ideal member product-entry experience

Design target: a person adding "the protein powder I buy" should never see procurement
vocabulary. Minimum interaction that still preserves matching quality:

1. **One text box.** "What do you buy?" Free text, not a dropdown.
2. **Typeahead after ~3 characters**, lexical, local, sub-50ms. No LLM on this path — see §11.
3. **Product cards, not rows.** Image, brand, product name, size. Three to six results.
   Recognition, not recall — the member confirms rather than describes.
4. **One tap to select.** That resolves free text → `product_id`. The member never sees the id.
5. **Two questions only:** how many, and how often. Everything else has a safe default.
6. **A single optional line for flexibility:** "OK to buy up to N days early." This is the one
   field that is genuinely load-bearing for pull-forward and cannot be inferred.
7. **Substitution stays collapsed** behind "fine-tune", exactly as the current form already does.
8. **"Can't find it?"** → free text is captured verbatim as a resolution request, the need is
   *not* created, and the member is told plainly that Pool will add it. No silent failure.

**What gets remembered:** the resolved `product_id` and the member's cadence, so re-declaring is
one tap next time. Nothing else.

**Explicit non-goals:** barcode scan (nice later, not now — it needs camera permission the
Permissions-Policy currently denies outright), category-level needs (they break the case-boundary
math), brand preferences as a first-class field (already covered by `APPROVED_BRANDS`).

**Multiple variants:** show them as separate cards (vanilla / chocolate) rather than a variant
picker. The member picks the one they actually buy; `SAME_PRODUCT_OTHER_VARIANT` handles the rest
downstream, deterministically.

---

## 4. Data problems that must remain separate

The single most important structural conclusion. These are six different problems with six
different sources, reliabilities, and legal positions. Collapsing them into one "catalog" would
be the architectural error.

| # | Concern | Question it answers | Correct source | Reliability |
|---|---|---|---|---|
| 1 | **Consumer identity** | "Is this the thing I buy?" | Open Food Facts subset | Good |
| 2 | **Imagery** | "Does it look right?" | OFF images, pinned locally | Good, licence-encumbered |
| 3 | **Matching key** | "Are two needs compatible?" | Pool-curated mapping table | Must be deterministic |
| 4 | **Package structure** | "What is one sealed unit? How many per case?" | **Operator-verified only** | OFF data is unusable (§5.1) |
| 5 | **Retail baseline** | "What would I pay alone?" | Member-stated or operator-verified | Synthetic in demo |
| 6 | **Bulk supplier offer** | "What does a case cost, and what's the MOQ?" | **No lawful public source exists** | Synthetic; operator-entered in pilot |

Concerns 1–3 can become real now. Concerns 4–6 cannot, and pretending otherwise would violate
AGENTS.md §8.

The boundary that matters most: **identity is not structure.** A product can be perfectly
identified and still have no trustworthy package size. Pool's economics depend entirely on
structure, so structure must never be inherited from a crowd-sourced field.

---

## 5. Research findings

### 5.1 Open Food Facts — RECOMMENDED for identity + images only

**Provides:** ~4.75M products globally, **954,580 for the United States** (verified on
`us.openfoodfacts.org`). Per product: GTIN/EAN code, product name, brand, category tags,
front image URL, ingredients, nutrition.

**Verified by live probe.** Query for US protein powders (`categories_tags=en:protein-powders`,
`countries_tags=en:united-states`) returned **1,299 products**. Sample of 8:

```
0851770007566 | Orgain            | qty="43.2 oz ("  | img=Y | Organic Protein
0851770008631 | Orgain            | qty="1.2 kg"     | img=Y | Organic Protein
0748927059113 | Optimum Nutrition | qty=""           | img=Y | Gold Standard 100% Whey Extreme
0748927065404 | Optimum Nutrition | qty="80 x 31g"   | img=Y | Protein powder
0850019568240 | Vital Proteins    | qty="I tablesp"  | img=Y | Collagen Peptides
0196633918901 | Kirkland Signature| qty="5.4lb"      | img=Y | Whey Protein Creamy Chocolate
0089094026219 | Isopure           | qty="30.5 g"     | img=Y | Protein Powder Drink Mix
0851770003179 | Orgain            | qty="2.03 lbs"   | img=Y | Organic Protein Protein Powder
```

**8/8 have images. 7 different package-size formats in 8 records**, including one truncated
(`"43.2 oz ("`), one empty, one free-text nonsense (`"I tablesp"`), one multipack (`"80 x 31g"`),
and at least one that is a *serving* size rather than a package size (`"30.5 g"`).

A direct lookup of the real US Gold Standard whey UPC **748927028669** returned correct name,
brand, category and image — and **`quantity: ""`, `product_quantity: None`**.

Brand casing is inconsistent: "Optimum nutrition", "Optimum Nutrition", "OPTIMUM NUTRITION"
appeared in a single five-record response.

> **Conclusion: Open Food Facts is excellent for identity and images, and unusable as a source of
> package structure.** This is the finding that fixes the architecture.

**Does not provide:** any pricing, any wholesale data, any case/MOQ structure, reliable package
size, reliable variant/flavour as a structured field (it is embedded in the name).

**Licence:** database ODbL 1.0; contents Database Contents Licence; **images CC-BY-SA**.
Per the ODbL text and the OSMF guidance, displaying data in an app is a **Produced Work** —
share-alike does *not* reach Pool's own database — but *publishing an extracted subset* (e.g. in
a public GitHub repo) **is a Derivative Database** and must itself be offered under ODbL with
attribution. OFF also warns explicitly that images may carry third-party rights (packaging design
copyright, trademark) beyond the CC-BY-SA grant.

**Reliability — measured, not assumed.** Documented limits: **10 req/min/IP for search**,
15 req/min/IP for product reads. The official docs explicitly warn *against using search for
real-time autocomplete*. During this research session, under light manual use, the search
endpoint returned **HTTP 503**. This is direct evidence: the live API must not be a demo
dependency.

**Bulk access:** nightly JSONL/CSV/MongoDB dumps at `static.openfoodfacts.org/data/` (redirects
to `openfoodfacts-ds.s3.eu-west-3.amazonaws.com`); Parquet on Hugging Face
(`openfoodfacts/product-database`, ~4.75M rows). **Images are on the AWS Open Data Registry** —
`s3://openfoodfacts-images` (eu-west-3), accessible with `--no-sign-request`, storage sponsored
by the AWS Open Data Sponsorship Program.

### 5.2 USDA FoodData Central — RECOMMENDED as a licence-clean supplement

**Provides:** Global Branded Food Products Database. GTIN/UPC, brand owner, brand name,
ingredients, serving size, food category. Bulk download: **195 MB zipped / 3.1 GB unzipped JSON**
(Dec 2025 release), updated roughly twice yearly. API: 1,000 req/hour/IP with a free key.

**Does not provide:** images, prices, wholesale data, non-food products.

**Licence: CC0 1.0 — public domain.** No attribution required, no share-alike, no restriction on
redistribution or commercial use. **Strictly better licensing than OFF.**

**Relevance:** the licence-safe fallback for identity and GTIN where OFF's share-alike is
awkward. Its lack of images is the reason it cannot be the only source.

### 5.3 Open Products Facts — REJECTED (coverage)

**44,285 products total** (verified on the homepage). OFF's own non-food category holds ~1,409
products, with ~230 laundry detergents. Paper towels are effectively absent.

Pool's household categories (paper towels, detergent) have **no viable open catalog**. They must
stay curated.

### 5.4 Kroger Products API — REJECTED for now, revisit at pilot

**Provides:** real US grocery catalog with real store-level prices, images, UPC, size, aisle
location, and inventory. Free tier: 10,000 calls/day. OAuth2 required.

**Does not provide:** wholesale/bulk pricing, case structure, MOQ.

**Problems:** results are store-specific (needs a `locationId`), terms around caching and
redistribution are not publicly documented in a form I could verify (the developer portal is
JS-rendered and timed out on two fetch attempts), and it is a live third-party dependency.

**Relevance:** genuinely the best candidate for a *real retail baseline* in a geographically
scoped pilot. Not for the demo.

### 5.5 Amazon Product Advertising API — REJECTED (dead)

**PA-API 5.0 is being deprecated 2026-05-15 and is no longer accepting new customers.**
Its replacement, the Creators API, gates access behind **10 qualifying affiliate sales in a
trailing 30-day window**. Pool has no affiliate sales. Not available, full stop.

### 5.6 UPCitemdb / Go-UPC / Barcode Lookup — REJECTED (redistribution)

Large barcode databases (UPCitemdb claims 724M codes; Go-UPC claims 1B+ items) returning titles,
brands, images, and merchant offers. Free tiers ~100 req/day.

**Fatal problem:** UPCitemdb participates in the Amazon Associates and eBay Partner Network
programs and is bound by those agreements — sales information may be shown *on their site only*
and **cannot be redistributed**. Image provenance is also unclear: images appear to be aggregated
from retailer listings, so the CC-BY-SA-style clarity OFF offers is absent.

### 5.7 GS1 US — REJECTED (cost)

The authoritative GTIN registry. GS1 US Data Hub View/Use subscription starts at **$500**, and
API access is a **$6,500 flat-fee add-on**. Individual GTIN licensing is $30 one-time (that is
for *issuing* your own barcodes, not looking others' up).

Correct long-term answer for GTIN authority in a funded company. Out of reach here.

### 5.8 Nutritionix — REJECTED (cost)

1.9M foods, 600k+ UPCs, 92% match rate, bulk CSV/JSON delivery available. **From $1,850/month.**

### 5.9 Instacart Developer Platform — REJECTED (timeline)

Real US grocery catalog with nutrition, size, and more. **Access requires business registration
and averages 30–40 days from request to production keys**, and Catalog API access specifically
requires contacting an Instacart representative. The hackathon deadline is 2026-09-14 —
approximately 26 days out. Timeline does not work. Worth pursuing for a pilot.

### 5.10 Wholesale / bulk supplier data — NO VIABLE SOURCE

Searched for public developer APIs from Sysco, US Foods, and Costco Business. **None exist.**
The channel runs on EDI and contractual relationships, not REST. Third-party scrapers are
marketed (e.g. Apify Sysco scrapers claiming pack size, barcode, images, real-time availability),
but scraping a distributor's authenticated catalog is a terms-of-service violation, legally
exposed, and unreliable — exactly the dependency AGENTS.md §46 argues against.

> **Say it plainly: real wholesale offer data is closed, contractual, location-dependent, and
> membership-gated. Pool cannot obtain it lawfully at this scale.** The existing
> `ManualVerifiedOfferProvider` — one operator phones a wholesaler and records terms with a
> timestamp — is not a shortcut. It is the correct and honest cold-start architecture, and it is
> already built.

### 5.11 Vertex AI Search for commerce — REJECTED (supplies no data)

Google's commerce search/ranking service. **Confirmed from Google's own docs: it supplies no
product data.** "You ingest user event and catalog data." Pool must bring its own catalog.
Pricing ~$2.50 per 1,000 queries; a free tier exists (~10k queries/month).

It is an excellent ranking engine for a catalog of millions with real user-event streams. Pool
has neither. At Pool's scale it buys nothing that SQLite FTS5 does not already provide for $0.

### 5.12 Google Merchant API / Content API for Shopping — REJECTED (wrong shape)

Manages **your own** Merchant Center listings. It is not a global product search. This is exactly
the "merchant catalog management ≠ global product search" confusion to avoid.

### 5.13 Amazon OpenSearch Serverless — REJECTED at demo scale

Classic collections carry a **2-OCU minimum** (~$350/mo production, ~$175/mo dev/test). NextGen
collections (GA 2026-05-28) have **no minimum and scale to zero** after 10 minutes idle, at
$0.24/OCU-hour + $0.02/GB-month.

NextGen removes the cost objection but not the complexity one. For a catalog under ~100k rows
this is unjustified infrastructure — and AGENTS.md §3.7 explicitly forbids "just in case"
infrastructure.

### 5.14 Amazon S3 Vectors — NOTED, not needed yet

GA since 2025-12-02, expanded to 17 more regions in 2026-03, with query costs cut up to 80% for
large indexes in 2026-06. Genuinely cheap vector storage.

Not needed: at 5k–50k products, an in-memory brute-force dot product over precomputed embeddings
is faster and free.

### 5.15 Bedrock embeddings — CHEAP, use offline only

Titan Text Embeddings V2: **$0.02 per million input tokens** (1024-dim). Cohere Embed:
$0.10/M. Embedding a 50,000-product catalog at ~20 tokens each is ~1M tokens ≈ **$0.02, one
time.** Cost is a non-issue; the design question is only *when* to call it (answer: at index
build time, never per keystroke).

### 5.16 BLS Average Price Data — NOTED, narrow

US Bureau of Labor Statistics AP series. Public domain, free API (registration required, 500
queries/day). Genuine US city-average retail prices — but only for food staples and fuel.
Coffee: yes. Protein powder, paper towels, detergent: no.

Useful as a *credibility anchor* for one or two demo categories. Not a general baseline.

---

## 6. Comparison matrix

Scored 1–10 for Pool's actual needs. Bold = chosen.

| Option | Consumer UX | Data quality | Images | US cover | Bulk data | Reliability | Demo repro | Cost | Licence | Complexity | **Total** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **OFF subset, bundled locally** | 9 | 7 | 9 | 8 | 0 | **10** | **10** | **10** | 6 | 8 | **77** |
| OFF live API | 9 | 7 | 8 | 8 | 0 | **2** | **2** | 10 | 6 | 9 | 61 |
| USDA FDC bundled | 7 | 8 | **0** | 9 | 0 | 10 | 10 | 10 | **10** | 8 | 72 |
| Kroger API live | 9 | 9 | 9 | 7 | 0 | 5 | 3 | 9 | 4 | 5 | 60 |
| Status quo (6 fictional) | **2** | 3 | 0 | 0 | 0 | 10 | 10 | 10 | 10 | 10 | 55 |
| UPCitemdb / Go-UPC | 8 | 6 | 7 | 8 | 0 | 6 | 4 | 6 | **2** | 7 | 54 |
| Nutritionix | 8 | 9 | 6 | 9 | 0 | 8 | 8 | **1** | 5 | 6 | 60 |
| Instacart IDP | 9 | 9 | 9 | 9 | 0 | 7 | 5 | 7 | 4 | 4 | 63 |
| Vertex AI Search | 7 | n/a | n/a | n/a | 0 | 8 | 6 | 6 | 8 | 4 | — |
| GS1 US | 6 | **10** | 2 | 9 | 0 | 9 | 9 | **1** | 7 | 5 | 58 |

**The answer is a hybrid, not a single winner:** OFF for identity and images, bundled locally for
reliability; USDA FDC as the licence-clean GTIN cross-check; everything commercial rejected on
cost, licence, or timeline; wholesale stays synthetic because nothing else is lawful.

---

## 7. Recommended product catalog source

**A curated, version-controlled subset of Open Food Facts, bundled in the repository as a SQLite
file, with USDA FDC used to cross-check GTINs.**

Why:
- It is the only source that supplies **identity + image + GTIN + US coverage** at zero cost with
  a licence that permits commercial use.
- Bundling converts the worst property (a 10 req/min API that returned 503 during research) into
  a non-issue: **zero network calls at query time**.
- A curated subset is small. Filtering ~954k US products to Pool's categories yields roughly
  5k–50k rows — a 10–40 MB SQLite file, trivially committable and trivially fast.
- It keeps the demo reproducible by construction: the catalog is a build artifact with a pinned
  snapshot date, not a live query.

**Hard rule: import identity fields only.** Name, brand, GTIN, category tags, image. Never import
`quantity`/`product_quantity` into anything the economics engine can read — §5.1 shows why.

---

## 8. Recommended product image strategy

**Pin images locally as repository assets, served same-origin.**

1. Fetch canonical demo product images once from `s3://openfoodfacts-images` (`--no-sign-request`,
   AWS Open Data Program — free, no credentials, no rate limit).
2. Resize to a fixed display size, store under `apps/web/public/products/<product_id>.webp`.
3. Serve same-origin. **This requires no CSP change** — `img-src 'self'` already permits it, and
   already forbids the remote-URL alternative. The existing policy was right.
4. Record `image_attribution` per product and render it (CC-BY-SA requires it).
5. Ship a neutral category-glyph fallback so a missing image never renders a broken box.

Why not remote URLs: they break the CSP, add a third-party dependency to every page paint, can
404 without warning, and would make the demo's appearance depend on a host Pool does not control.

**Licensing caveat to state plainly:** OFF images are CC-BY-SA, but OFF itself warns they may
carry packaging-design copyright and trademark rights beyond that grant. Naming a real product is
protected by nominative fair use; reproducing its packaging photograph is a separate question. For
a hackathon demo with attribution, the exposure is low. **Before any commercial launch this needs
a real answer**, and the cheapest one is to photograph products directly or use manufacturer press
assets.

---

## 9. Recommended bulk supplier strategy

**Keep it synthetic for the demo. Keep `ManualVerifiedOfferProvider` as the pilot path. Change
nothing structural.**

There is no lawful public source (§5.10). The existing design is already correct and already
honest:

- `OfferSource.SYNTHETIC` for demo data, surfaced in the UI as simulated.
- `OfferSource.MANUAL_VERIFIED` for pilot data, with `verified_at` and a refusal to self-refresh
  — a human confirmed the price, so only a human can re-confirm it.
- `OfferSource.SUPPLIER_SUBMITTED` reserved for a supplier portal.
- `OfferSource.LIVE_RETAILER` reserved and deliberately unimplemented.

The one addition worth making: **a product with no offer is still a legitimate need.** A member
can declare a need for anything in the catalog; a *pool* can only form where a verified offer
exists. That is exactly how the real business works, and it makes the "we don't have a supplier
for this yet" state a first-class, honest UI state rather than a dead end.

---

## 10. Recommended retail baseline strategy

**Keep `Offer(kind=RETAIL)` — the model is right. Add provenance, and add a member-stated option.**

Ranked by defensibility:

1. **Member-stated usual price** — "what do you normally pay?" Most defensible (it is their own
   fact), zero licensing exposure, personalised. Add `OfferSource.MEMBER_STATED`.
2. **Operator-verified snapshot** — someone checks the campus store, records price + timestamp +
   source. Reuses the `ManualVerifiedOfferProvider` pattern exactly.
3. **Live retailer API (Kroger)** — real, but store-specific, terms-uncertain, and a live
   dependency. Pilot only.
4. **Synthetic** — the demo default, already labelled.

Rejected: catalog MSRP (does not exist in any source examined), scraped prices (ToS), and
BLS averages for anything except the couple of categories BLS actually covers.

The baseline is the number Pool's entire savings claim rests on. Its provenance must be visible
wherever a savings percentage is shown.

---

## 11. Recommended search / matching architecture

### Search: SQLite FTS5, in-process, zero network

- FTS5 virtual table over `name || brand || variant || synonyms`, BM25 ranking.
- Prefix queries for typeahead (`whey*`), trigram fallback for typos.
- A hand-authored synonym table for the cases lexical search cannot reach:
  `"ON" → "Optimum Nutrition"`, `"tp" → "toilet paper"`, `"pods" → "laundry detergent pods"`.
- Runs inside the existing Lambda. **No OpenSearch, no Vertex AI Search, no vector database.**
- Sub-50ms on 50k rows, $0, and deterministic — the same query returns the same ranking on every
  run, which is what a repeatable demo requires.

**No LLM on the typeahead path.** It would add latency to the most-used interaction, cost per
keystroke, non-determinism to the demo, and would violate AGENTS.md §3.3 (bound AI usage). The
LLM earns its place on the *fallback* path only: when a member says "can't find it", one bounded
call extracts structured attributes from their text into a resolution request for operator review.

Optional later: precomputed Titan embeddings (~$0.02 one-time, §5.15) brute-forced in memory for
semantic recall. Add it only if lexical recall is measurably insufficient.

### Matching: unchanged, with one addition

`domain/substitution.py` is correct and must not change. What changes is **how `substitute_group`
gets assigned** when products come from a real catalog rather than a seed author's hand.

**A curated, version-controlled mapping table** from OFF category tags to Pool substitute groups:

```python
# data/substitute_groups.py — reviewed by a human, committed, diffable
CATEGORY_TO_GROUP = {
    "en:protein-powders": "whey_protein",
    "en:coffees":         "coffee",
    "en:energy-drinks":   "energy_drink",
}
```

Applied at **catalog build time**, never at request time. A product whose category has no mapping
gets **no substitute group**, which under `substitution.py` means it can only ever match itself
(`EXACT_ONLY` behaviour) — a correct, safe default, because an unmapped group already fails closed.

This preserves the architectural principle exactly:

| Layer | Who decides | Determinism |
|---|---|---|
| "vanilla whey" → candidate products | lexical search (+ optional LLM on fallback) | ranked, reproducible |
| member picks one | **the human** | explicit |
| `product_id` → `substitute_group` | curated table, build time | deterministic, reviewable |
| two needs compatible? | `evaluate_compatibility` | deterministic, tested |
| money | `economics.py` | deterministic, tested |

**An LLM never assigns `substitute_group` and never decides compatibility.** The normalisation of
"vanilla whey" / "Gold Standard vanilla protein" / "ON whey vanilla" happens by *ranking search
results for a human to confirm*, not by a model asserting equivalence.

---

## 12. Recommended Google Cloud architecture

Honest assessment first: **Vertex AI Search for commerce is not the answer** (§5.11 — it supplies
no data and Pool's catalog is too small to need it), and **Merchant API is the wrong shape**
(§5.12). Forcing either in would be exactly the decorative-service mistake AGENTS.md §2 warns
against.

**The one genuinely Google-differentiated capability: Gemini multimodal product resolution.**

Point your camera at the tub in your pantry → Gemini identifies brand + product + variant →
Pool matches it against the same local catalog → one tap to confirm → need created.

Why this is the right Google-specific bet:
- It is a **capability difference**, not an infrastructure swap. AWS Bedrock can do multimodal
  too, but "photograph your pantry" is a natural, demoable, consumer-grade use of Gemini that a
  judge immediately understands.
- It attacks the *hardest* remaining UX problem: a member who does not know the brand name.
- It uses the **same normalized Pool product model**. The output is a `product_id` candidate list
  — identical contract to the text path. **No lock-in.**
- Gemini's structured-output mode constrains the response to a schema, so the model returns
  candidate attributes, and deterministic code still does the matching.

Supporting, low-commitment Google fits:
- **BigQuery** for the offline catalog build — load the OFF Parquet dataset, filter to US +
  Pool categories, export the subset. A legitimate, cheap, genuinely-better-than-local pipeline.
- **Cloud Storage** for image assets, if the Google build wants a CDN.

Explicitly *not* recommended: Firestore or Cloud SQL (the repository abstraction already has
in-memory and DynamoDB implementations; adding a third buys nothing), Recommendations AI (no
user-event stream exists), Vision API product search (superseded by Gemini for this use).

---

## 13. Recommended AWS architecture

**Add almost nothing. That is the recommendation.**

- **Catalog storage:** the bundled SQLite file, shipped in the Lambda package. No new service.
- **Search:** FTS5 in-process. **Do not add OpenSearch** — §5.13. Even NextGen's scale-to-zero
  does not justify the operational surface for a 50k-row catalog.
- **Images:** repo assets served same-origin by the existing Lambda. If they outgrow the bundle,
  S3 + CloudFront — and `PoolStack` already has that pattern.
- **Bedrock:** already load-bearing for the agent. Use Titan embeddings **at index build time
  only** if semantic recall is later needed ($0.02 one-time).
- **DynamoDB:** unchanged. Products already persist through `DynamoRepository` with a `PRODUCT`
  entity type; new fields are additive.
- **S3 (`--no-sign-request`) against `s3://openfoodfacts-images`** for the one-time image fetch.
  Pleasingly, this is an *AWS Open Data Program* dataset — a genuine, non-decorative AWS story
  for the write-up.

The AWS-specific narrative is not "we added a search service." It is: *the catalog is a build
artifact, the demo makes zero third-party calls at judging time, and the agent's reasoning runs
on Bedrock.* That is a stronger technical claim than another logo.

---

## 14. Canonical demo strategy

Everything the canonical scenario touches must be local and pinned.

| Element | Strategy |
|---|---|
| Catalog | SQLite artifact committed with a pinned `snapshot_date`, built by a script, never fetched at runtime |
| Images | WebP files in `apps/web/public/products/`, fetched once from the AWS Open Data bucket, committed |
| Product IDs | **Unchanged.** `prod_whey_vanilla` etc. stay as the primary keys |
| Offers | Unchanged synthetic seed, still `OfferSource.SYNTHETIC`, still labelled |
| Retail baseline | Unchanged synthetic |
| Economics | Unchanged — every figure still computed by `economics.py` |
| External calls at demo time | **Zero** |

**Product IDs do not change.** Only the *identity fields on those rows* change — the invented
"Northfield" becomes a real brand with a real image and a real GTIN. Every test that references
`prod_whey_vanilla`, every offer, and every economics assertion keeps working untouched.

### The one judgement call worth flagging

Using a **real brand** (e.g. Optimum Nutrition Gold Standard) next to a **synthetic wholesale
quote** could imply Pool has a supplier relationship it does not have. Two defensible options:

- **(a) Real identity + prominent synthetic labelling.** Strongest demo. Requires the
  "simulated supplier quote" label to be unmissable wherever the offer appears. Nominative fair
  use covers naming the product; the existing `OfferSource` labelling covers the quote.
- **(b) Real *categories*, invented brands.** Keeps the current "Northfield" style but adds
  search, images (generic/own-photographed), and structure. Zero brand risk, less visceral.

**This is your call, not mine** — it is a brand-risk judgement. My recommendation is (a) with
strict labelling, because AGENTS.md §12's rule is "label simulated things", not "avoid real
names", and the labelling machinery already exists.

---

## 15. Exact Rosa demo flow

**Starting state.** Rosa Navarro (`hh_navarro`, `ASK_ME` autonomy) is signed in. The community
holds ~33 standing needs from 24 members. No pool exists. Rosa sees her own needs; she cannot see
who else wants what, because that is the premise.

1. **She taps "Add a need."** One text box: *What do you buy?*
2. **She types `vanilla whey`.** Not a brand, not an ID — what a person actually says.
3. **Resolution runs locally.** FTS5 over name + brand + variant + synonyms. No network call.
   Sub-50ms.
4. **Three product cards appear**, each with a real image, brand, name, and size. She recognises
   the tub she actually buys.
5. **She taps it.** Free text → `product_id`. She never sees the id.
6. **Two questions:** *How many?* `2`. *How often?* `every 6 weeks`. One optional line:
   *OK to buy up to 11 days early.*
7. **She saves.** Pool stores one `NeedDeclaration`. **No card touched. No group created. Nobody
   invited.** The screen says so.
8. **She taps "Find opportunities."** The agent takes over — the same
   `list_latent_demand` → `evaluate_pool_economics` → `create_candidate_pool` sequence that
   exists today.
9. **The agent finds what she could not see:** seven other students independently need the same
   product; 18 units is short of the supplier's 24-unit minimum *and* short of a clean 12-unit
   case boundary; two students authorised buying early, which lands it exactly on 24.
10. **A worked-out pool appears** that Rosa never organised: exact landed price, named pickup
    site, real travel time, host being recruited.

**What the judge learns.** The causal chain is visible end to end, and each link is a different
kind of truth:

```
member intent ("vanilla whey")     ← free text, human
  → canonical product              ← deterministic search, human confirms
  → standing need                  ← deterministic write, no commitment
  → latent demand discovered       ← AI decides what to investigate
  → economics                      ← deterministic, every figure computed
  → coordinated pool               ← nobody asked for it
```

### A caveat that needs your decision

Rosa already has a seeded whey need (`need_whey_navarro`, 2 tubs). For her live declaration to be
*causal* rather than decorative, that seed row must be removed — but the arithmetic then breaks:
the inner ring drops to 16 units, and with the two pull-forward members it reaches 22, not 24. The
pool would correctly fail to form, and the flagship scenario would be lost if she skipped the form.

Three options, in order of my preference:

- **(i) Keep her seeded need; demo entry with a *second* product.** Flagship math untouched. Her
  new need feeds a different pool. Safest; slightly less dramatic.
- **(ii) Remove her seed row and re-balance** another member's quantity by +2 so the fallback
  still reaches 24 without her. Preserves both the drama and the fallback. Requires re-verifying
  `test_demo_scenario.py`.
- **(iii) Remove her seed row with no fallback.** Most dramatic, most fragile. Not recommended.

---

## 16. Normalized data model changes

All additive. `Product.from_dict` already defaults every non-core field (`models.py:618`), so
**existing DynamoDB rows deserialize unchanged — zero migration.**

```python
class ProductSource(str, Enum):            # NEW
    CURATED = "curated"                    # hand-authored demo seed
    OPEN_FOOD_FACTS = "open_food_facts"
    USDA_FDC = "usda_fdc"
    MEMBER_SUBMITTED = "member_submitted"  # pending operator review
    OPERATOR_VERIFIED = "operator_verified"

@dataclass
class Product:
    # --- unchanged core ---
    id: str
    name: str
    category: str
    unit: str
    substitute_group: str
    brand: str = ""
    variant: str = ""
    unit_weight_grams: int = 0
    individually_sealed: bool = True

    # --- NEW: consumer identity ---
    gtin: str = ""                    # GTIN-14 normalized; "" = unknown
    image_ref: str = ""               # LOCAL asset path, never a remote URL
    image_attribution: str = ""       # CC-BY-SA obligation
    synonyms: list[str] = field(default_factory=list)
    display_size: str = ""            # human string, e.g. "5 lb (2.27 kg)"

    # --- NEW: provenance ---
    identity_source: ProductSource = ProductSource.CURATED
    identity_snapshot_date: str = ""  # pinned catalog build date
```

Deliberately **not** added: any machine-readable package size from an external source. The
economics engine reads `unit_weight_grams` (host capacity) and `Offer.case_units` (case
structure), and both must stay operator-set. `display_size` is a *string for humans* precisely so
it can never be arithmetic.

```python
@dataclass                                  # NEW entity
class ProductResolutionRequest:
    """A member described something Pool could not resolve. Becomes operator work."""
    id: str
    household_id: str
    community_id: str
    raw_text: str
    suggested_product_ids: list[str] = field(default_factory=list)
    state: str = "pending"                  # pending | resolved | rejected
    resolved_product_id: str = ""
    created_at: str = ""
```

```python
class OfferSource(str, Enum):
    ...
    MEMBER_STATED = "member_stated"         # NEW — retail baseline the member reports
```

---

## 17. API changes

```
GET /api/products/search?q=<text>&limit=10
  → { "query": "vanilla whey",
      "results": [
        { "product_id": "prod_whey_vanilla",
          "name": "Gold Standard 100% Whey",
          "brand": "Optimum Nutrition",
          "variant": "Vanilla Ice Cream",
          "display_size": "5 lb (2.27 kg)",
          "image_ref": "/products/prod_whey_vanilla.webp",
          "image_attribution": "Open Food Facts contributors, CC-BY-SA",
          "has_supplier_offer": true } ],
      "snapshot_date": "2026-08-19" }

POST /api/products/unresolved
  body → { household_id, raw_text }
  → { request_id, state: "pending" }
```

`GET /api/needs` keeps returning its `products` array unchanged, so the existing frontend and
`test_api.py` keep passing during the transition. Deprecate it only after the new component ships.

Public-demo note: `/api/products/search` is read-only, computes nothing, spends no Bedrock tokens,
and takes no client-supplied instruction — it belongs in the **cheap deterministic quota bucket**,
and it must be added to the public route allowlist, whose method-and-path counts are pinned by
`test_the_published_endpoint_counts_are_the_real_ones`.

---

## 18. Frontend changes

- **`ProductSearch`** (new) — debounced combobox replacing the `<select>` in
  `views/needs.tsx:130`. Keyboard-navigable, ARIA-correct.
- **`ProductCard`** (new) — image, brand, name, size. Fallback glyph on missing image.
- **`UnresolvedItem`** (new) — the "can't find it?" path.
- **`api.ts`** — extend `ProductRow` with `variant`, `display_size`, `image_ref`,
  `image_attribution`, `has_supplier_offer`; add `api.searchProducts`.
- **Attribution** — a single line in the About view crediting Open Food Facts with a link, as
  ODbL requires for a Produced Work.

The rest of the form is already right and should not be redesigned: the two-number timing split,
the collapsed advanced section, and the "saving a need never commits money" copy all stay.

---

## 19. Agent/tool changes

**None required**, and that is a good sign — it confirms the seam is in the right place.
`list_latent_demand` buckets by `substitute_group` and is indifferent to where products came from.

One optional addition, only if the fallback path is built: a bounded, non-tool LLM call (not an
agent tool) that turns unresolved free text into structured attributes for the operator queue.
It must not run inside the coordinator loop, must not see the workspace, and must not write.

---

## 20. Migration plan

Strictly additive; each step independently shippable and revertible.

| Step | Change | Data migration | Tests affected | Back-compat |
|---|---|---|---|---|
| 1 | Add optional `Product` fields + `ProductSource` | **None** — `from_dict` defaults | none | full |
| 2 | Add `scripts/build_catalog.py` (OFF → SQLite artifact) | none, new artifact | new unit tests | n/a |
| 3 | Curated `CATEGORY_TO_GROUP` table | none | new mapping tests | n/a |
| 4 | Fetch + commit canonical images | none | none | n/a |
| 5 | Enrich the 6 seed products with real identity | seed rewrite, **same IDs** | `test_demo_scenario` re-verified | IDs stable |
| 6 | `GET /api/products/search` | none | new API tests; allowlist count pinned | additive |
| 7 | `ProductSearch` component | none | `needs.test.tsx` updated | `<select>` removed last |
| 8 | `ProductResolutionRequest` + unresolved flow | new entity | new service tests | additive |

**Canonical demo IDs and economics do not change at any step.** The offers, prices, case sizes,
MOQs, and every assertion in `test_demo_scenario.py` are untouched — only identity fields on
existing product rows gain values.

Steps 1–5 are the demo-visible win. Steps 6–8 can land after the deadline if time is short.

---

## 21. Testing plan

**Unit**
- `Product.from_dict` on a pre-migration dict yields correct defaults (proves back-compat).
- Search ranking: `"vanilla whey"`, `"ON whey"`, `"protein powder"`, `"whye"` (typo) each rank
  the canonical product first — pinned, so ranking drift is a test failure.
- `CATEGORY_TO_GROUP`: every canonical product maps to its expected group; an unmapped category
  yields empty `substitute_group`.
- **Unmapped group cannot match anything but itself** — the fail-closed guarantee, asserted
  directly against `evaluate_compatibility`.

**Integration**
- `POST /api/needs` with a searched `product_id` produces a need identical to the seeded shape.
- The public route allowlist count matches after adding the search endpoint.
- **Catalog artifact integrity:** every seed `product_id` exists in the SQLite artifact, and
  every `image_ref` resolves to a file that is actually present.

**Demo**
- `test_demo_scenario.py` passes **unchanged** — the strongest possible evidence the migration
  was additive.
- New: the whole search path makes **zero network calls** (assert with a patched socket).

**Explicitly not tested:** live OFF API behaviour. Nothing in the demo may depend on it.

---

## 22. Licensing / attribution requirements

| Source | Licence | Commercial | Attribution | Redistribution | Obligation on Pool |
|---|---|---|---|---|---|
| Open Food Facts data | ODbL 1.0 | ✅ | **Required** | ✅ under ODbL | App display = *Produced Work*: attribution only. **Committing the subset to a public repo = Derivative Database → that subset must be ODbL-licensed** |
| OFF images | CC-BY-SA | ✅ | **Required** | ✅ share-alike | Per-image attribution rendered in UI. ⚠️ May carry packaging copyright/trademark beyond the grant |
| USDA FDC | CC0 1.0 | ✅ | Not required | ✅ unrestricted | None |
| OFF images on AWS Open Data | as OFF | ✅ | Required | ✅ | None additional; free access |
| BLS AP series | Public domain | ✅ | Courtesy | ✅ | None |

**Concrete obligations if OFF is adopted:**
1. `data/catalog/LICENSE` stating the subset is ODbL 1.0, separate from the repo's MIT code.
2. A visible in-app credit linking to `openfoodfacts.org`.
3. `image_attribution` rendered wherever an image appears.
4. `README.md` noting the MIT-code / ODbL-data split.
5. Recommended: notify `reuse@openfoodfacts.org`, as OFF requests.

**Flagged as genuinely ambiguous — do not treat as settled:**
- Whether a *filtered subset* committed to Git triggers full ODbL share-alike on Pool's combined
  product table. Mitigation: keep OFF-derived rows in a physically separate table/file so the
  Derivative Database boundary is unambiguous.
- Whether CC-BY-SA on a photograph of branded packaging is sufficient for commercial display. It
  is fine for a labelled hackathon demo; it needs counsel before commercial launch.

---

## 23. Cost model

| Scale | Catalog | Search | Images | Embeddings | Cloud | **Total/mo** |
|---|---|---|---|---|---|---|
| **Hackathon demo** | $0 (bundled) | $0 (in-process) | $0 (repo assets) | $0 | existing Lambda | **$0** |
| **100 users** | $0 | $0 | $0 | $0 | existing | **~$0** |
| **1,000 users** | $0 | $0 | ~$0.10 (S3) | $0.02 one-time | +$1–3 Lambda | **~$3** |
| **10,000 users** | $0 | $0 | ~$2 (S3+CloudFront) | $0.02 one-time | +$20–50 | **~$50** |

The recommended architecture is **flat to about 10k users** because the catalog is a static
artifact and search is in-process. Costs only begin when the catalog exceeds Lambda-bundle size
(~250 MB unzipped) or query volume justifies a managed index — neither happens at any scale this
project will reach.

For contrast, the rejected options at 1,000 users: Nutritionix **$1,850/mo**; GS1 US **$7,000
first year**; OpenSearch Serverless classic **~$175–350/mo**; Vertex AI Search ~$2.50/1k queries
beyond the free tier.

---

## 24. Risks

**Technical**
- Lambda bundle size if the catalog subset is over-inclusive. *Mitigation:* filter hard to Pool
  categories; measure the artifact in CI.
- Search ranking regressions on catalog rebuild. *Mitigation:* pinned ranking tests (§21).

**Legal**
- ODbL share-alike scope on the committed subset — **flagged ambiguous** (§22). *Mitigation:*
  physical separation + explicit `data/catalog/LICENSE`.
- Packaging photographs carrying rights beyond CC-BY-SA — **flagged ambiguous**. *Mitigation:*
  attribution now; own photography before launch.
- Real brand names beside synthetic quotes implying a supplier relationship. *Mitigation:*
  unmissable "simulated quote" labelling, or option (b) in §14.

**Data quality**
- **OFF package size is unusable** (§5.1, evidenced). *Mitigation:* architecturally excluded —
  never imported into anything the economics engine reads.
- Brand casing inconsistency. *Mitigation:* normalize at build time; `SAME_PRODUCT_OTHER_VARIANT`
  compares normalized brand.
- Duplicate GTINs across EU/US variants. *Mitigation:* prefer US-country rows at build time.

**Demo reliability**
- Largely *eliminated* by bundling: zero external calls at judging time. The residual risk is a
  missing image file, covered by the fallback glyph and the artifact-integrity test.

---

## 25. Things explicitly rejected

| Rejected | Looked attractive because | Why it is wrong |
|---|---|---|
| **OFF live API for autocomplete** | Zero build step, always current | 10 req/min; docs explicitly warn against autocomplete; **returned 503 during this research** |
| **Vertex AI Search for commerce** | "Google's product search service" | Supplies **no data**; needs a catalog and user events Pool doesn't have; $2.50/1k for nothing gained |
| **Google Merchant / Content API** | Sounds like a product database | Manages *your own* listings — merchant catalog management ≠ global product search |
| **Amazon PA-API** | Huge catalog, images, prices | **Deprecated 2026-05-15, closed to new customers**; successor needs 10 affiliate sales/30 days |
| **OpenSearch Serverless** | "Proper" search, AWS-native | 2-OCU minimum on classic; even scale-to-zero NextGen is unjustified surface for <100k rows |
| **UPCitemdb / Go-UPC** | Huge barcode coverage with images | Amazon/eBay affiliate terms **forbid redistribution**; image provenance unclear |
| **Nutritionix** | Best-in-class US branded food data | $1,850/mo |
| **GS1 US** | The *authoritative* GTIN registry | $500 + $6,500 API add-on |
| **Instacart IDP** | Real US grocery catalog | 30–40 day approval; deadline is ~26 days out |
| **Scraping distributors** | Only path to "real" wholesale | ToS violation, legally exposed, unreliable — and wholesale is not the interesting claim |
| **LLM on the typeahead path** | Handles messy input elegantly | Latency, per-keystroke cost, non-determinism, AGENTS.md §3.3 |
| **LLM assigning `substitute_group`** | Scales to a large catalog automatically | Would let a model decide two people's purchases are interchangeable — the exact thing forbidden |
| **Vector DB (S3 Vectors / pgvector)** | Semantic search is the modern default | Brute-force over 50k precomputed vectors is faster and free |
| **Category-level needs** | Simpler for the member | Breaks case-boundary math; §48 no-speculative-surplus |

---

## 26. P0 / P1 / P2

**P0 — before the AWS demo (justified: this is the member's first interaction, and it is 20% of
the score under Design)**
1. Add optional identity fields to `Product` (additive, no migration).
2. `scripts/build_catalog.py` — OFF dump → filtered SQLite artifact with pinned snapshot date.
3. Curated `CATEGORY_TO_GROUP` table + fail-closed tests.
4. Fetch and commit images for the six canonical products from the AWS Open Data bucket.
5. Enrich the six seed products with real identity — **same IDs, same offers, same economics**.
6. `GET /api/products/search` (FTS5) + public allowlist entry.
7. `ProductSearch` + `ProductCard` replacing the `<select>`.
8. Attribution: `data/catalog/LICENSE`, in-app credit, README note.
9. Re-verify `test_demo_scenario.py` passes unchanged.

**P1 — Google adaptation / near-term**
10. Unresolved-item flow + `ProductResolutionRequest` + operator queue.
11. Gemini multimodal "photograph the item" resolution (the real Google differentiator).
12. BigQuery catalog build pipeline for the Google variant.
13. `OfferSource.MEMBER_STATED` retail baseline.

**P2 — pilot / post-hackathon**
14. Expand the catalog beyond demo categories; measure search recall.
15. Kroger integration for a geographically scoped real retail baseline.
16. Supplier portal (`SUPPLIER_SUBMITTED`) — the only honest path to real bulk data.
17. Own-photography programme to retire the image-licensing ambiguity.
18. Barcode scan (needs the Permissions-Policy camera denial revisited).

---

## 27. Final architecture

```
 BUILD TIME (offline, versioned, runs on a laptop — never at request time)
 ┌──────────────────────────────────────────────────────────────────────┐
 │ Open Food Facts dump  ──filter US + Pool categories──┐               │
 │   [REAL]  identity, brand, GTIN, category, image ref │               │
 │                                                       ▼              │
 │ USDA FDC (CC0) ──GTIN cross-check──▶  build_catalog.py               │
 │                                            │                         │
 │ CATEGORY_TO_GROUP  ──[DETERMINISTIC]──────▶│  substitute_group       │
 │                                            ▼                         │
 │ s3://openfoodfacts-images ──▶ resize ──▶ apps/web/public/products/   │
 │   [REAL, PINNED]                             catalog.sqlite (FTS5)   │
 └──────────────────────────────────────────────────────────────────────┘
                                    │  committed artifacts, pinned date
 ══════════════════════════════════ ▼ ══════════════════════════════════
 REQUEST TIME (zero external calls)

  Rosa types "vanilla whey"
        │ [HUMAN INTENT]
        ▼
  GET /api/products/search ──▶ SQLite FTS5 + synonyms
        │                       [DETERMINISTIC, ranked, reproducible]
        ▼
  product cards w/ local images ──▶ Rosa taps one
        │                            [HUMAN CONFIRMS — not the model]
        ▼
  product_id  ────────────────────────────────────────┐
        │                                             │
        ▼                                             │
  POST /api/needs ──▶ NeedDeclaration                 │
        │  [DETERMINISTIC WRITE — no money, no group] │
        ▼                                             │
  ┌─────────────────────────────────────────┐         │
  │  UNCHANGED CORE                         │         │
  │                                         │         │
  │  list_latent_demand                     │◀────────┘
  │    [AI DECIDES what to investigate]     │
  │         │                               │
  │         ▼                               │
  │  evaluate_compatibility  [DETERMINISTIC]│   substitute_group equality
  │  evaluate_timing         [DETERMINISTIC]│   pull-forward permission
  │         │                               │
  │         ▼                               │
  │  Offer  [SYNTHETIC, LABELLED]           │◀── ManualVerifiedOfferProvider
  │    unit_price, case_units, MOQ          │    (pilot path, already built)
  │         │                               │
  │         ▼                               │
  │  economics.py  [COMPUTED]               │   every figure, no exceptions
  │    fit_to_cases, host reward, fees      │
  │         │                               │
  │         ▼                               │
  │  viability.py  [DETERMINISTIC GATE]     │
  └─────────────────────────────────────────┘
        │
        ▼
  A worked-out pool Rosa never organised
```

**Legend.** `[REAL]` external, verified, pinned · `[SYNTHETIC]` invented and labelled ·
`[COMPUTED]` deterministic arithmetic · `[AI DECIDES]` model chooses *what to look at*, never
what is true · `[DETERMINISTIC]` pure function, tested · `[HUMAN]` the member's own act.

The model never crosses into a `[COMPUTED]` or `[DETERMINISTIC]` box. That boundary is unchanged
by this proposal — which is the strongest argument that the existing architecture was right.

---

## 28. Final recommendation

If this were my product, in this order:

1. **Build the catalog artifact first** (P0 #2). Everything else is downstream, and it is the only
   step with real unknowns — do it while there is time to discover that the OFF filter needs work.
2. **Enrich the six canonical products in place** (P0 #5). Same IDs, same offers, same economics,
   real names and real images. This alone transforms how the demo *feels*, and it cannot break the
   scenario because nothing the economics reads has changed.
3. **Ship the search box** (P0 #6–7). This is the actual product fix: the member stops picking
   from someone else's list and starts saying what they buy.
4. **Do the attribution properly** (P0 #8). It is twenty minutes, and getting it wrong is the one
   mistake here that is genuinely embarrassing.
5. **Then stop, and re-run the demo end to end.** If it is 2026-09-10 and steps 1–4 are done, ship
   that. The unresolved-item flow and Gemini multimodal are better as the *next* chapter than as a
   rushed one.

**What I would not do:** rewrite the product architecture. I went looking for a reason to and did
not find one. `Product` / `Offer` / `substitution` / `economics` are already separated along
exactly the lines this research says they should be. The defect is a missing layer *above*
`product_id`, not a wrong model beneath it.

**The single most important finding to carry forward:** Open Food Facts gives Pool real identity
and real images for free, and gives it *nothing* it can trust about package size — and Pool's
economics live entirely in package size. Keep those two facts apart and this works. Blur them and
Pool will compute a confident, wrong price.
