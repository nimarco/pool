# Hackathon scorecard

Maps Pool to the five judging categories. **Nothing is marked complete unless it actually
is.** Requirements verified against <https://agentsforhumans.devpost.com/> on 2026-08-15 —
re-verify before submitting.

Legend: ✅ done · 🟡 partial · ⬜ not started · ❌ blocked

Evidence is labelled by where it lives: **local** (runs here, verified), **ready**
(implemented, never run against the real service), **cloud-verified** (observed working on
AWS). Nothing is currently cloud-verified.

---

## Submission requirements

| Requirement | Status | Notes |
| --- | :-: | --- |
| Built with Strands Agents SDK | ✅ | Core loop, twelve-tool surface, and the bounds hook are Strands primitives. Remove Strands and nothing runs |
| Newly created in the submission period | ✅ | Repo initialised 2026-08-15; full git history |
| Public repository | ⬜ | Remote configured, not yet pushed |
| MIT or Apache licence visible | ✅ | [`LICENSE`](../LICENSE) — MIT |
| README | ✅ | [`README.md`](../README.md) |
| Architecture diagram | ✅ | [`architecture.svg`](architecture.svg), source [`architecture.mmd`](architecture.mmd) |
| Demo video ≤ 5 min | ⬜ | Script written: [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md). Not recorded |
| AWS Builder ID | ⬜ | User action — account signup |
| Live demo URL | ❌ | Stack written and synth-verified; **no AWS credentials configured**, so nothing is deployed |
| Project description | ✅ | Draft: [`DEVPOST_DRAFT.md`](DEVPOST_DRAFT.md) |
| Testing instructions | ✅ | README → Run it. `make qa`, `make demo` |
| Good Neighbor framing | ✅ | Explicit in README, landing page, demo script, Devpost draft |

---

## 1. Technological Implementation

**Strongest evidence (all local, all verified):**

- **Strands is load-bearing.** `BoundedRun` is a real `HookProvider` subscribing to
  `BeforeModelCallEvent`, `BeforeToolCallEvent`, `AfterToolCallEvent`, and
  `AfterModelCallEvent`. The tool surface is twelve `@tool` functions. This is not a
  wrapper around code that would work identically without it.
- **A genuinely adaptive loop.** The agent chooses which product to investigate, whether
  the result is worth acting on, whether to recruit a host, when to price exactly, which
  pool to repair, when to lock, and when to stop having done nothing. It re-reads its work
  queue after acting so it can see the consequences of its own decisions — capped, so
  alternation never becomes polling.
- **A hard AI/deterministic boundary that is structural, not stylistic.** `domain/`
  performs no I/O and imports no adapter. Money, quantities, package maths, host
  eligibility, Smart Join, and viability are pure functions. A model client cannot reach
  them.
- **Non-trivial deterministic work.** Exact-cent arithmetic with largest-remainder splits;
  a per-buyer processing gross-up so nobody is silently subsidised; a bounded exact search
  that picks the buyer set filling whole cases; a two-stage viability engine.
- **Bounded autonomy, enforced not requested.** 8 iterations, 25 tool calls, duplicate
  detection, 120 s wall clock, 100-cell route matrix — all configurable, all proven by
  driving deliberately misbehaving models through the real event loop.
- **Idempotency everywhere it matters.** Duplicate pool creation, authorisation, capture,
  withdrawal, purchase, and webhook delivery are each tested by doing them twice.
- **Payment state machine with real failure paths.** Authorise → capture at lock, with
  declines, capture failures, cancellations, replays, and stale-authorisation handling.
- **Observability.** Every run records trigger, tool sequence, iterations, termination
  reason, duration, and token usage — with no model reasoning text, and arguments stored
  as hashes so a run log cannot leak member details.
- **469 tests** (445 application + 24 infrastructure), all offline and free.

| Item | Status | Evidence |
| --- | :-: | --- |
| Strands foundational | ✅ | local |
| Adaptive, non-scripted agent loop | ✅ | local |
| Twelve typed narrow tools, no escape hatch | ✅ | local |
| Deterministic domain separation | ✅ | local |
| Bounded autonomy | ✅ | local, `test_agent_bounds.py` |
| Idempotency and invariants | ✅ | local |
| Payment lifecycle | ✅ | local (simulated provider) |
| Webhook verification and replay safety | ✅ | local |
| Quote freshness enforcement | ✅ | local |
| One-time pickup confirmation | ✅ | local |
| Comprehensive tests | ✅ | 469 passing |
| Bedrock real inference | 🟡 | **ready**, never invoked |
| AgentCore Runtime | 🟡 | **ready** (`agentcore_app.py`), never deployed |
| DynamoDB | 🟡 | **ready**, pinned by a fake-client test, never live |
| EventBridge background path | 🟡 | **ready**, ships disabled |
| Amazon Location | 🟡 | **ready**, never called |
| Real cloud trace | ⬜ | Needs credentials |

**Exact next action:** configure a non-root AWS identity, grant Bedrock model access, then
work down the verification order in the README.

---

## 2. Design

**Strongest evidence:**

- **Four surfaces, each shaped for its user.** Buyer (needs, candidate pools, decision
  inbox, final offer, pickup code), host (opportunity, live checklist, earnings
  breakdown), operator (offers, payments, purchases, issues), judge (landing page, one
  button that runs the whole story).
- **Judge Mode is frictionless.** No signup, no verification, no configuration. Enter,
  press one button, watch the entire lifecycle.
- **The money is the interface.** "Where the money goes" shows merchandise, host pay,
  processing, and Pool's fee as separate lines against the retail baseline. Hiding
  operating costs behind a headline discount would be the easy version; this is the honest
  one.
- **Reasoning is legible, not decorative.** Host candidates show their score components
  and the factual reason anyone is ineligible. The viability panel shows all eleven checks
  with their details, passed or failed.
- **Calm by default.** No polling, no badges, no engagement mechanics. The Decision Inbox
  is usually empty, and says so.
- **Deliberate visual language.** Paper and ink, one warm accent for "a human is needed",
  one cool accent for "Pool acted alone". No gradient-and-sparkle AI house style.
- **Verified responsive and dark-mode correct**, with no horizontal overflow at 375 px on
  any view.

| Item | Status |
| --- | :-: |
| Frictionless judge mode | ✅ |
| Buyer UX | ✅ |
| Host UX | ✅ |
| Operator UX | ✅ |
| Decision Inbox | ✅ |
| Transparent landed economics | ✅ |
| Agent trace visible | ✅ |
| Mobile responsive | ✅ |
| Dark mode | ✅ |
| Deployed and reachable | ❌ needs credentials |

---

## 3. Potential Impact

**Strongest evidence:**

- **The behaviour already exists.** Informal campus bulk-buying is real and its failure
  mode is well understood; Pool automates the part that makes it stop.
- **A truthful impact claim.** Bulk pricing favours whoever can afford a larger upfront
  purchase and has somewhere to put it. Pool lets several people reach that pricing
  without each carrying the capital, quantity, storage, and coordination alone. No
  charitable claim, no invented socioeconomic metric.
- **Precommitment instead of speculative inventory.** The goods are sold before they are
  bought. Nobody underwrites stock and hopes.
- **A paid fulfilment role**, priced by the work actually done, funded by buyers rather
  than subsidised.
- **Metrics computed from records**, labelled as synthetic demo data, and never presented
  as traction.
- **A plausible pilot path** documented in [`PILOT_READINESS.md`](PILOT_READINESS.md),
  with the unresolved questions named as legal rather than technical.

| Item | Status |
| --- | :-: |
| Real, observed problem | ✅ |
| Honest impact framing | ✅ |
| Campus wedge, community-general architecture | ✅ |
| No speculative inventory | ✅ |
| Transparent net savings | ✅ |
| Plausible supplier path | ✅ documented |
| Plausible controlled pilot | ✅ documented |
| Real users | ⬜ none, and none claimed |

---

## 4. Creativity & Originality

**Strongest evidence:**

- **Latent-demand discovery.** Nobody creates the group. That single inversion is the
  product, and it is what makes this an agent problem rather than a marketplace.
- **The organiser is the thing being automated** — not the shopping.
- **Three-sided coordination.** Buyers, bulk supply, and local fulfilment labour, in one
  transaction that only exists if all of them work.
- **Timing-aware demand pull-forward** with per-member authority. The agent decides
  whether to investigate; the deterministic engine decides who is actually eligible.
- **Case-boundary fitting as a solver**, not a validation. "Zero speculative surplus"
  becomes something the system can *achieve* rather than merely refuse.
- **Payment-failure recovery that replaces exactly what was lost**, because
  over-recruiting would trade a funding hole for surplus stock.
- **A three-verdict autonomy boundary** where `NOT_ALLOWED` is reserved for situations no
  prompt can fix.
- **The agent does something end to end** — discovery through physical handoff — rather
  than chatting about it.

| Item | Status |
| --- | :-: |
| Latent demand, no manual group creation | ✅ |
| Autonomous organiser replacement | ✅ |
| Three-sided coordination | ✅ |
| Timing-aware pull-forward | ✅ |
| Host recruitment and ranking | ✅ |
| Deterministic autonomy boundaries | ✅ |
| Payment-failure recovery | ✅ |
| Pickup completion | ✅ |
| End-to-end, not conversational | ✅ |

---

## 5. Presentation

| Item | Status | Notes |
| --- | :-: | --- |
| README explains the thesis | ✅ | |
| Architecture doc and diagram | ✅ | Diagram shows only what is built |
| Demo script | ✅ | [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md), timed to five minutes |
| Devpost draft | ✅ | With an honesty checklist attached |
| Pilot readiness | ✅ | [`PILOT_READINESS.md`](PILOT_READINESS.md) |
| Startup thesis | ✅ | [`STARTUP_THESIS.md`](STARTUP_THESIS.md) |
| Build history | ✅ | [`BUILD_HISTORY.md`](../BUILD_HISTORY.md) |
| Article notes | ✅ | [`ARTICLE_NOTES.md`](ARTICLE_NOTES.md) |
| Video recorded | ⬜ | |
| Public repo pushed | ⬜ | |
| Live URL in the video | ❌ | Needs credentials |

---

## Bonus: Builder Center article

Up to +0.6. Three drafts planned; see [`ARTICLE_NOTES.md`](ARTICLE_NOTES.md). Re-verify
the current title and content requirements before publishing.

---

## Honest summary

**Strong:** the agent architecture, the deterministic boundary, the economics, the
lifecycle, the safety bounds, the test suite, the four UX surfaces, and the honesty of the
documentation.

**Weak, and only for one reason:** nothing has run on AWS. Bedrock, AgentCore, DynamoDB,
EventBridge, and Amazon Location are all implemented and none is verified. There is no
live demo URL, and no video.

**The single highest-value unblock** is an AWS identity with Bedrock model access. Every
🟡 in this document becomes a ✅ or a specific known failure within an hour of that
existing — and a specific known failure would itself be worth writing about.
