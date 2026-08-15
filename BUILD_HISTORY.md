# BUILD_HISTORY.md — Engineering Notebook for Pool

A factual, append-oriented development journal. **This is not a README and not a git changelog.**
Its purpose is to let us reconstruct the *truthful* development story later for:

- the three AWS Builder Center articles
- the Devpost submission
- the final README
- the architecture explanation
- the demo script
- the postmortem

The operating rules for the project live in [`AGENTS.md`](AGENTS.md). This file records what
actually happened.

---

## Rules for this file

**Read these before adding an entry.**

- **This history must remain truthful.** It is the primary source for public writing. A false entry
  becomes a false article.
- **Do not manufacture entries** for work that did not happen.
- **Do not claim a test passed unless it was actually run.**
- **Do not claim AWS infrastructure exists unless it was actually deployed.**
- **Do not claim a feature works because code exists.**
- **Distinguish clearly between planned, implemented, tested, and deployed** (vocabulary below).
- **Preserve failures and abandoned approaches.** These are the most valuable article material in
  the file. Do not tidy them away.
- Prefer **concise but information-dense** entries. Judgment and reasoning over narration.
- **Avoid enormous dumps of terminal output.** Quote the few lines that mattered.
- **Never include secrets.** No keys, tokens, credentials, or credential-bearing URLs — including
  inside pasted logs, traces, and screenshots.
- **Never include private user data.** Real addresses, real names, real contact details. Synthetic
  households only.
- **Do not rewrite old entries to make the project story look cleaner.**
- **Corrections are added explicitly** (see below), never applied by silent edit.

**Deserves an entry even when the visible change is small:**

- significant architecture changes (even when the UI barely moves)
- significant product decisions (even when little code changes)
- anything AWS-cost-related
- any change to autonomy or human-in-the-loop boundaries
- production or deployment incidents

**Does not need an entry:** meaningless formatting changes, renames, typos, formatter runs.

### Correcting an earlier entry

Do not edit the original. Append a new entry titled `Correction to #NNNN — <what was wrong>`, state
what the earlier entry claimed, what was actually true, and how we found out. Then add a single
line to the original entry: `> **Corrected by #NNNN.**` That one-line pointer is the only permitted
modification to a past entry.

---

## Conventions

**Order:** append-only, **oldest first**. New entries go at the bottom. Entries are numbered
sequentially (`#0001`, `#0002`, …) so they can be cross-referenced.

**Status vocabulary** — shared with `AGENTS.md`, used precisely:

| Term | Means |
| --- | --- |
| **Planned** | Decided, not written. |
| **Implemented** | Code exists and is runnable. Says nothing about correctness. |
| **Tested** | Verified by an actual executed test, fixture, or reproduced scenario. |
| **Deployed** | Actually running on AWS, verified by an observed response or trace. |

**Tags** — for finding article-worthy material later. Use only the tags genuinely relevant to an
entry. Do not spam every tag onto every entry; a file where everything is tagged is a file where
nothing is findable.

| Tag | Use for |
| --- | --- |
| `[ARTICLE-1]` | Concept and problem framing — why this is an agent problem. |
| `[ARTICLE-2]` | AWS and technical architecture — Strands, Bedrock, AgentCore, data. |
| `[ARTICLE-3]` | Autonomy and human-in-the-loop — act vs. ask. |
| `[DEMO]` | Material for the demo video or live demo. |
| `[ARCHITECTURE]` | Structural decisions and their consequences. |
| `[COST]` | Cost-relevant decisions, incidents, or bounds. |
| `[HITL]` | Human-in-the-loop and authorization semantics. |
| `[AGENT]` | Agent loop behavior, tool use, prompting, termination. |
| `[AWS]` | AWS service behavior, limitations, surprises. |

---

## Entry template

Copy this block for each new entry. Omit fields that genuinely do not apply — do not pad them with
"N/A" noise, but never omit a field to hide something.

```markdown
### #NNNN — [YYYY-MM-DD] — Short milestone title
`[TAG]` `[TAG]`

**Goal / user intent**
What we were trying to accomplish.

**Starting state**
What existed before this change, where relevant.

**Decision**
What architecture or product decision was made.

**Why**
Why this approach was selected, and what alternatives were considered and rejected.

**Implementation**
What materially changed. Status: planned / implemented / tested / deployed.

**AWS / external services touched**
Which cloud resources or services were actually used. "None" is a valid and common answer.

**Cost-relevant activity**
Meaningful paid AWS or model activity, unusual request volume, schedules created, browser/search
usage, or anything potentially persistent. Do not guess dollar figures if they are unknown —
describe the activity instead.

**Agent behavior** *(if applicable)*
Model/provider · tools available · tools called · iteration count and bounds · HITL behavior ·
termination condition · unexpected behavior.

**Validation**
Exactly how this was verified: tests run, fixture results, deployment checked, trace inspected,
API response verified, scenario reproduced. If it was not verified, say so plainly.

**Failures / dead ends**
What did not work, including approaches abandoned. Do not rewrite history to look clean.

**What we learned**
The concise technical or product lesson.

**Article fodder**
Which of Article 1 / Article 2 / Article 3 / demo / architecture diagram this may serve, and why.

**Evidence worth preserving**
Screenshots to capture, trace IDs or descriptions, architecture snapshots, benchmarks, test
output, before/after UI, interesting log output. Never store secrets or private data here.

**Relevant commits / files**
When known.
```

---

## Live AWS resource ledger

The one **mutable** section of this file. Every AWS resource created — including throwaway test
resources — is recorded here at creation time, per `AGENTS.md` §3.8. Rows move to *Destroyed* or
carry an explicit reason for remaining. Review this before ending any session that touched AWS.

### Active

| Resource | Service | Created | Purpose | Recurring cost? | Destroy by |
| --- | --- | --- | --- | --- | --- |
| _(none)_ | | | | | |

### Recurring / scheduled (highest risk — review every session)

| Resource | Schedule | Enabled? | Created | Kill switch | Destroy by |
| --- | --- | --- | --- | --- | --- |
| _(none)_ | | | | | |

### Destroyed

| Resource | Service | Created | Destroyed | Notes |
| --- | --- | --- | --- | --- |
| _(none)_ | | | | |

---

## Open questions / to verify

Tracked so they are not silently assumed. Move each to an entry when resolved.

| # | Question | Why it matters | Status |
| --- | --- | --- | --- |
| Q1 | Which Bedrock model tier is sufficient for the coordination loop? | Cost vs. reasoning quality; §3.3 says do not over-buy. | Open |
| Q2 | What state belongs in DynamoDB vs. AgentCore Memory? | `AGENTS.md` §6 sets the principle; the boundary is undecided. | Open |
| Q3 | Is AgentCore Runtime the right deployment target, or is plain Lambda sufficient? | Favorable for judging, but must be justified, not decorative. | Open |
| Q4 | Do we need a real routing/geocoding provider, or do synthetic distances suffice for the demo? | Live routing is a per-request paid call (§3.4). | Open |
| Q5 | How does a household express preauthorization (Smart Join) in a machine-verifiable way? | Core of Article 3; must not be an informal LLM judgment. | Open |
| Q6 | Re-verify hackathon requirements before submission. | Snapshot in `AGENTS.md` §2 is dated 2026-08-15. | Open |

---

## Entries

### #0001 — [2026-08-15] — Repository documentation foundation
`[ARTICLE-1]` `[ARCHITECTURE]` `[COST]`

**Goal / user intent**
Establish durable operating rules and a truthful historical record *before* serious development
begins, so that (a) any coding agent joining later has full context without chat history, and
(b) the eventual Builder Center articles can be reconstructed from a real record rather than
invented after the fact.

**Starting state**
Empty directory at `~/Desktop/pool`. No files, no hidden files, no git repository, no code, no
AWS configuration, no dependencies.

**Decision**
Create two documents and nothing else:

- `AGENTS.md` — operating manual for coding agents: mission, hackathon-aware engineering, AWS cost
  safety, security and privacy, agent architecture principles, source of truth, development
  discipline, no-fake-demo rules, observability, documentation duties, and an end-of-task checklist.
- `BUILD_HISTORY.md` — this file: append-only engineering journal with a fixed entry template,
  article tags, a live AWS resource ledger, and an open-questions table.

Deliberately **not** done in this task: no feature code, no scaffolding, no dependency choices, no
`git init`, no AWS calls of any kind.

**Why**
Two constraints shaped this. First, the hackathon requires the project to be newly created during
the submission period, so the record of *how* it was built starts now and has to be real. Second,
the project runs on student promotional credits, so cost rules need to exist before the first agent
loop is written — retrofitting bounds onto a running system is how credits get burned.

Writing the history rules *first* is the load-bearing choice: a journal started after the
interesting decisions have been made can only be a reconstruction, and a reconstruction is exactly
what we are trying to avoid.

Alternatives considered:

- *Single `AGENTS.md` with a history section* — rejected. Operating rules are read constantly and
  should stay short; the journal only grows. Mixing them buries the rules.
- *Start coding and document afterward* — rejected. This is precisely the failure mode the task
  exists to prevent.
- *Separate infrastructure ledger as a third file* — rejected to keep the deliverable to two files.
  The ledger lives at the top of this file instead, and is explicitly marked as the single mutable
  section of an otherwise append-only document. Worth revisiting if it becomes noisy.

**Implementation**
Two files created: `AGENTS.md`, `BUILD_HISTORY.md`. Status: **implemented** (documentation only —
nothing here is executable, so "tested" does not apply).

**AWS / external services touched**
None. No AWS account access, no SDK calls, no credentials read, no resources created.

**Cost-relevant activity**
Three HTTP fetches of public Devpost pages (hackathon overview, rules, resources) to verify
competition requirements rather than assume them. No paid API usage. No model inference beyond the
authoring session itself. No schedules, no persistent resources. This task was effectively
cost-free.

**Validation**
- Confirmed the working directory was empty, including hidden files, before writing.
- Hackathon facts recorded in `AGENTS.md` §2 were read from the official Devpost pages on
  2026-08-15, not recalled from memory. Marked in-file as a dated snapshot requiring re-verification
  before submission (tracked as Q6).
- No claim of tested or deployed status is made anywhere in this entry.

**Failures / dead ends**
None yet — this is the first entry. The absence of failures here is a fact about the task being
documentation-only, not a sign of a smooth project.

**What we learned**
The hackathon's scoring shape (five equally weighted criteria; Design and Presentation together
40%) argues for building observability and evidence capture into the process from the start rather
than treating them as end-stage polish. Explaining the system *is* 40% of the score, and the same
artifacts serve the demo, the README, and the articles.

**Article fodder**
- **Article 1** — the framing in `AGENTS.md` §1 (why group buying fails on coordination labor
  rather than on software, and why latent demand discovery is the agent-shaped part of the problem)
  is the seed of the article's thesis.
- **Article 2** — the cost-safety constraints will shape real architecture choices; documenting
  them before building means the article can show constraints driving design rather than
  rationalizing it afterward.
- **Article 3** — the act-vs-ask split in `AGENTS.md` §5 is the starting position. Its evolution
  under real implementation pressure is the article's actual content.

**Evidence worth preserving**
- This entry as the zero point of the build timeline.
- The initial act/ask split and the AI-decides/code-verifies table in `AGENTS.md` §5, for later
  before-and-after comparison once reality has pushed back on them.

**Relevant commits / files**
`AGENTS.md`, `BUILD_HISTORY.md`. No commits — the repository is not yet under version control.

---

### #0002 — [2026-08-15] — Version control and secret-leak prevention
`[COST]`

**Goal / user intent**
Put the repository under version control and make `AGENTS.md` §4 (never commit secrets) and the
§3.1/§3.2 cost bounds mechanically enforced rather than merely written down.

**Starting state**
Two documentation files, no git repository, no ignore rules. Nothing prevented a future `.env`
containing AWS keys from being committed to a repository that must eventually be public.

**Decision**
`git init` on `main`; add `.gitignore` with secrets patterns listed first and explicitly annotated;
add `.env.example` carrying the loop bounds and the `SCHEDULES_ENABLED=false` kill switch as
committed defaults.

**Why**
The hackathon requires a public repository, so a leaked credential would be public and permanent —
and git history keeps it after deletion. Ignore rules are worth more before the first `.env` exists
than after.

Putting the §3.1 bounds in `.env.example` rather than leaving them to code makes them visible on
first clone and adjustable without a code change, as §3.1 requires. `SCHEDULES_ENABLED=false`
ships as the committed default so the safe state is what a fresh environment inherits.

The `.gitignore` also excludes raw traces and logs, which for this product will routinely contain
household locations (§4).

**Implementation**
`.gitignore`, `.env.example`, initial commit on `main`. Status: **implemented** — the bounds are
declared configuration only; no code reads them yet.

**AWS / external services touched**
None.

**Cost-relevant activity**
None. No resources, no schedules, no model calls.

**Validation**
`git check-ignore` confirmed `.env` is ignored and `.env.example` is not. Confirmed the initial
commit contains only the four intended files.

**Failures / dead ends**
None.

**What we learned**
Nothing novel — but worth recording that the cost bounds existed as enforced defaults from the
first commit, since the alternative (retrofitting bounds onto a running agent loop) is the standard
way credits get burned.

**Article fodder**
Minor. Possibly a supporting detail for Article 2 on constraints shaping the build from the start.
Not a story on its own — recorded because it is security- and cost-relevant per the entry rules,
not because it is interesting.

**Evidence worth preserving**
None beyond the commit itself.

**Relevant commits / files**
`.gitignore`, `.env.example`. Initial commit on `main`.
