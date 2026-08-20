# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Primary: a household member of one Community.** On the initial campus wedge this is
usually one student. Their situation is that they already buy certain things on a rough
cadence — coffee, rice, protein, paper towels — and they would benefit from bulk pricing
they will never organise. They are not shopping when they use Pool. They state what they
buy once, and afterwards their job is only to answer a question when Pool genuinely needs
a decision. Success for them is being handed a worked-out, feasible group order they never
asked anyone to arrange.

**Second, explicitly recorded: a hackathon judge**, and after that anyone evaluating
whether the autonomy claim is real. This audience needs to verify rather than use: what
Pool did on its own, what deterministic code proved, what the agent contributed, what
persisted, and what AWS evidence exists. They are served by dedicated destinations
(Behind Pool, Showcase, the Operations console), reached deliberately and never on the
member path.

**When the two conflict on a consumer surface, the member wins.** Depth goes behind a
door rather than onto their screen. Judge-facing destinations may be long and dense
because they are proof destinations, not member screens.

**Third, present in the domain but not the primary design subject: the host.** A paid
local fulfiller who collects the bulk order and distributes it. In v1 one person does
both jobs.

## Product Purpose

Pool is an autonomous collective-purchasing coordinator. People declare recurring
purchasing needs and constraints; Pool works in the background to find overlapping latent
demand inside a Community, evaluate whether a bulk purchase is genuinely worthwhile,
determine feasible allocations, recruit and pay a host, coordinate financial commitment,
handle routine recovery, and assemble a real transaction. It contacts a human only when a
decision actually requires one.

It exists because group buying fails for a reason software usually ignores: the
coordination labour is unpaid, tedious, and lands on one exhausted volunteer. That labour
— recruiting, comparing quantities, chasing non-responders, re-planning after a dropout,
arranging pickup — is exactly the work an agent suits.

Success is a member being *offered* a viable order they did not organise, and being
interrupted at most once to approve it.

## Positioning

**The user does not create the buying group. Pool discovers that a useful group can
exist.** A "create a group and invite your neighbours" flow is a product failure, not a
feature. This is the claim a neighbouring product cannot truthfully copy without
rebuilding around latent demand: the opportunity is never stated by anyone, so finding it
requires searching a space nobody asked about.

The second half, and the harder one: **Pool only coordinates transactions that are
independently viable for buyers, host, supplier and platform.** It never manufactures
viability by hiding costs, violating authorization rules, requiring speculative
inventory, or silently subsidising a participant. When the four sides do not work, the
correct product outcome is that no pool forms — and saying so is a feature. Removing an
obstacle does not buy a yes.

## Operating Context

- **Community is the fundamental boundary** — the local trust-and-density unit inside
  which Pool coordinates demand, hosts, pickup sites and schedules. Campuses, apartment
  complexes, neighbourhoods, workplaces. College campuses are the initial go-to-market
  wedge, not a domain assumption; pools do not form across Communities.
- **Quiet by default.** Pool runs in the background and surfaces only decisions useful to
  the person receiving them. Attention is the resource the product exists to conserve. A
  Pool that pings you six times to assemble one order has reproduced the problem it was
  built to remove. There is no group chat: routine communication is automated, and human
  messaging is exception-driven and transaction-scoped.
- **The member journey** is: say what you buy → Pool watches → Pool checks (on the
  Community's pool day, or on demand in the demo) → an order forms or is refused with a
  reason → at most one approval question → collect from a pickup point → reconciliation.
- **Evaluation context.** The judged artifact is a public web demo plus a repository, a
  README, an architecture diagram and a five-minute video. The demo is a continuous
  browser journey from a fresh workspace, recorded at roughly 1080p, in which supplier
  facts arrive as real committed CSV files that are really parsed.
- **Horizon: a hackathon submission built to survive into a real campus pilot.** Shipping
  for 2026-09-14, but the architecture must be a plausible real system rather than a demo
  harness with a UI painted on. Pilot-readiness constraints are live concerns to preserve,
  not deferred fiction.

## Capabilities and Constraints

**Canonical product invariants.** Each is asserted by tests; breaking one is a product
change, not a refactor.

1. Nobody creates the group; the primary input is a standing declaration of need.
2. Provisional participation is never financial commitment — declaring or joining never
   touches a card.
3. Host selection precedes final buyer authorization, because host pay is part of the
   buyer's price.
4. A final offer never rests on a stale quote.
5. Buyers fund everything — merchandise, fulfilment, processing, platform fee. Pool does
   not subsidise; the host does not front the purchase.
6. No speculative surplus. If case rounding would leave units nobody ordered, select a
   buyer set that fills whole cases, or do not lock.
7. Future demand moves only inside the window a member authorised.
8. Offering to host is not claiming the job; candidates are ranked and the best eligible
   one is offered the work.
9. Pickup is proved by the buyer's one-time credential, not asserted.
10. No group chat.
11. Contact details are private by default; sharing a pool is not consent to share an
    address.
12. Never fake Stripe, AWS or traction. Simulated things are labelled simulated
    everywhere they appear.

**Authority boundary.** The model may decide what information it needs, which safe tool
to call, what deserves investigation, when to escalate, and how to phrase a message. All
money, quantities, discounts, allocations, commitment state, threshold arithmetic,
authorization decisions and validation are computed by deterministic code. **A number
shown to a human came from a deterministic tool, never from the model.** Application and
database state is authoritative; agent memory is not, and is not used for anything
transactional.

**Terminology, reconciled with the code.** Consumer surfaces and internal registers use
deliberately different words, and the difference is load-bearing.

| Term | Meaning |
| --- | --- |
| **Pool** (capital) | the product itself |
| **order** | one concrete group purchase — the consumer word for a `pool` row |
| **Community** | the local trust-and-density boundary |
| **what you buy** | the consumer name for a standing need declaration |
| **product family** | a curated substitute group a member may declare instead of one SKU; the order still buys exactly one product |
| **host** | the paid local fulfiller (one word only — never "runner" or "fulfiller" in consumer copy) |
| **funded** | payment authorised for the exact final amount; only this counts toward a threshold |
| **provisional** | counted for discovery, not a commitment |
| **final offer** | the exact landed price, issued only after a host accepts and the quote is refreshed |
| **landed economics** | merchandise + host pay + processing + Pool fee — what the buyer actually pays |
| **pull-forward** | demand bought earlier than a member's normal restock, only inside the window they authorised |

**Consumer state grammar — five words, and no screen may re-derive them.**
*needs you · coordinating · ready to collect · watching · done*, decided server-side in
`services/relevance.py`, with the specific deterministic reason carried alongside. A
formed-but-excluded order is a **watching** state with its own reason, never a generic
failure. If a screen says "you", the server decided that.

**Constraints that bind design.**

- Real workflows execute. Synthetic *data* is expected; fabricated *behaviour* is banned.
  No progress animation that implies work the system did not do, no fake thinking, no
  fake tool progress.
- A member declares a family or an exact product; both intents stay expressible, and
  being handed a family member is fulfilment, not a substitution. Never call it a swap.
- Public-demo economics are content-addressed: uploaded supplier bytes must hash-match a
  committed fixture, so nobody can steer the numbers. The parser is always real.
- Cost safety is a hard constraint. Bounded loops, no polling, no always-on compute, no
  paid call on a page render.
- **Undecided product facts, recorded rather than invented:** merchant-of-record for real
  purchasing; what happens to unclaimed paid-for goods; whether the platform fee model
  (10% of gross savings) is defensible; whether deterministic travel times resemble real
  ones.

## Brand Commitments

- **Name:** Pool. The wordmark glyph is a ring of separate people around a single pooled
  order — the product in one shape, with the centre deliberately reading as a person's
  order rather than as automation.
- **Voice:** plain, specific, and never stronger than the evidence. Say what is real,
  what is synthetic and what is simulated, in the interface and not only in the docs.
  Never say "deployed", "paid", "captured", "final" or "permission" more strongly than
  the screen supports. Never show a number the system did not compute.
- **A refusal is spoken as a result, not an error.** "There is enough demand and it still
  would not be cheaper" is the product working.
- Implementation nouns stay out of consumer copy: no "workspace", "declaration",
  "coordinator", "run", "scan" or row counts shown to buyers. Those words are correct on
  operator and judge surfaces and a judge needs them there.
- An incumbent visual system already exists and is not documented here by design (see
  `/impeccable document`): a token layer in `apps/web/src/styles.css`, a shared primitive
  set in `apps/web/src/ui.tsx`, brand marks and one explanatory figure in
  `apps/web/src/brand.tsx`, and Instrument Serif as the only web font dependency.

## Evidence on Hand

Real, and safe to rely on:

- **A real product catalogue** — 295 products and 20 human-curated substitute families,
  snapshot 2026-08-19, from Open Food Facts / Open Beauty Facts / Open Products Facts
  under ODbL-1.0 (data) and CC-BY-SA-4.0 (images). Attribution is required and already
  carried in `catalog.json`. Package sizes there are display text and are never used in
  economics.
- **Committed supplier sheets** — `demo-data/riverbend-split-case.csv`,
  `demo-data/riverbend-case-programme.csv`, `demo-data/MANIFEST.json`. Really parsed,
  digest-pinned, imported in that order.
- **A deployed public demo** on AWS Lambda + DynamoDB, with the coordinator on Amazon
  Bedrock AgentCore Runtime: `https://5hhaadit5pdarllqmbj24u4ybm0ixsyj.lambda-url.us-east-1.on.aws/`
- **Stored proof of real invocations** — run ids, `created_by_run` lineage on the
  resulting pool, tool sequences, outcomes, terminations, and authoritative readback from
  the same workspace the browser reads.
- **A large executed test suite** — 975 agent tests (verified by collection),
  plus infra and web suites, reported green at 1,156 total in `BUILD_HISTORY.md` #0050.
- **A canonical lifecycle fixture**, not to be paraphrased or adjusted for presentation:
  11 memberships, 10 funded buyers, 1 authorization failure, 1 replacement, 24 units,
  2 cases, 0 surplus, $861.44 all-in against $1,127.76 retail, $266.32 saved, 23.61%,
  North Hall lobby.
- **An engineering record** — `AGENTS.md` (operating rules), `BUILD_HISTORY.md` (50
  entries, an AWS resource ledger and 18 tracked open questions), `docs/DEMO_SCRIPT.md`,
  `docs/ARCHITECTURE.md`.

Absences that future work must not fabricate:

- **No real suppliers.** Riverbend Wholesale does not exist. Every supplier figure is
  synthetic and the interface says so.
- **No real money.** Payments are simulated; the Stripe provider refuses to construct
  without a test key, and no live charge has ever occurred.
- **No real users, no traction, no customers, no testimonials, no press, no pricing
  validation.** Demo University is invented and no real institution is named or implied.
- **No real households or addresses.** Every location is synthetic, and the map is
  projected from fixture coordinates rather than a tile service, because putting invented
  households on a real street map would be a more convincing lie, not a better map.
- **No live sourcing or scraping.** Supplier data arrives as operator-imported files.
- Screenshot, atlas and rehearsal artifacts from earlier passes **do not survive
  locally**; any before/after comparison must capture its own baseline.

## Product Principles

1. **Simple on the surface, extraordinary underneath — and only when asked.** The
   interface should make a viewer think: *I tell Pool what I buy, other people
   independently do the same, Pool notices when the overlap becomes actionable, it only
   coordinates when the numbers work, it handles the ugly details, and it interrupts me
   only when it genuinely needs me.* Depth is a destination, never a default.
2. **Represent the engine better rather than hiding it.** Every simplification must come
   from showing what the system already computes more truthfully — never from concealing
   what it does. The interface got simpler last pass by removing repetition, not evidence.
3. **A refusal is a result.** Pool's most distinctive behaviour is declining to act, with
   the reason attached. Design refusals as first-class outcomes with their own dignity;
   never dress one as a failure or an empty state.
4. **Say it once, on the object it belongs to.** One row per thing a member buys, and
   that row changes state. Duplication across sections is the defect that made a correct
   system look like an operations console.
5. **Never claim more than the system did.** No fabricated progress, no invented number,
   no unlabelled simulation, no word stronger than the evidence. This constrains motion
   directly: motion may show what changed, and may not imply work that did not happen.

## Accessibility & Inclusion

**Target: WCAG 2.2 AA.** Binding on future passes, and specifically on the motion work
now beginning:

- Contrast at AA for text and meaningful non-text; no meaning carried by colour alone —
  a state must be readable from its word, not only its dot.
- Full keyboard operability with visible focus, including the tab strips, drawers and
  disclosures that carry most of the depth.
- `prefers-reduced-motion` honoured for every animation added; the information must
  survive with motion off, because motion explains change and is never the only carrier
  of it.
- Live regions used where content changes without a navigation, and dense proof surfaces
  given real heading structure rather than visual grouping alone.
- The map degrades to a list for screen readers and on small viewports.

Current state is partial and should be treated as a floor to raise: across roughly 17k
lines of frontend there is one `prefers-reduced-motion` rule and two `aria-live` regions.
