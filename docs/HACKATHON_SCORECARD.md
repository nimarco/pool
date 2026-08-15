# Hackathon scorecard

Maps Pool to the five judging categories. **Nothing here is marked complete unless it
actually is.** Requirements verified against <https://agentsforhumans.devpost.com/> on
2026-08-15 — re-verify before submitting.

Legend: ✅ done · 🟡 partial · ⬜ not started · ❌ blocked

---

## Submission requirements

| Requirement | Status | Notes |
| --- | :-: | --- |
| Built with Strands Agents SDK | ✅ | `strands-agents 1.52.0`. Core loop, tool surface, and the bounds hook are all Strands primitives — not a wrapper |
| Newly created in the submission period | ✅ | Repo initialised 2026-08-15; full git history |
| Public repository | ⬜ | Not yet pushed to GitHub |
| MIT or Apache license visible | ✅ | [`LICENSE`](../LICENSE) — MIT |
| README | ✅ | [`README.md`](../README.md) |
| Architecture diagram | ✅ | [`architecture.svg`](architecture.svg), source [`architecture.mmd`](architecture.mmd) |
| Demo video ≤ 5 min | ⬜ | Script written: [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md). Not recorded |
| AWS Builder ID | ⬜ | User action — account signup |
| Live demo URL | ❌ | Infrastructure written and synth-verified; no AWS credentials available to deploy |
| Project description | ✅ | Draft: [`DEVPOST_DRAFT.md`](DEVPOST_DRAFT.md) |
| Testing instructions | ✅ | README → Testing; `make test`, `make test-demo` |
| Good Neighbor track positioning | ✅ | Explicit in README, landing page, and Devpost draft |

---

## 1. Technological Implementation

**Strongest evidence:**

- **Strands is load-bearing.** The agent loop, the seven typed tools, and the safety
  system are all Strands primitives. `BoundedRun` is a real `HookProvider` subscribing to
  `BeforeModelCallEvent`, `BeforeToolCallEvent`, `AfterToolCallEvent`, and
  `AfterModelCallEvent`. Remove Strands and the project does not run.
- **A genuinely adaptive loop.** The agent chooses which product to investigate, which
  pickup site, whether a result is worth acting on, whether to recover a broken pool, and
  when to stop with no action. It is not `if quantity > 80: create_pool()`.
- **A hard AI/deterministic boundary.** Money, quantities, thresholds, allocations, routes,
  and authorization are computed in pure modules that cannot import a model client.
- **Bounded autonomy, enforced not requested.** 8 iterations, 25 tool calls, duplicate
  detection, 3 retries, 120 s wall clock, 100-cell route matrix — all configurable, all
  tested by driving a deliberately-looping model through the real event loop.
- **Idempotency.** Duplicate create, withdraw, approve, and recover are each tested by
  calling them twice.
- **Observability.** Every run stores trigger, tool sequence, iteration count, termination
  reason, duration, and token usage — with no model reasoning text.
- **219 tests**, all offline and free.

| Item | Status |
| --- | :-: |
| Strands foundational | ✅ |
| Non-trivial adaptive agent loop | ✅ |
| Typed, narrow tools | ✅ |
| Deterministic domain separation | ✅ |
| Bounded autonomy | ✅ |
| Idempotency and invariants | ✅ |
| Tests | ✅ 219 passing |
| AgentCore Runtime deployment | 🟡 entrypoint written to the official contract; not deployed |
| Live demo | ❌ blocked on AWS credentials |
| Real Bedrock invocation | ❌ blocked on AWS credentials |
| Real Amazon Location call | ❌ blocked; response parsing tested against the service model |

**Honest gap:** every AWS integration is written and unit-tested, but none has run against
a live account. That is the single biggest thing standing between this and full marks here.

## 2. Design

**Strongest evidence:**

- A coherent consumer product, not a dashboard: landing page, neighbourhood view, pool
  detail, decision inbox, needs table, map, agent activity, impact.
- **Not a chatbot.** There is no chat box anywhere. The agent's output is a decision inbox
  and an activity feed.
- A real design system: paper-and-ink palette with one warm and one cool accent, serif
  display type against a sans UI face, tabular numerals throughout. Explicitly avoids the
  purple-gradient-and-sparkles AI house style.
- Dark mode, responsive down to mobile, `prefers-reduced-motion` honoured, skip link,
  focus-visible rings, ARIA progressbar on the threshold meter, keyboard-usable throughout.
- Empty, loading, error, disabled and busy states all designed.
- Microcopy carries the product thesis: *"Nothing needs you — Pool is working in the
  background."*

| Item | Status |
| --- | :-: |
| Coherent consumer product | ✅ |
| No chatbot dependency | ✅ |
| Needs / map / pool lifecycle / inbox / activity / impact | ✅ |
| Smart Join visible and explained | ✅ |
| Responsive, accessible, dark mode | ✅ |
| Empty / loading / error states | ✅ |
| Smart Join *editing* UI | 🟡 policies are displayed and enforced; editing is API-only |

## 3. Potential Impact

**Strongest evidence:**

- A specific, real problem with a named cause: bulk pricing is inaccessible to households
  because coordination labour, not software, is the bottleneck.
- A specific audience: neighbourhoods, apartment buildings, campuses, food banks, schools,
  small local organisations — the Good Neighbor track's actual subject.
- Quantified from computed state: $99.00 saved across 9 households (42.3%), 7 commitments
  made without interrupting anyone, 2 questions asked, 1 pool repaired.
- A credible path beyond the demo: supplier portal, negotiated offers, pickup-host
  compensation, and eventually direct demand aggregation with distributors.
- Limitations stated plainly in the README rather than hidden.

| Item | Status |
| --- | :-: |
| Specific problem and audience | ✅ |
| Savings computed, not asserted | ✅ |
| Coordination burden quantified | ✅ |
| Concrete demo scenario | ✅ |
| Plausible commercial path | ✅ |
| Realistic limitations documented | ✅ |

## 4. Creativity & Originality

**Strongest evidence:**

- **Latent demand discovery.** The system searches a space nobody asked about. There is no
  "create a group" button, by design — that flow would be a product failure.
- **The organiser becomes the agent.** Group buying is old; making the coordination layer
  itself autonomous is the new part.
- **Autonomous dropout recovery** that repairs the group without disturbing the people who
  did nothing wrong — "form tight, repair wide."
- **Machine-verifiable autonomy policy.** Smart Join is a pure function with a six-rule
  audit trail, not an LLM judging whether something feels close enough.
- **A genuine HITL subtlety:** if a recovery would push an existing member's share past
  their own cap, Pool asks instead of silently repricing them.

| Item | Status |
| --- | :-: |
| Latent demand discovery | ✅ |
| Autonomous group formation | ✅ |
| Automatic recovery | ✅ |
| Deterministic autonomy boundaries | ✅ |
| Not a recommender or chat wrapper | ✅ |

No "world's first" claims are made anywhere.

## 5. Presentation

| Item | Status |
| --- | :-: |
| Repeatable demo (`make demo`, one command) | ✅ |
| End-to-end scenario asserted by tests | ✅ |
| Architecture diagram | ✅ |
| Clear narrative | ✅ |
| Real agent trace visible in the UI | ✅ |
| Clean UI | ✅ |
| Demo script | ✅ written, ⬜ not recorded |
| Devpost submission | 🟡 draft written, not submitted |

---

## Bonus — Builder Center articles

Up to +0.6 (0.2 each). **All unpublished.** Material is being captured as it happens in
[`ARTICLE_NOTES.md`](ARTICLE_NOTES.md) and `BUILD_HISTORY.md`.

| # | Working title | Material | Status |
| --- | --- | :-: | :-: |
| 1 | Replacing the neighbourhood group-buy organiser with an AI agent | ✅ strong | ⬜ unpublished |
| 2 | Building Pool with Strands Agents and Amazon Bedrock AgentCore | 🟡 needs real deployment evidence | ⬜ unpublished |
| 3 | When should an autonomous agent ask permission? | ✅ strong | ⬜ unpublished |

⚠️ **Before publishing**, re-check the current Builder Center title and tag requirements
against the live rules — the competition changed its blog-post wording mid-event, so the
requirement recorded here may already be stale.

---

## The honest summary

Everything that can be built and proven without an AWS account is done and tested. The
remaining gap is a single category: **nothing has run in the cloud.** Closing it needs AWS
credentials, Bedrock model access, and roughly an hour — see *Remaining blockers* in the
handoff notes.
