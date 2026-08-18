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
| Strands Agents SDK is load-bearing | ✅ | Real Strands event loop, hooks and twelve typed tools |
| Created during submission period | ✅ | Repository history begins 2026-08-15 |
| Repository pushed | ✅ | `origin/main` exists; final patch still must be pushed after QA |
| Repository publicly reachable | ⬜ | Human/private-window check before submission |
| MIT or Apache licence | ✅ | [`LICENSE`](../LICENSE), MIT |
| README | ✅ | [`README.md`](../README.md) |
| Architecture diagram | ✅ | [`architecture.svg`](architecture.svg) |
| Demo video ≤ 5 minutes | ⬜ | One-run rehearsal script exists; video intentionally not recorded yet |
| AWS Builder ID / entrant eligibility | ⬜ | Human-only checks |
| Live demo | ✅ | Deployed Lambda Function URL; recheck from a private browser after final deploy |
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
  id, pool id, tool sequence, model, outcome, termination and authoritative readback. It
  never substitutes “latest run.”
- **State is authoritative.** AgentCore and the public Lambda share one DynamoDB table
  with per-workspace leases, conditional writes, strongly consistent readback and TTL.
- **No fake demo logic.** The lifecycle, recovery, payment state machine and pickup
  credential flow execute through real services and stored state. Synthetic data and
  simulated rails are labelled.

### AWS status

| Component | Status |
| --- | --- |
| Amazon Bedrock / Nova Lite through Strands | **Deployed and verified** |
| Amazon Bedrock AgentCore Runtime | **Deployed and verified**, `READY`, `us-east-1` |
| Lambda Function URL judge surface | **Deployed and verified** |
| DynamoDB authoritative state | **Deployed and verified** |
| CloudWatch logs / structured run records | **Deployed and verified**, retention bounded |
| Same-run proof presentation patch | **Deployed and rehearsed**; exact pool/run relationship survived the completed lifecycle and reload |
| EventBridge | Definition exists only in un-deployed pilot stack; **zero deployed rules** |
| Amazon Location | Adapter Implemented and Tested with fakes; live service unverified and absent from judge path |
| Payments and supplier purchase | **Simulated** in deployed demo |
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

The structural pass is frozen: architecture, deployed Product, same-run evidence and
submission narrative are aligned, and the one-run rehearsal passed. The next engineering
task is the bounded `/impeccable` visual/accessibility pass in
[`IMPECCABLE_HANDOFF.md`](IMPECCABLE_HANDOFF.md). The public video, repository visibility,
Builder ID and submission remain human-owned checks; none is claimed complete here.
