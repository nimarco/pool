# Hackathon scorecard

Maps Pool to the five equally weighted judging categories. Status words follow
`AGENTS.md`: **Implemented**, **Tested**, and **Deployed** are separate claims.

Competition facts were rechecked against the official Devpost overview, rules, FAQ and
resources on **2026-08-18**. Recheck again before submission.

Legend: ✅ complete with evidence · 🟡 partial / another gate remains · ⬜ human or future
work

## Submission requirements

| Requirement | Status | Evidence / remaining gate |
| --- | :-: | --- |
| Strands Agents SDK is load-bearing | ✅ | Real Strands event loop, hooks and seventeen typed tools (12 lifecycle, 3 cohort-strategy, 2 clarification) |
| Created during submission period | ✅ | Repository history begins 2026-08-15 |
| Repository pushed | ✅ | `origin/main` exists; final patch still must be pushed after QA |
| Repository publicly reachable | ⬜ | Human/private-window check before submission |
| MIT or Apache licence | ✅ | [`LICENSE`](../LICENSE), MIT |
| README | ✅ | [`README.md`](../README.md) |
| Architecture diagram | ✅ | [`architecture.svg`](architecture.svg) |
| Demo video ≤ 5 minutes | ⬜ | One-run rehearsal script exists; video intentionally not recorded yet |
| AWS Builder ID / entrant eligibility | ⬜ | Human-only checks |
| Live demo | ✅ | Deployed and verified **2026-09-02** at <https://d38kno05ygcarw.cloudfront.net/verify> — CloudFront distribution `EMOLZSGVY7HTN`, `Deployed` and enabled. This hostname is what fixes the DNS-level category block on `*.lambda-url.*.on.aws` that made the raw Function URL unreachable behind Cisco Umbrella and its peers (#0065); the Function URL remains the origin. Coffee and paper-towels flows re-driven end to end against it on 2026-09-02, both `model_provider=offline`, 0 model tokens |
| Problem, users and why it matters in video | 🟡 | Covered by the ~4:50 rehearsal script; recording remains |
| Good Neighbor framing | ✅ | Collective value inside an existing Community |

## 1. Technological Implementation

### Strongest evidence

- **Strands is foundational.** Remove the Strands event loop and hook provider and the
  coordinator no longer runs.
- **AI/deterministic separation is structural.** The model selects typed tools;
  deterministic services compute cents, quantities, eligibility, allocation, policy,
  state transitions and viability.
- **Autonomy is bounded.** Public runs allow 8 iterations, 25 tool calls, and 2 identical
  calls. The 45-second coordinator bound is cooperative and checked between steps; the
  bridge and Lambda own the outer 60- and 90-second deadlines.
- **The tool surface is narrow and classified from one source:** 4 read, 1 record, 6 act,
  1 end. There is no shell, arbitrary SQL or generic mutation.
- **Consequential operations are authorized and idempotent.** Candidate creation,
  authorization, capture, withdrawal, purchase, webhook delivery and pickup redemption
  have repeated-call tests.
- **Same-run causality is server-owned.** Candidate pools store `created_by_run`; the API
  follows that exact id to the stored run in the same workspace. The Product shows run
  id, pool id, tool sequence, **provider**, outcome, termination and authoritative
  readback. It never substitutes “latest run,” and the proof's vocabulary follows the
  stored provider — an offline run reports *planner iterations*, never model calls.
- **State is authoritative.** AgentCore and the public Lambda share one DynamoDB table
  with per-workspace leases, conditional writes, strongly consistent readback and TTL.
- **Historical proof is frozen, not reconstructed.** A coordination event records the
  clarification plan that shaped *that* declaration revision, so a later plan for the same
  member and product cannot re-describe an earlier one. Run→strategy listings are stored
  as transmitted for the same reason.
- **No fake demo logic.** The lifecycle, recovery, payment state machine and pickup
  credential flow execute through real services and stored state. Synthetic data and
  simulated rails are labelled.

### AWS status

| Component | Status |
| --- | --- |
| Amazon Bedrock / Nova Lite through Strands | **Verified live 2026-08-22** through AgentCore runtime **v7** — `us.amazon.nova-lite-v1:0`, run `run_787aa5b33e91`, 2 of 8 iterations, 5,513 in / 133 out tokens. Not repeated for the 2026-08-23 deployment. Outcome a truthful `no_action`: the declaration had already been served, so the objective was correctly empty. Establishes the deployment, the tool surface and the bounds on real infrastructure — **not** a live trace of the Kestrel→Harbourstone adaptation |
| The `/verify` judge path — declare → event → bounded run → order → proof | **Deployed and verified 2026-08-23** over HTTPS on the real table, on the final-audit release: declaration → event → run `run_8b635f43db71` → Kestrel refused `not_cheaper` (−$7.19 against retail), Harbourstone viable → `pool_39edddc37e7d`, 18 provisional units in 3×6 cases with 0 surplus, $69.18 saved (20.7%), 0 payment rows, provider `offline` at 0 tokens. Earlier the same path on 2026-08-22: `run_1b953d5eca25` → `pool_afb6982e61b7`. Earlier, locally and browser verified 2026-08-21: three fresh-workspace rehearsals — a short self-guided flow apiece, one clarification run and one coordination run each — plus two truthful no-action flows. **Runs the deterministic offline planner**, at zero model tokens |
| Immutable run→strategy history | **Locally verified 2026-08-21**: run A's listing is byte-identical after runs B and C |
| Reversible preferences (A→B→C) | **Locally and browser verified 2026-08-21**: distinct revisions, events and runs; withdrawal and restoration; zero payment rows |
| Amazon Bedrock AgentCore Runtime | **Deployed 2026-08-23** — `Pool_PoolCoordinator-TmVqSN9H56` **v8**, `READY`, `us-east-1`, carrying this branch. The only path to a live model. v8 has not been invoked; the live Nova Lite run below was against v7 |
| Lambda Function URL judge surface | **Deployed and verified 2026-08-23** — this branch; `/verify` hard-loads on every form; runs the offline planner at zero model tokens and holds no `bedrock:InvokeModel` |
| DynamoDB authoritative state | **Deployed and verified 2026-08-22** — one table shared by both artefacts |
| CloudWatch logs / structured run records | **Deployed and verified 2026-08-19**, retention bounded |
| Same-run proof presentation patch | **Deployed and rehearsed 2026-08-19**; exact pool/run relationship survived the completed lifecycle and reload. The `/verify` proof was **deployed and verified 2026-08-22** in the same session |
| EventBridge | Definition exists only in un-deployed pilot stack; **zero deployed rules** |
| Amazon Location | Adapter Implemented and Tested with fakes; live service unverified and absent from judge path |
| Payments and supplier purchase | **Simulated** everywhere — locally, in tests, and in the deployed stack |
| Host payout | **Absent**; compensation is computed and recorded, never claimed paid |

## 2. Design

- The Product is the main demo: Home, Pools, Needs and Community are member concepts, not
  judge navigation.
- A member's primary action is a recurring need declaration. There is no “create a group”
  or invitation flow.
- The one Product discovery action performs the one live AgentCore invocation. The exact
  resulting pool later exposes `Technical proof for this run`; `Run again` is collapsed
  and secondary.
- The wait state names AgentCore and the shared workspace without inventing intermediate
  progress.
- A three-actor grammar distinguishes agent choice, deterministic computation and human
  approval.
- Candidate economics stay estimated; final terms appear only after host acceptance and
  quote refresh.
- Authorized, funded, captured, ordered and paid-out are not treated as synonyms. Host
  compensation is labelled earned/recorded because no payout rail exists.
- The Community screen explains the operating model without implying an institutional
  partnership: **Community enables → Pool coordinates → Members choose and collect.**
- Demo controls are participant/scheduler scaffolding. They call real endpoints and do
  not set lifecycle state directly.

## 3. Potential Impact

Pool is designed as **recurring purchasing infrastructure for existing communities**.
Campuses are the initial wedge, not a core-domain assumption; apartment buildings,
neighbourhoods, workplaces and community organisations can provide the same useful
membership and pickup boundary.

The impact claim is bounded:

- people can reach viable bulk economics without one person organizing or holding
  speculative inventory;
- host work is included in landed economics rather than hidden or subsidized;
- the supplier receives one clean bulk order;
- attention is conserved by deterministic standing policies and exception-only asks; and
- every displayed impact figure is computed from synthetic records and labelled as demo
  data, not traction.

Real users, institutional partnerships and real transaction savings: **none claimed**.

## 4. Creativity & Originality

- **Latent-demand discovery:** nobody starts or names a group.
- **The organizer is automated, not the shopping conversation.**
- **Three-sided coordination:** buyers, bulk supply and local fulfilment work have to be
  viable simultaneously.
- **Permissioned timing pull-forward:** AI may investigate; deterministic timing policy
  decides who is eligible.
- **Exact case fitting:** zero speculative surplus is solved for, not merely checked.
- **Exact-gap recovery:** a failed authorization recruits only compatible demand needed
  to restore the threshold.
- **Same-run provenance:** the visible group-purchase record carries the causal id of the
  deployed agent execution that formed it.

## 5. Presentation

| Item | Status | Notes |
| --- | :-: | --- |
| Product / Showcase separation preserved | ✅ | Same components and state, different tour order |
| One-run ~4:50 rehearsal path | ✅ | [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) |
| Architecture diagram matches deployed path | ✅ | 24/40 routes, 45 s cooperative bound, tool kinds, zero EventBridge rules |
| Devpost draft current | ✅ | Includes deployment/simulation honesty table |
| Build history / resource ledger current | ✅ | Final patch, deployment, rehearsal and measured CDK asset storage recorded |
| Fresh deployed rehearsal | ✅ | One Product invocation: `run_3954c1d2d97f` → `pool_e36b32c84ee2`; no second invocation |
| Video recorded and public | ⬜ | Human-only final production and private-window check |

## Bonus: Builder Center articles

Up to +0.6 was confirmed on the official site. Three article outlines exist in
[`ARTICLE_NOTES.md`](ARTICLE_NOTES.md). Publication and acceptance remain human work;
recheck the current title requirement immediately before publishing.

## Current gate

The visual and UX finishing pass is done (`BUILD_HISTORY.md` #0051): the Showcase reads as
one sheet with the quantity drawn rather than narrated, Behind Pool is ordered for a judge,
the order record answers a member before an operator, and colour is semantic again. Verified
rather than asserted — 0 contrast failures across 444 rendered pairs in both themes, 0 focus
stops without a ring under real Tab traversal, no target under 24x24, and three demo
rehearsals from reset that were byte-identical.

The live app is self-testable, and **the way it is tested changed** (#0057). The scripted
judge demo asked a visitor to load a fixture, record a supplier quote and press "run
agent" — four clicks whose only purpose was advancing a demo, which is the thing a
sceptical reader is trying to see past. It still exists at `/judge` for regression and is
no longer in navigation.

Verification is now **`/verify`**: a fresh synthetic community that already contains
fragmented coffee demand, and then the ordinary product. A judge adds a coffee they buy,
answers questions *about coffee* — whole bean, caffeinated, which roasts — and saves. That
single save is the only causal action. Pool lists two orders it could assemble, costs the
one with more demand behind it, is refused on landed economics, costs the other, and forms
it; Home changes, *Why this order?* explains both verdicts and the aggregate exclusions,
and *Technical proof for this run* shows the same event, run, evaluation and pool ids with
the bounds each was inside. A reload changes none of it, because none of it is held in the
browser.

Browser-verified at 390×844 and 1280×720 against the local public-demo stack: event
`cev_ba48cbb0e450e9b8` → run `run_34720f1f9297` → pool `pool_d10604b82d23`, 18 units in
three whole cases, zero surplus, six members including the judge, $69.18 saved (20.7%),
and the refused option at −$7.19. Nothing was deployed and no model tokens were spent.

What remains is human-owned and none of it is claimed complete here: the public video,
repository visibility, the Builder ID, the Builder Center articles, and the submission
itself. `docs/IMPECCABLE_HANDOFF.md` is a redirect now, not a task list — the structure it
froze was replaced.
