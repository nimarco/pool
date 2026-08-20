# `/impeccable` handoff — superseded, kept as a redirect

**This document's contents are obsolete.** It froze a structure and a demo shape that later
implementation replaced. It is kept only so existing links resolve; the historical record of
what it once said, and of the passes run against it, lives in `BUILD_HISTORY.md` (#0034,
#0035) and is not reproduced here.

## What in it is no longer true

- **The `Home / Pools / Needs / Community` navigation is gone.** Consumer navigation is
  Home, Orders, and What You Buy. Community left the primary nav entirely and its content
  became **Behind Pool**, a judge/operator proof destination reached from the footer.
- **The one-run assumptions are gone.** The demo is no longer a single invocation of
  `Find opportunities` against the canonical whey scenario. The recorded sequence is the
  changing-world story: the same standing demand answered three times as supplier facts
  arrive, with two live invocations.
- **The "13-stage lifecycle reader" is wrong twice over.** The Showcase is a separate
  scripted lifecycle in its own workspace, and a successful run emits **14** steps, pinned
  by `tests/test_demo_scenario.py::test_the_whole_lifecycle_completes`.
- **"Needs as the primary input"** is now "what you buy", and a member may declare a
  product *family* rather than one SKU.

Its "Do not change" truth boundaries — domain semantics, economics, viability, the
model-versus-deterministic authority split, synthetic/simulated honesty, payment meaning,
and the ban on fabricated agent progress — do still hold. They are stated properly in
`AGENTS.md` and `PRODUCT.md`, which are the places to read them.

## Authoritative current context

| Source | What it governs |
| --- | --- |
| `PRODUCT.md` | durable product truth: users, purpose, invariants, vocabulary, evidence, accessibility target |
| `DESIGN.md` + `.impeccable/design.json` | the visual system. Normative, including where the CSS does not yet comply |
| `AGENTS.md` | operating rules. Cost and security sections are blocking constraints |
| `BUILD_HISTORY.md` | what actually happened, the AWS resource ledger, and open questions |
| `docs/DEMO_SCRIPT.md` | the current rehearsal and continuity rules |
| `docs/FINAL_EXPERIENCE_PLAN.md` | **design rationale written before implementation — why, not current state.** Not a todo list and not a status page |
| the running app | the last word on how anything actually looks and behaves |

## The rule that resolves conflicts

**Later implementation decisions override stale pre-implementation detail.** Where a
planning document and the shipped system disagree, the shipped system wins and the
document is the historical reason. Do not revert an implemented decision because an
earlier plan described something else — the two-sheet supplier sequence, which the plan
discussed as one CSV, is the standing example. Only a proven defect justifies reopening a
settled decision.

`DESIGN.md` is the one deliberate exception, and it says so in place: its colour doctrine
is normative and the current CSS has recorded deviations from it. Those are listed under
**Colors → Known deviations in the implementation** and are code work, not documentation
drift.
