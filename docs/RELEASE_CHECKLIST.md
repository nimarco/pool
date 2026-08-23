# Release checklist — AWS Agents for Humans

Everything that must be true before the submission is final, in the order it becomes
checkable. Most of it is not code, which is exactly why it needs a list: strong
engineering can still fail Stage One over a form field nobody filled in.

**Status vocabulary is AGENTS.md's.** `Verified` means someone observed it — a response,
a loaded URL, a screenshot. `TODO` means it has not been done. **A human-only item is
never marked verified by a coding agent**, however confident it is: an agent cannot see
a Devpost account, cannot own a Builder ID, and cannot confirm that a video plays for a
stranger. Those lines say `TODO (human)` and stay that way until a person changes them.

Deadline: **2026-09-14, 5:00 pm PDT.** Verified against
<https://agentsforhumans.devpost.com/> on 2026-08-18; re-verify before relying on any
line here for a submission decision.

---

## 1. Eligibility — pass/fail, Stage One

| Item | Status | Note |
| --- | --- | --- |
| AWS Builder ID exists, and its email matches the Devpost account | **TODO (human)** | Required to submit. Only the account owner can confirm this |
| Entrant eligibility (age, region, not an excluded party) | **TODO (human)** | Read the official rules; an agent cannot assess this |
| Project newly created inside the competition period | **Verified** | GitHub reports the repository created 2026-08-15; competition opened 2026-08-10. The full commit history is public |
| No undisclosed pre-existing code incorporated | **Verified** | Every commit is in this repository's history |
| Strands Agents SDK is load-bearing | **Verified** | `pool/agent/coordinator.py` runs the real event loop; `pool/agent/bounds.py` is a Strands `HookProvider`. Remove Strands and nothing runs |
| Public repository | **Verified** | <https://github.com/nimarco/pool> |
| MIT or Apache license visible | **Verified** | `LICENSE` (MIT), recognised by GitHub |

## 2. Required artifacts

| Item | Status | Note |
| --- | --- | --- |
| README with setup and run instructions | **Verified** | `README.md`; commands are the Makefile's and are run by `make qa` |
| Architecture diagram | **Verified** | `docs/architecture.svg`, hand-authored, readable at video resolution |
| Diagram distinguishes deployed from absent services | **Verified** | Solid judge path is deployed; dashed pilot components say implemented but not deployed; EventBridge says zero deployed rules |
| Public demo URL, reachable with no AWS account | **Verified** | <https://5hhaadit5pdarllqmbj24u4ybm0ixsyj.lambda-url.us-east-1.on.aws/verify> — the final-audit release, deployed and driven end to end 2026-08-23. Recheck from a private window before submitting |
| Demo stays free to test throughout judging | **TODO (human)** | Depends on credits lasting. `make cost-check` weekly; `make demo-kill` is the emergency stop |
| Public video, **5 minutes maximum** | **TODO (human)** | Not recorded. Must cover the problem, the users, and why it matters |
| Video is public and plays without a login | **TODO (human)** | Check in a private window before submitting |
| Devpost submission form complete | **TODO (human)** | Draft text in `docs/DEVPOST_DRAFT.md` — it is a draft, not a submission |

## 3. Builder Center articles — bonus, up to +0.6

Three qualifying public posts at 0.2 each. An August 12 rules update removed the hashtag
requirement while surviving wording still asks for **"Agents for Humans" in the title**;
the safe reading is to use that exact phrase and not depend on the hashtag.

| Item | Status | Note |
| --- | --- | --- |
| Article 1 — Strands, and the boundary that keeps money deterministic | **TODO (human)** | Outline in `docs/ARTICLE_NOTES.md` |
| Article 2 — a shared-state coordinator on AgentCore, and the consistency problem | **TODO (human)** | |
| Article 3 — bounding agent loops, projecting tool results, and cloud-only failures | **TODO (human)** | |
| Each is **public** and accepted before the deadline | **TODO (human)** | Publish with several days of buffer, not minutes |
| Each title contains "Agents for Humans" | **TODO (human)** | |

## 4. Engineering freeze

| Item | Status | Note |
| --- | --- | --- |
| `make qa` green — lint, typecheck, Python tests, web tests, build, secret scan | **Verified 2026-08-23** | 1,308 agent/API/domain tests, 75 infrastructure tests, 180 frontend tests — **1,563 total**; ruff, ESLint, TypeScript, production build, secret scan and secret-scan self-test all passed, no waived failures |
| Frontend lint actually runs | **Verified** | ESLint installed and wired into `make lint`; it was referenced but absent until 2026-08-18 |
| Infrastructure tests green | **Verified** | `infra/test_stack.py`, `infra/test_demo_stack.py` |
| Production dependency audit clean | **Verified** | `npm audit --omit=dev` → 0 vulnerabilities. Two dev-only Vite/esbuild advisories remain, fixable only by a major upgrade; deferred deliberately |
| One fresh Product-originated AgentCore run captured after final deploy | **Verified against runtime v7** | Workspace `w0z2b3v2r6c3b0q6l`; `run_3954c1d2d97f` → `pool_e36b32c84ee2`; exact `created_by_run`, stored tools and readback verified. **Not repeated after the 2026-08-23 v8 redeploy** — that deployment was code-only and deliberately spent no model tokens |
| Final-audit release deployed and smoke-tested | **Verified 2026-08-23** | AgentCore v7→v8 (same runtime id, IAM byte-identical), Lambda code-only update. Deployed `/verify`: Kestrel refused `not_cheaper` (−$7.19), Harbourstone viable → 18 units, 3×6 cases, 0 surplus, $69.18 saved (20.7%), 0 payment rows. Quantity 2 in a separate workspace → truthful `no_action`. Seeded-household create overridden to the consumer, amend refused 400, 0 victim events |
| Same live run remains the pool's technical proof after full lifecycle | **Verified** | Completed 10/10 handoffs, reloaded, and deep-linked from Home without using `Run again` |
| Historical proof is frozen, not reconstructed | **Verified 2026-08-23** | A → B → C over the real endpoints: flexible under plan A → `pool_1ea75c229c04`, 18 provisional units, 0 payment rows; a later plan B for the same member and product; A's proof still plan A. Exact-only revision shows no plan; the run→strategy listing is unchanged (#0063) |
| Public need creation cannot be pointed at a seeded household | **Verified 2026-08-23** | Reproduced against `d5ac806` and refused now: in public mode the server resolves the declaring identity, an amend naming another member's declaration is a 400, and no event is written for the named household (#0063) |
| The `/verify` proof never calls the offline planner a model | **Verified 2026-08-23** | Vocabulary derives from the stored `model_provider`; offline runs report *planner iterations* and 0 model tokens. Pinned both ways in `apps/web/src/views/why.test.tsx` |
| `/verify` offers no scripted-walkthrough diversion, and the form starts on the fixture's own quantity | **Verified 2026-08-23** | Pinned in `apps/web/src/views/verify-flow.test.tsx`; quantity 2 still produces the truthful no-action, quantity 3 forms the 18-unit order |
| Cost check — no schedules, no always-on resources | **Verified** | Account-wide EventBridge rule count is 0; one existing AgentCore runtime is `READY` and idle between invocations |
| Resource ledger in BUILD_HISTORY reconciled | **Verified** | No new logical resources; CDK staging bucket measured at 36 objects / 544,983,237 bytes |

## 5. Final tag and link verification

| Item | Status | Note |
| --- | --- | --- |
| Submission commit tagged and pushed | **TODO** | An immutable tag, linked from the README and Devpost, so later work cannot be mistaken for the submitted architecture |
| Every URL in the submission opened in a private window | **TODO (human)** | Repository, demo, video, articles, diagram |
| Demo exercised end to end on the deployed URL after the final deploy | **TODO** | Including 390 px mobile |
| Repository has no secret, and the scanner says so | **Verified** | `make secret-scan` and `make secret-scan-selftest` both pass |

---

## Not part of this submission

Recorded so nobody mistakes absence for oversight: real Stripe, host payouts, real
supplier ordering, production authentication, notifications, refunds, mobile/Capacitor,
and RevenueCat are all deliberately absent. `docs/PILOT_READINESS.md` says what a real
pilot would need first.

No user, host, or supplier validation has been performed. If any is done before the
deadline, record it there with the date and what was actually said — and never as a
quotation nobody gave.
