# Final experience plan

The decisions this reconstruction pass implements, and the evidence behind each one. Written
before the code, kept as the record of *why* — not a status page. Status lives in
`BUILD_HISTORY.md`.

The system underneath is not the problem. The problem is that the interface makes a
correct system look like an operations console, and in two places it makes a correct
system look like a *contradictory* one. Every decision below is either "represent what the
engine already does" or "stop saying the same thing three times".

---

## 0. What the browser actually showed

Measured at 1280x720, 100% zoom, real rendering, no zoom-out. Viewport-heights (`vh`) are
`scrollHeight / 720`.

| Screen | vh | Primary CTA | Problem |
| --- | --- | --- | --- |
| Home, two items, after a run | **2.52** | `Run Pool again` at y=859 — **below the fold** | the same two items render **three times** |
| Home, pool formed | **2.87** | — | five stacked sections |
| Community, fresh account | **3.45** | `Open operations` at y=2277 | eight sections, nearly every figure `$0.00` |
| Operations | 2.98 | — | consumer nav still on screen |
| Onboarding search | 1.48 | `Add this` below the fold | catalogue browsing, not intent |
| Pools, one pool | 1.00 | fine | no marker that the pool is not yours |
| Pool detail | 1.44 | — | no marker either; five tabs; "11 deterministic checks" |

Three findings decided most of this plan.

**Home says the same thing three times.** After a run with two items, `POOL CHECKED`
lists both items with verdicts, `Still standing` lists both items again with demand counts
and blockers, and `What you buy anyway` lists both items a third time with cadence — which
is also, field for field, the whole of the Needs page (`home.tsx:939-970` and
`needs.tsx:647-687` filter and sort the same `api.needs()` response with the same
predicate). The frontend audit found 33 such duplications; this is the one a viewer sees
first.

**The centrepiece demo beat is one number, and it moves the wrong way.** The
changing-world sequence is the strongest thing this build does: same people, same
declarations, supply changes, the answer changes. On Home, the entire visible difference
between "no supplier" → "supplier found, still not worth it" → "viable" is the tail of a
sentence:

- before: `With yours, 24.`
- after quote A: `With yours, 24. The supplier's best price starts at 12.`
- after quote B: `With yours, 24. The supplier's best price starts at 16.`

The good quote makes the number go **up** (12 → 16, because the case-programme minimum is
higher), so the beat where Pool becomes able to act reads as a regression. The actual
verdict — *there is enough demand and it still would not be cheaper* — is rendered only on
**Needs**, under `AS THINGS STAND`, on a different screen. The presenter has to navigate
between two screens and verbally reconcile two different sentences at the exact moment the
argument lands.

**36 units of coffee demand produce nothing.** Run against the real engine: 12 members,
3 units each, all declaring some coffee, supplier minimum 18.

```
prod_coffee_beans  (Pike Place)      group='coffee'  bulk: 1690¢, min 18, case 6
prod_0025500304076 (Folgers)         group='coffee'  bulk: none
prod_0810063343040 (Death Wish)      group='coffee'  bulk: none

evaluate_opportunity(prod_coffee_beans) → viable=False  below_minimum
    matched_units=9   minimum_units=18
    rejected: "member accepts the exact product only" → 40 needs
```

Nine of twelve members are discarded at `domain/substitution.py:61-62` before timing or
geography is consulted. The product whose thesis is *Pool notices overlapping demand* is
configured so that overlapping demand does not overlap.

---

## 1. The Need abstraction — group-level declaration, exact fulfilment

**Decision: add a group-level declaration. Keep exact-only. Keep exact fulfilment.**

This is not a new capability. `SubstitutionPolicy.STRUCTURED_CATEGORY_MATCH`
(`models.py:87-98`) already pools a whole substitute group, `evaluate_compatibility`
already implements it (`substitution.py:98-102`), and the catalogue already carries **22
curated substitute groups** over 295 products (coffee 26, whey_protein 28, rice 13,
energy_drink 24 …). Flipping the same 12 members to that policy: `viable=True`,
`matched_units=36`, all 12 included. The mechanism works. Nothing in the UI can express
it, and nothing in the UI ever asks for it.

So the missing thing is a *declarable object*, not an algorithm.

Rejected alternative — **flip the default** to `STRUCTURED_CATEGORY_MATCH` (~6 lines).
It produces the right pools and the wrong sentences: `Membership.is_exact_product` becomes
false for the ordinary case, so every member gets told "a substitute for the Pike Place you
declared" when they never asked for Pike Place. It also silently widens authority for
declarations already stored. A default that makes the app apologise for doing what the
member wanted is the wrong default.

Rejected alternative — **category-only declarations**. Destroys a real intent. "I only
buy this exact product" is a true thing about real people, it is already modelled, and
`test_matching.py::test_exact_match_short_circuits_every_other_rule` pins it.

### What gets built

- `SubstitutionPolicy.GROUP_DECLARED` — a new enum member meaning *the member declared the
  family, not this row*. Distinct from `STRUCTURED_CATEGORY_MATCH`, which means *I named a
  product and will accept its relatives*. Those are different member intents and they need
  different sentences: "Pool chose Pike Place for your coffee" is fulfilment; "Pool
  substituted Pike Place for the Folgers you declared" is a substitution. Collapsing them
  is how the interface starts lying politely.
- `CompatibilityVerdict` gains `requires_disclosure`, splitting the overloaded `is_exact`
  flag (`substitution.py:32-39`), which currently means both "same product id" and "needs
  no disclosure". Group fulfilment needs the second without the first.
  `Membership.is_exact_product` keeps meaning literally what it says — stored data stays
  true.
- Group rows in the catalogue. The taxonomy already exists as
  `scripts/build_catalog.py:86-122` but is not emitted; `catalog.json` gets a `groups`
  array and `catalog.search` returns group rows beside SKU rows. Grouping stays curated by
  a human and pinned by `test_catalog.py::test_every_catalogue_group_is_one_a_human_wrote`
  — the model never decides two products are close enough (AGENTS.md §21).
- A group declaration stores the group's canonical exemplar as `product_id`, so
  `Membership.need_id` lineage (`relevance.py:28-31`) is untouched and `Pool.product_id`
  stays one exact SKU. **The pool still buys exactly one product.** That is the exact
  fulfilment, and it does not change.
- Fix `discovery.py:386-418`, which ranks a group's target by member count and never checks
  the target is sourceable. Today it is latent — it currently proposes Death Wish (no offer
  at all) the moment exact-only declarations outnumber sourceable ones. Group declaration
  makes every coffee declaration group-compatible, so target selection starts deciding
  everything.

Fail-closed is already guarded: `test_catalog.py:185-204` is parametrised over
`list(SubstitutionPolicy)`, so an empty `substitute_group` must combine with nothing but
itself under the new policy or the build breaks.

---

## 2. Search — say what you buy, then narrow if you care

Typing `coffee` today returns four SKUs, one of which is **Chobani Vanilla Coffee
Creamer**, which is not coffee. Only `prod_coffee_beans` carries "Pool can source this", so
a member's brand choice silently decides whether they get anything, and nothing on screen
says so.

**Decision:** the group is the first-class result.

```
coffee

  Coffee                                    ← group row, primary
  Pool watches 26 coffees in this family

  Or a specific product ›                   ← disclosure
    Starbucks   Pike Place Medium Roast
    Folgers     Classic Roast
    …
```

Picking the group → `GROUP_DECLARED`. Picking a SKU → `exact_only`, unchanged, and it
keeps saying when Pool cannot source that exact row. Both intents stay expressible; the
common one stops being three decisions deep.

"Pool can source this" moves off the SKU rows in the primary path. It is a deployment
fact, not a product fact (`catalog.py:115-120`), and as a badge on one brand it reads as an
endorsement.

---

## 3. Defaults and advanced preferences

An ordinary item should cost **one decision**: what, and roughly how much.

Kept on the main path: item, quantity, cadence. Everything else defaults.
Moved behind `Preferences ›`: minimum saving, maximum spend, per-unit ceiling, pull-forward
window, and the substitution row (which the group/SKU choice now sets implicitly).

Nothing is removed. `needs.test.tsx::"keeps the authorisation constraints available, and
unchanged, behind a disclosure"` already asserts this shape; it now covers more fields.

---

## 4. Terminology

| Now | Becomes | Why |
| --- | --- | --- |
| Pool (brand) / pool (the thing) / order | **Pool** = the product. **order** = what it makes. | one word did both jobs; nav said "Pools" for the object |
| declaration, declared, standing | what you buy, on your list | database register in consumer copy |
| host / fulfiller / "carrying it" | **host** | three vocabularies for one actor |
| run, coordinator, scan | Pool checked / Pool is checking | implementation nouns as button states |
| workspace | — (removed from consumer copy) | partition vocabulary on a member's wait screen |
| memberships ("6 on the record") | buyers | row counts shown to buyers |
| Economics (tab) | What it costs | engineering label on a consumer tab |
| outlook, opportunity | already translated — keep | "As things stand", "Pool found something" |

Operator and judge surfaces keep `offer`, `quote`, `run`, `evaluation`, `workspace`,
`created_by_run`. They are correct there and a judge needs them.

---

## 5. Information architecture

Every destination has to finish the sentence.

| Destination | This page exists so the user can… | Verdict |
| --- | --- | --- |
| **Home** | …see what Pool needs from them and what it is doing right now. | keep, rebuild |
| **Orders** | …see and act on the group orders they are in. | keep, renamed from Pools |
| **What you buy** | …manage the list of things Pool watches for them. | keep, renamed from Needs |
| Community | …*(cannot be completed for a member)* | **removed from primary nav** |

Community fresh is 3.45 viewport-heights and eight sections in which a new member's every
figure is `$0.00`. Its content is real and worth keeping — it is simply not consumer
content. It is the community's aggregate economics, an attention ledger, a
responsibility-boundary explanation, a money ledger, and a link to Operations. All of that
is judge proof.

**New: "Behind Pool"** — one judge/operator destination, reached from the footer and the
demo drawer, never on the member path. It absorbs: this community's aggregates and map,
the money ledger, the attention ledger, technical proof, the stage-by-stage walkthrough,
the Operations console, and Showcase. §29's "one coherent entry point", instead of proof
scattered across Community, Operations, Pool tabs, drawers and accordions.

---

## 6. Home

One job: **what needs me, what is happening, what is being watched.** Three bands, in that
order, and nothing else.

```
Needs you            → only when true. Approve $17.53. One question, price already worked out.
Happening now        → orders in flight, with their state
Watching             → one row per item on your list, each carrying its current state
```

Removed from Home: the community counters (`Members 24 / Standing needs 39 / Groups anyone
organised 0`), the activity feed, the duplicate item list, and the four-clause caveat
paragraph — which becomes a disclosure on the row it belongs to. Target: **≤1 viewport for
the ordinary case, CTA above the fold.**

The run report stops being a separate section. Each item is **one row that carries its own
current state**, with what the last check found as a secondary, dated line underneath.
Which brings us to the two things that must be visible at once.

---

## 7. One row per item, and it evolves

The status-continuity requirement (§19) and the one-frame requirement (§8) are the same fix.

```
┌─────────────────────────────────────────────────────────┐
│  Jasmine rice, 5 lb                          Watching   │
│  7 people nearby buy this · 24 bags                     │
│  ● No verified supplier yet                             │
│  Last checked 5:29 PM — no supplier to price against    │
└─────────────────────────────────────────────────────────┘
                          ↓ a supplier quote is recorded
│  ● Supplier found — still not cheaper                   │
│  Last checked 5:29 PM — no supplier to price against    │
                          ↓ a better quote is recorded
│  ● Ready to coordinate                                  │
```

Demand, blocker, and history in one frame, in that order, on the same object. The blocker
becomes a labelled line instead of the tail of a sentence, so `12 → 16` stops being the
beat. The dated "last checked" line is how history and present sit together without
history being rewritten (§42) — the run report keeps saying what that run found, because
that is what was true then.

---

## 8. Consumer state grammar

Five states. Everything the engine can conclude maps onto one of them, and the *reason*
rides along.

| State | Meaning | Deterministic sources |
| --- | --- | --- |
| **Needs you** | one question, already worked out | `HUMAN_APPROVAL_REQUIRED`; host question |
| **Coordinating** | an order exists and is moving | `formed_included`; `in_pool`; finding host → locked → purchased |
| **Ready to collect** | pickup window open | pickup states |
| **Watching** | standing, nothing to do | `declined`, `formed_excluded`, `viable_not_acted`, `not_investigated`, `no_supply`, `below_minimum`, `not_cheaper`, `not_matched`, `not_in_round`, `short` |
| **Done** | collected and reconciled | completed |

Reasons under **Watching**, each from a real reason code:

| Reason code | Line |
| --- | --- |
| `no_bulk_offer` / `no_retail_baseline` | No verified supplier yet |
| `below_minimum` | Not enough demand yet — *N of M* |
| `not_cheaper` | Supplier found — buying together would not be cheaper |
| `formed_excluded` | An order filled without your units |
| `not_in_round` | This round already filled |
| `not_matched` | the specific matcher reason, via `relevance.plain_reason` |

`formed_excluded` is a **Watching** state with its own reason, never a generic failure.
Which is the other contradiction.

---

## 9. "Formed but not for you"

Reproduced in the browser. Home is already honest about it — *"Pool formed an order for
Pike Place Medium Roast, and your units were not in this one. It filled 3 complete cases
exactly, and your units did not fit inside the boundary."* Then the member clicks through,
and the **Orders list and the order page carry no marker at all**: `6 buyers · 18/18 units`,
`Buyers 6 — everyone still in`, five tabs. Nothing says this order is not theirs. The
contradiction the prose fixed is reintroduced one click later.

Two fixes.

**Scope marker, server-decided.** Every order surface states whose it is. `relevance.py` is
already the single authority (AGENTS.md §8: "if a screen says *you*, the server decided
that"); the list row and the order header render it instead of dropping it.

**Draw the case boundary** instead of describing it.

```
Case 1  ██████    Case 2  ██████    Case 3  ██████     18 / 18 filled

Your +2  ░░                                            still on your list
```

Three sentences of case-fitting arithmetic become a diagram whose whole point is visible at
a glance: the cases are full, nothing is left over (invariant 6, no speculative surplus),
and the member's units are intact rather than lost.

---

## 10. Location and community discovery

Today: "Where are you?" → one button, `Continue in Demo University`. Honest, and it teaches
nothing about how the product works.

**Decision:** show the real interaction, with synthetic geography.

```
Pool works street by street.
                                    ← Pool is local; the people it finds share a pickup
[ Use my location ]  [ Explore the demo community ]

Communities near you
  Demo University       24 members · 4 pickup points · synthetic
```

`Use my location` is offered because it is the real product's path, and it says plainly
that the demo does not call the browser's geolocation API and has not guessed a position.
No real institution is named or implied. This keeps the privacy posture
(AGENTS.md §"Personal and location privacy") while showing the model: locate → discover
nearby communities → join one.

---

## 11. Map

**Decision: a real SVG map of the synthetic campus, projected from the actual fixture
coordinates. No tile service, no key, no new dependency.**

The current "Where everyone is" is a grey box with scattered dots and no ground truth.

The honest constraint drives the choice: **Demo University does not exist.** Rendering
invented households onto a real OpenStreetMap tile of a real city would be a more
convincing lie, not a better map — and it would add a dependency, a network call and a CSP
surface for the privilege. The fixtures already carry real `lat`/`lon` per household and
per pickup site; projecting those into a hand-drawn campus is a map of the actual data.

It answers: where are the people who buy this, where would we collect it, and how far is
that? Privacy: aggregated density and approximate points, jittered, never an address —
matching what the fixtures already promise. It lives in Behind Pool, not on Home, and
degrades to a list on mobile and for screen readers.

---

## 12. Transparent supply ingestion

The changing-world beat needs an external fact to arrive. Today it arrives via two
hardcoded `Record quote` buttons whose terms live server-side
(`services/supplier_updates.py`) — safe, and it looks exactly like a demo switch.

**Decision: real file ingestion, with content-addressed economic authority.**

`demo-data/supplier_quotes.csv`, committed and readable on GitHub:

```csv
product_id,supplier,unit_price_cents,case_size,min_units,source_ref,received_at
prod_rice_jasmine,Riverbend Wholesale,975,4,12,QUOTE-RICE-SPLIT,2026-08-19T14:02:00Z
prod_rice_jasmine,Riverbend Wholesale,625,8,16,QUOTE-RICE-CASE,2026-08-19T14:31:00Z
```

Real bytes, really parsed: the browser uploads the file, the server reads it, a CSV parser
runs, the schema validates, malformed rows are genuinely rejected and counted, the filename
and row counts on screen are the real ones, and valid rows become ordinary `Offer` rows with
visible provenance. No agent call happens because a file was imported.

**The security conflict is the interesting part.** The build deliberately refuses
client-submitted economics — `SupplierQuoteRequest` sets `extra="forbid"` so a request that
*tries* to send a price is rejected rather than quietly stripped. An unrestricted CSV
endpoint would hand that authority straight back, and a judge could upload `$0.01 rice` and
make Pool look brilliant.

Resolution: **the parser is always real; the authority is content-addressed.** A manifest
of committed fixture digests ships with the repo. In the public demo, uploaded bytes must
hash-match a listed fixture — a judge downloads the file from GitHub, uploads it, and
watches it parse for real; edit one price and it is refused, naming the reason. Locally,
where the operator already owns the process, arbitrary CSV is accepted. Both properties
survive: inspectable real ingestion, and economics nobody can steer.

Every row stays labelled synthetic. Riverbend Wholesale does not exist, and the UI keeps
saying so.

---

## 13. No demand injection

Hard requirement, and the reason the beat is evidence rather than a switch. During the
supply sequence, **nothing about people changes**: no buyer, no declaration, no membership,
no household. The standing demand pre-exists in the seed
(`data/seed.py` — six rice declarations before the visitor arrives). The only thing that
enters the world is supply.

To be proved by test, not by assertion: counts of households, memberships and declarations
identical before and after each import, and the prior run report byte-identical.

---

## 14. Reset and rehearsal

`POST /api/demo/reset` already exists and is already correct: it takes the workspace lease,
then `seed()` deletes every row in the caller's partition and reseeds it, so imported
quotes, runs and pools from a bad take all go, and the seeded independent demand comes
back. It is scoped to the caller's session workspace, so it cannot touch another session,
and Showcase runs in its own partition (`showcase_workspace()`).

Work needed is presentation, not mechanism: make it obvious and one click from the drawer
during a recording, and confirm by rehearsing the full sequence three times from reset.

---

## 15. Showcase

Keep the canonical lifecycle; stop rendering it as a log. It should read as one story —
independent demand → viable order → host → commitment → one authorisation failure →
quantity falls → compatible replacement → exact quantity restored → purchase → pickup →
reconciliation — with members, units, cases and money **drawn** rather than narrated.

Canonical economics do not move: 11 memberships, 10 funded buyers, 1 authorisation failure,
1 replacement, 24 units, 2 cases, 0 surplus, $861.44 all-in, $1,127.76 retail, $266.32
saved, 23.61%, North Hall lobby.

Separately: the rice fixture added for the changing-world story is seeded into the shared
fixture, so it appears inside Showcase's product universe too. Showcase should be
semantically clean; fixture isolation gets fixed without touching canonical economics.

---

## 16. Visualisation

Prose that becomes a picture, only where it removes explanation:

| Today | Becomes |
| --- | --- |
| "It filled 3 complete cases exactly, and your units did not fit" | case-boundary diagram (§9) |
| "6 members have independently declared… — 22 bags. With yours, 24." | demand accumulating to a threshold |
| "no supplier" → "not cheaper" → "viable" | the same row's state changing (§7) |
| 24 → auth failure → 22 → replacement → 24 | one recovery strip |
| retail vs all-in vs saved | one comparison bar |

Motion earns its place by answering *what changed* — a state advancing on the row that owns
it, cases filling, a replacement entering. No fabricated thinking, no fake tool progress
(AGENTS.md §8), and `prefers-reduced-motion` honoured.

---

## 17. Order of work

Dependencies, not preference.

1. **Domain**: `GROUP_DECLARED`, `requires_disclosure`, catalogue group rows, the
   `discovery.py` target fix. Everything downstream renders its output.
2. **Search + declare**: group-first results, defaults vs preferences.
3. **State grammar**: one mapping from deterministic outcomes to five consumer states,
   server-side, so no screen re-decides it.
4. **IA**: nav, Home, Orders, What you buy, Behind Pool.
5. **Order surfaces**: scope marker, case-fit diagram, tab reduction.
6. **Ingestion**: CSV, manifest, provenance, operator UI.
7. **Location and map.**
8. **Showcase** and fixture isolation.
9. **Simplification pass**: kill the 33 duplications.
10. **Responsive, accessibility, motion.**
11. **Rehearse three times, then the matched atlas.**

---

## 18. Boundaries

Not touched: landed economics, allocation, zero-surplus case fitting, host compensation,
payment semantics, lifecycle rules, substitution *authority*, member relevance, agent
objective semantics, RunEvaluation history, `created_by_run` lineage, workspace isolation,
Showcase isolation, canonical flagship economics, AWS architecture.

This pass is local only. No deploy, no AgentCore invocation, no Bedrock call, no live
payment, no merge to main.
