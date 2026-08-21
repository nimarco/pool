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
| `[FRONTEND]` | Interface, information architecture, and how real behaviour is made legible. |
| `[SECURITY]` | Authorization boundaries, credential handling, privacy, and exposure surface. |

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

All of the below was created on **2026-08-16** by entry #0023, in account 860325090409,
`us-east-1`. Everything was enumerated by querying AWS after deployment, not by reading the
synthesized template — which is how rows 17–21 were found at all.

**CDK bootstrap — `CDKToolkit` stack (11 resources)**

| Resource | Service | Created | Purpose | Recurring cost? | Destroy by |
| --- | --- | --- | --- | --- | --- |
| `CDKToolkit` | CloudFormation | 2026-08-16 | Bootstrap stack, version 32 | No | Manual (see #0023) |
| `cdk-hnb659fds-assets-860325090409-us-east-1` | S3 | 2026-08-16 | Deploy staging bucket. Measured after the 2026-08-19 deployment pass: **43 objects, 648,260,603 bytes** (was 36 objects / 544,983,237 bytes on 2026-08-18 — three further deploys of two components, #0048). Every `agentcore deploy` and `deploy-demo` publishes hashed assets that do not expire automatically. Re-measure with `aws s3 ls s3://cdk-hnb659fds-assets-860325090409-us-east-1 --recursive --summarize` | **Yes — 618 MB of S3 storage at this measurement.** Growth is per deploy, not per request | Empty + delete before stack |
| `cdk-hnb659fds-container-assets-860325090409-us-east-1` | ECR | 2026-08-16 | Bootstrap image repo — **empty, 0 images** (CodeZip needs none) | No (empty) | With CDKToolkit |
| `/cdk-bootstrap/hnb659fds/version` | SSM Parameter | 2026-08-16 | Bootstrap version marker (`32`) | No (standard tier) | With CDKToolkit |
| `cdk-hnb659fds-cfn-exec-role-…` | IAM Role | 2026-08-16 | CFN execution — **holds `AdministratorAccess`** | No | With CDKToolkit |
| `cdk-hnb659fds-deploy-role-…` | IAM Role | 2026-08-16 | CDK deploy role | No | With CDKToolkit |
| `cdk-hnb659fds-file-publishing-role-…` | IAM Role | 2026-08-16 | Asset upload | No | With CDKToolkit |
| `cdk-hnb659fds-image-publishing-role-…` | IAM Role | 2026-08-16 | Image push (unused) | No | With CDKToolkit |
| `cdk-hnb659fds-lookup-role-…` | IAM Role | 2026-08-16 | Context lookups | No | With CDKToolkit |
| `CDKTo-FileP-dzcpx8KgZqLP` | IAM Policy | 2026-08-16 | File-publishing inline policy | No | With CDKToolkit |
| `CDKTo-Image-k0IS5jGSmRaE` | IAM Policy | 2026-08-16 | Image-publishing inline policy | No | With CDKToolkit |
| `cdk-hnb659fds-assets-…` bucket policy | S3 BucketPolicy | 2026-08-16 | Staging bucket access | No | With CDKToolkit |

**Pool AgentCore — `AgentCore-Pool-default` stack (4 resources, exactly as reviewed)**

| Resource | Service | Created | Purpose | Recurring cost? | Destroy by |
| --- | --- | --- | --- | --- | --- |
| `AgentCore-Pool-default` | CloudFormation | 2026-08-16 | Pool runtime stack | No | `make destroy-agent` |
| `Pool_PoolCoordinator-TmVqSN9H56` | Bedrock AgentCore Runtime | 2026-08-16 | Deployed coordinator, status `READY`. **Version 6** as of 2026-08-19 (#0048); was version 4 (#0031) | **No — billed per invocation only.** No always-on compute; idle session 60 s, max lifetime 300 s | `make destroy-agent` |
| `AgentCore-Pool-default-ApplicationAgentPoolCoordina-Ad6KX4akMhNd` | IAM Role | 2026-08-16 | Runtime execution role | No | `make destroy-agent` |
| `Agent-Appli-6NpmisJ95ByC` | IAM Policy | 2026-08-16 | Inline policy: Bedrock invoke, scoped Logs, X-Ray, config bundles | No | `make destroy-agent` |
| `ApplicationAgentPoolCoordinatorRuntimeAdditionalCustomPolicy03BEAE200` | IAM Policy | **2026-08-17** (#0030) | Inline policy from `services/agent/iam/agentcore-dynamodb.json`: `GetItem`, `PutItem`, `Query` on `table/pool-demo-state` and nothing else. Verified by `iam simulate-principal-policy`: `DeleteItem`, `BatchWriteItem`, `UpdateItem`, `Scan`, `DeleteTable` all `implicitDeny`, and any other table `implicitDeny`. **Region pinned to `us-east-1` on 2026-08-18** (#0031) — the resource ARN was `arn:aws:dynamodb:*:*:table/pool-demo-state`, granting the runtime a same-named table in every region for no reason. The account segment stays a wildcard deliberately: the role can only act in its own account | No | `make destroy-agent` |

**Created *outside* both stacks — `make destroy-agent` will NOT remove these**

| Resource | Service | Created | Purpose | Recurring cost? | Destroy by |
| --- | --- | --- | --- | --- | --- |
| `…runtime/Pool_PoolCoordinator-TmVqSN9H56/runtime-endpoint/DEFAULT` | AgentCore | 2026-08-16 | Default endpoint, `READY` | No | With runtime |
| `…workload-identity-directory/default/workload-identity/Pool_PoolCoordinator-TmVqSN9H56` | AgentCore | 2026-08-16 | Runtime workload identity | No | Manual |
| `/aws/bedrock-agentcore/runtimes/Pool_PoolCoordinator-TmVqSN9H56-DEFAULT` | CloudWatch Logs | 2026-08-16 | Runtime logs — **retention set to 14 days** (#0023 step E) | Yes — log storage, KB-scale | Manual `delete-log-group` |
| `/aws/application-signals/data` | CloudWatch Logs | 2026-08-16 | Created by Transaction Search — **was unbounded, set to 14 days** | Yes — ingestion + storage | Manual `delete-log-group` |
| `aws/spans` | CloudWatch Logs | 2026-08-16 | Transaction Search span store — 30 d (AWS default, finite) | Yes — ingestion + storage | Manual `delete-log-group` |
| **X-Ray Transaction Search** | X-Ray / CloudWatch | 2026-08-16 | **Account-level, set by AgentCore CLI 0.27.0, not by our template.** Destination `CloudWatchLogs` → **100 % span ingestion** (inherent, not configurable) | **Yes — per-GB span ingestion, account-wide.** The dominant charge | `aws xray update-trace-segment-destination --destination XRay` |
| **X-Ray `Default` indexing rule** | X-Ray | 2026-08-16 | **Separate account-level change by the same CLI call sequence.** `DesiredSamplingPercentage` raised **1 % → 100 %** for trace-summary indexing. Retained through the hackathon (Q18) | No separate ingestion charge; indexed-trace dimension only | `aws xray update-indexing-rule` (post-hackathon — see Q18) |

**The last two rows are the ones to watch.** They are the only things here that were not in
the reviewed four-resource plan: as a side effect of `agentcore deploy`, AgentCore CLI
0.27.0 enabled Transaction Search *and* raised the account-level `Default` X-Ray indexing
rule to `DesiredSamplingPercentage: 100.0`, printing one line about it. Both survive
`make destroy-agent`, and nothing in `agentcore/agentcore.json` asked for either.
CloudTrail timestamps both calls at **2026-08-16T19:50:23Z** — see Q18 for the full record
and for why they are deliberately retained through the hackathon. At Pool's invocation
volume the cost is negligible; the objection is that a deploy tool changed account-level
configuration, not the money. See #0023.

**No always-on compute exists.** The runtime bills only while an invocation is in flight;
six invocations totalling ~30 s of processing is the entire compute spend so far.

**Public judge demo — `PoolDemoStack` (8 resources, deployed 2026-08-16, entry #0025)**

**Live URL: <https://5hhaadit5pdarllqmbj24u4ybm0ixsyj.lambda-url.us-east-1.on.aws/>**

| Resource | Service | Actual name | Recurring cost? | Destroy by |
| --- | --- | --- | --- | --- |
| `PoolDemoStack` | CloudFormation | `stack/PoolDemoStack/65684040-99d9-11f1-bfd1-12dcf36da785` | No | `make destroy-demo` |
| `DemoApi` | Lambda, 1024 MB, **90 s** (was 30 s — #0028), **no reserved concurrency** (see below) | `PoolDemoStack-DemoApiE67238F8-NRdyivEjgNe9` | **No** — per invocation | With the stack |
| `DemoApi/FunctionUrl` | Lambda Function URL, `AuthType: NONE` | `https://5hhaadit5pdarllqmbj24u4ybm0ixsyj.lambda-url.us-east-1.on.aws/` | No | With the stack |
| `DemoState` | DynamoDB, PAY_PER_REQUEST, TTL `ttl` **ENABLED** | **`pool-demo-state`** — explicit physical name since 2026-08-17, so the AgentCore runtime (a different stack, a different tool) can name the same table. **Replaced** the generated-name table below | ~$0 — storage only, rows self-delete in 24 h | With the stack |
| `DemoLogs` | CloudWatch Logs, **14 days** | `PoolDemoStack-DemoLogs66B26719-oLVBNSrBt9aX` | Yes — KB-scale | With the stack |
| `DemoApi/ServiceRole` | IAM Role | `PoolDemoStack-DemoApiServiceRoleD1A1B4D5-kT16gVvbahFM`. **DynamoDB grant narrowed 2026-08-18** (#0031) from `grant_read_write_data` to the five actions the code issues — `GetItem`, `PutItem`, `Query`, `UpdateItem`, `BatchWriteItem`. Removed: `Scan`, `DeleteItem`, `DescribeTable`, `BatchGetItem`, `ConditionCheckItem`, `GetRecords`, `GetShardIterator` | No | With the stack |
| Role default policy | IAM Policy | `PoolD-DemoA-IgvYHVbqMZn9` — DynamoDB on one table, `InvokeAgentRuntime` on one runtime ARN | No | With the stack |
| 2 x invoke permission | Lambda Permission | `...-DemoApiinvokefunctionEB041109-WxR1cOdgWRyn`, `...-DemoApiinvokefunctionurl07DCB729-roeUn4lhuRUD` | No | With the stack |

**No reserved concurrency, and not by choice.** Lambda enforces
`account_limit - sum(reserved) >= 10`, and this account's limit **is** 10 — so any
nonzero reservation is rejected outright. The first deploy failed on exactly that and
rolled back cleanly, creating nothing. The ceiling still exists one level up: with no
other function in the account, the account's own limit of 10 caps this function.
`make demo-kill` (reserve **0**) is unaffected and was verified working — it returns
429 and deletes nothing.

**Verified after deployment, not assumed:** stack `CREATE_COMPLETE`; TTL `ENABLED` on
`ttl`, with a ~24 h horizon observed on real rows; log retention 14 days; **no implicit
`/aws/lambda/...` log group was created**; the X-Ray trace destination is unchanged from
#0023; no API Gateway, CloudFront, EC2 or RDS anywhere in the account; zero EventBridge
rules.

**The one growth surface:** the CDK staging bucket went from 2 objects / 41.7 MiB to
**13 objects / 176.8 MiB** across five deploy attempts (~28 MB zipped per bundle
version). Not garbage-collected; empty it before deleting `CDKToolkit`. **2026-08-17
(#0030): now 22 objects / 300.1 MiB** after three further deploys. It grows by ~28 MB
every time the bundle changes and nothing prunes it — the single largest standing
artefact this project has created.


### Recurring / scheduled (highest risk — review every session)

| Resource | Schedule | Enabled? | Created | Kill switch | Destroy by |
| --- | --- | --- | --- | --- | --- |
| _(none)_ | | | | | |

### Destroyed

| Resource | Service | Created | Destroyed | Notes |
| --- | --- | --- | --- | --- |
| `PoolDemoStack-DemoStateC0AFBE5F-MEYUG6F12SA` | DynamoDB | 2026-08-16 | 2026-08-17 | The generated-name demo table. Giving `DemoState` an explicit `table_name` is a replacing change, so CloudFormation created `pool-demo-state`, switched the function's grant and env to it, then deleted this one (`DELETE_COMPLETE`, 2026-08-17 19:38 UTC). Expected and reviewed in `cdk diff` beforehand; it held only disposable demo sessions with a 24 h TTL. `aws dynamodb list-tables` afterwards returns exactly one table. |

---

## Open questions / to verify

Tracked so they are not silently assumed. Move each to an entry when resolved.

| # | Question | Why it matters | Status |
| --- | --- | --- | --- |
| Q1 | Which Bedrock model tier is sufficient for the coordination loop? | Cost vs. reasoning quality; §3.3 says do not over-buy. | **Resolved (#0019, #0021)** — `us.amazon.nova-lite-v1:0` drove discovery correctly three runs of three, and the consequential recovery + lock branch correctly six runs of six, well inside every bound. One known rough edge, characterised in #0021 and tracked as Q16: in 1 of 12 coordinator runs it opened a turn with an invented pool identifier, which deterministic code refused without touching state. The documented default `us.anthropic.claude-haiku-4-5-20251001-v1:0` exists as an inference profile in the account but has still not been run. |
| Q2 | What state belongs in DynamoDB vs. AgentCore Memory? | `AGENTS.md` §6 sets the principle; the boundary is undecided. | **Resolved (#0004, #0008)** — AgentCore Memory is *not used*. Every piece of state Pool holds is transactional (commitments, money, quantities, membership, deadlines, policies), which §6 forbids putting in agent memory. Adding it would have been logo-collecting. Revisit only if durable learned preferences appear. |
| Q3 | Is AgentCore Runtime the right deployment target, or is plain Lambda sufficient? | Favorable for judging, but must be justified, not decorative. | **Resolved (#0009, #0022, #0023)** — both are implemented: Lambda serves the API, AgentCore hosts the coordinator. #0023 deployed it for real: **4 resources**, `READY` in 84 s, and six live invocations proving AgentCore Runtime → Pool entrypoint → Strands → Bedrock → Pool tools. AgentCore earns its place for the coordinator specifically — per-invocation billing with no always-on compute, session-scoped microVMs, and OTel tracing that shows tool spans without any code of ours. The honest caveat is that it cost a CDK bootstrap with an `AdministratorAccess` execution role and switched on account-wide Transaction Search unasked, neither of which plain Lambda would have. |
| Q4 | Do we need a real routing/geocoding provider, or do synthetic distances suffice for the demo? | Live routing is a per-request paid call (§3.4). | **Resolved (#0003)** — deterministic routing is the default so tests and demos are free; the Amazon Location `geo-routes` adapter is implemented and its parsing tested against the real service model. It has not been called live. |
| Q5 | How does a household express preauthorization (Smart Join) in a machine-verifiable way? | Core of Article 3; must not be an informal LLM judgment. | **Resolved (#0004)** — six numeric/boolean rules evaluated by a pure function returning a full audit trail. Stricter-of-policy-and-need wins. Every rule has a test proving it can block an auto-join. |
| Q6 | Re-verify hackathon requirements before submission. | Snapshot in `AGENTS.md` §2 is dated 2026-08-15. | **Open** — still required before submitting, and specifically before publishing any Builder Center article (the blog-post wording changed mid-event). |
| Q7 | Does the deterministic routing model resemble real travel times? | The demo shows travel minutes as if they were real. | **Open** — blocked on live AWS. Until then the provider is labelled in the API response and the UI. |
| Q8 | What is the actual per-run Bedrock cost at the configured bounds? | Determines whether a 6-hourly schedule is affordable. | **Measured (#0019, re-measured #0020, extended #0021)** — a discovery run is 6 ConverseStream calls, ~19.2k input / ~490 output tokens, ~5.5 s after the tool-result projection (was ~35.7k / ~420 / ~6 s). A recovery run is 4–5 calls and 11.3k–14.5k input tokens; a lock run 3–6 calls and 7.1k–17.0k. The consequential branches are **cheaper** than discovery — they read a 468-byte work queue instead of evaluating economics across the community. Dollar cost still not asserted: the current Bedrock rate has not been checked. **#0023 confirmed the shape in the cloud** — a deployed discovery run is 6 Bedrock calls, ~19.1k input / ~473 output tokens, ~5 s of agent time inside ~12 s wall clock including cold start. The per-call breakdown is now visible in traces (2111→4131 input as context accumulates), so the growth is observable per turn rather than only in aggregate. |
| Q9 | Does the Stripe PaymentIntent manual-capture flow behave as documented? | The whole payment lifecycle rests on it, and it has never touched Stripe's servers. | **Open** — needs TEST keys. Re-read the current official docs first; the shapes were written from documentation, not from a response. |
| Q10 | Is the platform fee mode (10% of gross savings) defensible as a business model? | It is provisional business configuration, not domain truth. | **Open** — aligned by construction (no saving, no fee) and transparent, but untested against anyone's willingness to pay. |
| Q11 | Does the case-fitting solver stay fast with realistic community sizes? | It is a bounded DP; bounded is not the same as fast at scale. | **Open** — trivially fast at demo scale (tens of members). Needs a benchmark at a few hundred before a pilot. |
| Q12 | What actually happens to unclaimed paid-for goods? | The lifecycle deliberately stops at operator review. | **Open** — a policy question with legal edges. See `docs/PILOT_READINESS.md`. |
| Q13 | Should tool results be trimmed before they reach the model? | Measured 85:1 input-to-output tokens (#0019). `evaluate_pool_economics` alone returns ~2,250 tokens and is re-sent every turn, so the cost grows with community size. | **Resolved (#0020)** — yes, by projection, not by summarization. `pool/agent/projection.py` gives the model the decision-critical facts and keeps the complete deterministic result for the API, auditing, and tests. Re-measured on the same model, seed, scenario and bounds: **35.8k → 19.2k input tokens (−46%)**, identical tool sequence and outcome. The "fetch detail on demand" shape was rejected: a thirteenth tool costs schema bytes on every turn and buys an extra paid iteration. |
| Q14 | Does the agent handle the harder branches on a small model? | Only discovery has run on Bedrock. Recovery, final offer, and lock involve more state and more careful ordering. | **Resolved for recovery and lock (#0021)** — six real-model runs of the payment-failure recovery branch, shaped so lost demand (2 units) and merely-unanswered demand (4 units) are different numbers. Every run repaired exactly the hole, left the pending buyers alone, preserved the case boundary, and did not lock; three of six *attempted* the lock and were refused by the viability engine. Then locked correctly once the humans answered. `issue_final_offer` was never reached on a pool that already had one, so that ordering rule is still only proven offline. |
| Q15 | Are the tool schemas worth 6.8 KB of context on every turn? | After #0020 compacted the results, the twelve tool schemas are **62% of the model's remaining context** — 6,805 bytes re-sent per turn. | **Open** — measured, deliberately not acted on. The docstrings are what lets a small model pick the right tool, so trimming them trades selection quality for tokens. Answering it needs an A/B on the real model, not a byte count. #0021 is a point against trimming: tool selection was correct in 12 of 12 runs. |
| Q16 | Should consequential tool docstrings state that identifiers must come from a read tool? | #0021 observed the real model opening a turn with `recover_pool(pool_id="short_of_demand_pool")` — an invented identifier passed to a money-adjacent tool. Refused before touching state, and the model recovered, but it happened in 1 of 12 runs. | **Open, deliberately** — the safety property is proven and regression-tested (all seven consequential tools refuse an invented id before reading or writing anything). The candidate mitigation is one sentence per docstring; it is a *behavioural* change to tool selection, so adopting it means re-running the paid verification and it should be its own decision, not a drive-by edit during a verification. See Q15 — it also adds schema bytes to every turn. **#0022 made the refusal observable** without touching model behaviour: the hosted entrypoint now reports `ok` and `summary` per tool call, so a deployed run can prove an invented id was *rejected* rather than merely showing that `recover_pool` was called. That was a prerequisite for testing this on AgentCore at all — with `POOL_REPOSITORY=memory` the run record dies with the microVM, so the response and the logs are the only evidence. **#0023 looked for it in the cloud and did not find it.** Six deployed runs, 30 tool calls, `ok=true` on every one and `refused=0` in every log line. Two deliberate probes fed a real-but-stale pool id into a fresh session — the second instructing `recover_pool` as the first action — and both times the model ran normal discovery instead. So the reporting shape is proven and the refusal is not: `ok=false` has never been observed outside the local suite. Reproducing it needs a session carrying a pool already in a recoverable state, which takes multiple invocations in one session to build. Still deliberately unmitigated. |
| Q17 | Does the `instruction` payload field actually steer a run? | The AgentCore entrypoint documents it as "optional override of the run instruction", and `coordinator.run()` substitutes it for the entire prompt — but on Nova Lite it did not change behaviour. | **Open (#0023)** — two deployed runs passed an explicit instruction naming a tool and an id, including one saying "do not run discovery"; both ran discovery anyway, because `SYSTEM_PROMPT`'s lifecycle framing dominates on a small model. Safety-positive in this instance: an injected instruction did not steer the agent into a consequential tool. But it means any caller relying on `instruction` to select a branch silently gets discovery. Either the field should be documented as advisory, or branch selection should be deterministic (trigger → work queue) rather than prompt-borne. |
| Q18 | Should X-Ray Transaction Search stay enabled, and at what indexing percentage? | `agentcore deploy` turned it on account-wide without it appearing in any config or template, and `make destroy-agent` will not turn it off (#0023). | **Resolved for the hackathon (#0023, read-only verification 2026-08-16)** — **leave Transaction Search `ACTIVE` and indexing at 100 %.** Not because 100 % is inherently required, but because Pool's trace volume is tiny (**138.9 KiB of spans per run**, so 1,000 runs ≈ 0.13 GB), because **reducing the indexing percentage would not reduce span-ingestion cost** — ingestion is 100 % by construction whenever Transaction Search is enabled, and it is the dominant charge — and because at ~6 traces, 1 % indexing would index approximately none, leaving the X-Ray/ServiceLens views empty for a judge who opens them. **CloudTrail proof of what the CLI did:** `UpdateIndexingRule` and `UpdateTraceSegmentDestination`, both at **2026-08-16T19:50:23Z**, `userIdentity arn:aws:iam::860325090409:user/pool-admin`, `userAgent aws-sdk-js/3.1037.0 … nodejs` (the AgentCore CLI, not the AWS CLI), five seconds after stack `CREATE_COMPLETE`, with `requestParameters {"name":"Default","rule":{"probabilistic":{"desiredSamplingPercentage":100.0}}}` — so **AgentCore CLI 0.27.0 explicitly raised the account-level `Default` indexing rule from AWS's 1 % default to 100 %**, outside the synthesized Pool stack. `ActualSamplingPercentage` is a real field in `ProbabilisticRuleValue` but AWS **did not return it**; only `DesiredSamplingPercentage: 100.0` came back. **Post-hackathon:** reconsider or disable when the deployed runtime is no longer needed — `aws xray update-trace-segment-destination --destination XRay`, and note that the on/off switch, not the percentage, is the real cost lever. |

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

---

### #0003 — [2026-08-15] — Verified the toolchain instead of assuming it
`[ARTICLE-2]` `[AWS]` `[ARCHITECTURE]`

**Goal / user intent**
Establish the real API surfaces of Strands, boto3 Location, and AgentCore before writing
code against them, rather than writing from recall and debugging later.

**Starting state**
Two documentation files, a git repo, an MIT licence. No code, no dependencies, no AWS.

**Decision**
Install each SDK and introspect it. Take no API shape from memory.

**Why**
Assistant knowledge has a cutoff; these libraries move. A wrong parameter name discovered
at integration time costs far more than fifteen minutes of introspection, and this
repository has an explicit rule against inventing API details.

**Implementation**
Installed `strands-agents 1.52.0`, `boto3 1.43.72`, `bedrock-agentcore`. Introspected:
`Agent.__init__`, the `@tool` decorator, `BedrockModel(model_config=...)`, the hook event
classes and their fields, `Model.stream`, the streaming event TypedDicts, the `geo-routes`
and `location` service models, and `BedrockAgentCoreApp.entrypoint`. Status: **tested** —
every finding came from executing against the installed package.

**AWS / external services touched**
None. Service *models* were read from the local botocore data files; no API was called.

**Cost-relevant activity**
None. Package downloads only.

**Validation**
Direct introspection output, quoted into the design decisions it informed.

**Failures / dead ends**
`Session.get_service_model` does not exist on a boto3 `Session` — the loader is at
`Session()._loader.load_service_model(name, "service-2")`. Cost one wrong turn.

**What we learned**
Four findings that shaped the architecture:
1. Strands exposes a full hook system (`BeforeModelCallEvent`, `BeforeToolCallEvent`, …).
   That, not prompt instructions, is where loop bounds belong.
2. `BeforeToolCallEvent.cancel_tool` accepts a **string**, so a cancelled tool call can
   tell the model *why* — graceful termination instead of an opaque error.
3. Two AWS routing services exist. `geo-routes` requires **no provisioned route
   calculator**, unlike `location`. Chose it for operational reasons: one less billable
   resource to create and forget.
4. `geo-routes` takes `Position: [lon, lat]` and returns Distance in **metres**, Duration
   in **seconds**. Reversing the coordinate pair silently routes into the Indian Ocean, so
   there is now a test asserting the order.

**Article fodder**
Article 2 — "choosing an AWS API for operational rather than feature reasons" is a small
but real lesson, and the hook system is the technical centrepiece.

**Evidence worth preserving**
The `geo-routes` service-model output pinning `Position`/`Distance`/`Duration` semantics;
it is the justification for the routing test.

**Relevant commits / files**
`services/agent/pool/adapters/routing.py`, `pool/agent/bounds.py`, `agentcore_app.py`

---

### #0004 — [2026-08-15] — Deterministic domain: money, matching, allocation, policy
`[ARCHITECTURE]` `[ARTICLE-3]`

**Goal / user intent**
Build the layer that decides what is *true*, before any agent code exists.

**Decision**
A pure-Python domain package that cannot import a model client. Integer cents everywhere;
savings in basis points; largest-remainder cost allocation; an explicit legal-transition
table for the pool state machine; Smart Join as a pure function returning a full audit
trail.

**Why**
Pool handles other people's money. A model that can produce a price will eventually produce
a wrong one, and the error is invisible until someone is out of pocket. Making the boundary
*structural* — these modules have no path to an LLM — is stronger than making it a rule.

Basis points rather than float percentages so policy comparisons are exact integer
comparisons. Largest-remainder allocation so per-household shares always sum to exactly the
group total; two households comparing notes must never find a missing cent.

**Implementation**
`domain/{money,models,matching,allocation,policy,state}.py`. Status: **tested**.

**AWS / external services touched**
None.

**Cost-relevant activity**
None.

**Validation**
`pytest` — allocation sums asserted exact across many totals; every Smart Join rule has a
test proving it can block an auto-join; every illegal state transition raises.

**Failures / dead ends**
First pricing model shared cost across *purchased* units rather than *requested* units,
which quietly hid case surplus and overstated savings. Corrected: the group pays for whole
cases and the surplus cost is shared across what people asked for, which is what actually
happens when neighbours split a case. There is now a test asserting that a near-empty case
produces *negative* savings rather than a flattering number.

**What we learned**
Deciding that savings may go negative — rather than clamping at zero — turned out to matter
more than expected. It is what lets the agent correctly conclude "this deal is not worth
doing" instead of always finding something to sell.

**Article fodder**
Article 3 — Smart Join's six-rule audit trail, and the choice to evaluate all rules rather
than short-circuit so the UI can show every reason a household is being asked.

**Relevant commits / files**
`services/agent/pool/domain/*`, `tests/test_{money,matching,allocation,policy,state}.py`

---

### #0005 — [2026-08-15] — First working Strands loop, with bounds that actually fire
`[AGENT]` `[COST]` `[ARTICLE-2]` `[ARTICLE-3]`

**Goal / user intent**
A real bounded agent loop: the agent chooses tools adaptively, and cannot run away.

**Decision**
One `PoolCoordinator` agent, seven narrow typed tools, and a `BoundedRun` HookProvider that
raises on run-level bounds and cancels on tool-level bounds.

**Why**
One agent, not a swarm: pricing/matching/routing/policy need to be correct, not creative,
so they are tools. Splitting cancel-vs-raise matters — a cancelled tool lets the model wind
down gracefully and *see why*; a breached iteration cap means the run is no longer trusted
to stop itself.

**Implementation**
`agent/{bounds,tools,coordinator,offline_model}.py`. Status: **tested**.

**AWS / external services touched**
None — the offline planner and deterministic routing were used throughout.

**Cost-relevant activity**
Zero tokens. Every run in this entry cost nothing.

**Agent behavior**
Model provider `offline`; 6 tools available; typical scan calls `list_unmet_demand →
evaluate_opportunity → create_buying_pool` in 4 iterations; terminates `completed`.

**Validation**
`tests/test_agent_bounds.py` drives the *real* Strands event loop with two deliberately
broken models: one repeating an identical call (cancelled by duplicate detection), one
varying its arguments to evade that (stopped by the iteration cap). Asserted that the fault
is stored, that the model was not invoked again after the cap, and that no reasoning text
appears in the run record.

**Failures / dead ends**
1. **`except BoundExceeded` never fired.** Strands wraps a hook exception in
   `EventLoopException`, so a tripped safety bound was being recorded as a generic crash —
   the single worst place to lose fidelity. Fixed by walking the `__cause__`/`__context__`
   chain (bounded to 12 links so a cyclic chain cannot spin).
2. **Token usage was always zero.** `stop_response` has only `message` and `stop_reason`;
   usage rides in `stop_response.message["metadata"]["usage"]`. Found by probing a live
   run, not by reading types. Now read per model call rather than from `AgentResult`, so an
   *aborted* run still records what it spent.

**What we learned**
When your safety net raises, verify the catch actually catches it. A bound that fires but
is mislabelled as a crash is worse than no bound, because it destroys the signal you built
it to produce.

**Article fodder**
Article 2 — both integration findings, with the fix. Article 3 — cancel-vs-raise as an
autonomy design decision.

**Evidence worth preserving**
The probe output showing `stop_response` attributes (`message`, `stop_reason` only) — it is
the justification for a non-obvious line of code.

**Relevant commits / files**
`services/agent/pool/agent/*`, `tests/test_agent_bounds.py`

---

### #0006 — [2026-08-15] — An offline planner so tests and demos cost nothing
`[COST]` `[ARTICLE-2]` `[DEMO]`

**Goal / user intent**
Run the complete agent path — repeatedly, in CI, during UI work — without spending tokens.

**Decision**
Implement the Strands `Model` interface with `DeterministicPlannerModel`: a planner that
reads structured tool results and emits the next tool call as real Bedrock-shaped stream
events.

**Why**
Cheap tests are the tests that actually get run. Mocking the *agent* would prove nothing —
the loop is the part most likely to break. Substituting only the model keeps the real event
loop, the real tools, the real domain math, the real state machine, and the real approval
boundary in the exercise.

Alternative considered: record/replay of real Bedrock responses. Rejected — it needs
credentials to record, and it goes stale the moment a tool schema changes.

**Implementation**
`agent/offline_model.py`. Emits `messageStart` / `contentBlockStart(toolUse)` /
`contentBlockDelta` / `contentBlockStop` / `messageStop`, plus a metadata event with
explicitly zero usage. Runs are labelled `model_provider="offline"` in the run record and
the UI. Status: **tested**.

**Cost-relevant activity**
Zero, permanently, by construction.

**Failures / dead ends**
**The planner looped forever.** Once every product had been evaluated and none was viable,
it re-issued `record_no_action` indefinitely. The iteration cap caught it and recorded a
`loop_fault` — the safety net working exactly as designed. But a system that needs its net
every run is a bug, so `record_no_action` was made terminal and a regression test added
that runs repeated scans and asserts none faults.

**What we learned**
Two things worth writing down. First, the guard proved itself against real (our own) buggy
code rather than a contrived test. Second, "the safety net fired" is a signal to fix the
thing that tripped it, not evidence the system is fine.

**Article fodder**
Article 2 — this is the strongest transferable idea in the project: how to test an agent
without paying for it, without mocking away the part you need to test.

**Relevant commits / files**
`services/agent/pool/agent/offline_model.py`,
`tests/test_persistence_and_termination.py::TestTerminationRegression`

---

### #0007 — [2026-08-15] — Tuning the demo so the dropout genuinely breaks the pool
`[DEMO]` `[ARTICLE-1]` `[ARTICLE-3]`

**Goal / user intent**
Make the showcase honest: the withdrawal has to *actually* kill the deal, and the recovery
has to *actually* find someone new.

**Starting state**
Working end-to-end scan, but the first tuning produced a pool with so much surplus demand
that no single withdrawal mattered. The "recovery" would have been theatre.

**Decision**
Two changes. (a) The supplier minimum sits just under the inner ring's aggregate demand, so
the pool is genuinely marginal. (b) A deliberate radius asymmetry: **form tight (2 km),
repair wide (8 km)**.

**Why**
The asymmetry is not a demo trick — it is the right product behaviour. Keep the initial
travel burden low; widen the net only when repairing, and even then every candidate is
still bounded by their own travel policy. It also makes the replacement genuinely *new*
rather than someone who should have been included originally.

Also fixed pickup-site selection: choosing the site nearest the demand *centroid* drifted
toward outliers and picked a site convenient for nobody. Now it maximises how many
households fall inside the formation radius, breaking ties on total distance.

**Implementation**
`data/seed.py` (25 households, 29 needs, 8 products, 13 offers, 5 sites — all synthetic),
`services/coordination.py` radius constants, `agent/tools.py` site selection. Status:
**tested**.

**Validation**
`make demo` and `tests/test_demo_scenario.py`. Observed: pool forms at 133/150 committed
(two households need approval) → approvals → 155/150 → largest participant withdraws (−30)
→ 125/150, status `recovering` → recovery run adds one Smart Join-eligible household →
155/150 `threshold_met`. Group savings $99.00, 42.3%. Zero existing members re-contacted.

**Failures / dead ends**
Three failed tunings before this. First: threshold too low, dropout irrelevant. Second:
formation radius too wide, so the reserve households were already in the pool and recovery
had nobody to find. Third: 50 lb cases left 22% surplus, which was honest but made the
savings look weak.

**What we learned**
It is easy to build a demo where the dramatic moment cannot actually fail. Forcing the
scenario to be genuinely marginal made both the product and the tests better — the
recovery path now has to really work, and the tests assert the *shape* of the outcome
(threshold broken, replacement found, nobody else disturbed) rather than pinned numbers.

**Article fodder**
Article 1 — the economics that make the pool marginal are the economics that make the
product necessary. Article 3 — "form tight, repair wide" as an escalation-minimising rule.

**Evidence worth preserving**
The `make demo` transcript. It is reproducible any time and is the core of the demo video.

**Relevant commits / files**
`services/agent/pool/data/seed.py`, `pool/services/{coordination,demo}.py`,
`tests/test_demo_scenario.py`

---

### #0008 — [2026-08-15] — API, web app, and the privacy boundary
`[ARCHITECTURE]` `[DEMO]`

**Goal / user intent**
A consumer product a judge can use without an account, and a privacy boundary that is
enforced rather than promised.

**Decision**
FastAPI (uvicorn locally, Lambda via Mangum in cloud) plus a React/TypeScript SPA. Each
visitor gets an isolated workspace. Household coordinates are snapped to a ~110 m grid
**in the API layer**, before they leave the process.

**Why**
Enforcing privacy at the serialisation boundary means no future UI change can leak a
precise position — the data never reaches the client. A convention would eventually be
broken by a well-meaning feature.

Workspaces isolate judges from each other and carry a DynamoDB TTL, which is both a
privacy and a cost property.

**Implementation**
`pool/api/app.py`, `apps/web/*`. Design system deliberately avoids the purple-gradient AI
house style: paper-and-ink palette, one warm and one cool accent, serif display against a
sans UI face, tabular numerals. Dark mode, reduced-motion, skip link, ARIA progressbar.
Status: **tested** (API), **implemented + manually verified in a browser** (web).

**AWS / external services touched**
None — in-memory repository throughout.

**Validation**
`tests/test_api.py` including an explicit assertion that the map endpoint can never return
a precise household coordinate and never returns names on markers. Manually exercised in a
browser: landing → scan → pool formed (42.3%) → decision inbox populated → full guided
scenario returning all seven steps. `npm run build` clean; `tsc -b --noEmit` clean.

**What we learned**
Putting the privacy rule in the serialiser rather than the component made it testable in
one assertion. Privacy properties that can be unit tested are the ones that survive.

**Article fodder**
Article 1 — a neighbourhood product where location privacy is a design constraint rather
than a settings toggle.

**Evidence worth preserving**
Screenshots to capture for the article and video: decision inbox with the "why you're being
asked" line; activity feed showing automatic recovery; the approximate-position map.

**Relevant commits / files**
`services/agent/pool/api/app.py`, `apps/web/src/*`, `tests/test_api.py`

---

### #0009 — [2026-08-15] — Infrastructure, with cost claims turned into tests
`[AWS]` `[COST]` `[ARCHITECTURE]`

**Goal / user intent**
Reproducible, cheap, destroyable infrastructure — and a guarantee that the cost properties
stay true.

**Decision**
AWS CDK (Python): DynamoDB on-demand + TTL, Lambda + API Gateway HTTP API, EventBridge rule
**created disabled**, S3 + CloudFront. AgentCore Runtime deliberately excluded from the
stack — it is deployed with its own official tooling.

Then: assert every cost claim against the synthesized template in `infra/test_stack.py`.

**Why**
A cost rule in a document decays. A cost rule in a test fails the build. The tests assert
the schedule is DISABLED, DynamoDB is PAY_PER_REQUEST with a TTL, log retention is bounded,
no always-on resource type exists, nothing survives `cdk destroy`, no IAM policy grants
wildcard actions, and the web bucket blocks public access.

AgentCore is excluded from CDK because duplicating its container build and IAM would be
exactly the fragile custom path to avoid — but it is called out in `COST_NOTES.md` as the
resource most likely to be forgotten, precisely *because* `cdk destroy` will not remove it.

**Implementation**
`infra/app.py`, `infra/test_stack.py`, `scripts/*.sh`, `Makefile`. Status: **tested**
(synth + 21 assertions). **Not deployed.**

**AWS / external services touched**
None. `cdk synth` runs entirely offline.

**Cost-relevant activity**
None. No resource created.

**Validation**
Synthesized `PoolStack.template.json` and asserted against it: EventBridge `State:
DISABLED`, DynamoDB `PAY_PER_REQUEST` + TTL enabled, log retention 14 days, zero always-on
resource types.

**Failures / dead ends**
The tagging test failed, and it was a real defect rather than a bad test: tags were applied
at the *app* level (`cdk.Tags.of(stack)` after construction), so any other instantiation of
`PoolStack` would produce untagged resources — and untagged resources are the ones you
cannot find later when hunting for strays. Moved tagging inside the stack constructor.

Also hit two CDK deprecations (`point_in_time_recovery`, `log_retention`). Fixing the
second was worth more than it looked: an implicit Lambda log group **survives
`cdk destroy`** and retains logs indefinitely. Declaring it explicitly makes it destroyable.

**What we learned**
Writing tests against infrastructure found a real bug in ten minutes. The "assert your cost
claims" pattern is cheap and should be the default for any credit-constrained project.

**Article fodder**
Article 2 — turning cost policy into CI assertions; the implicit-log-group trap.

**Relevant commits / files**
`infra/app.py`, `infra/test_stack.py`, `Makefile`, `scripts/*.sh`

---

### #0010 — [2026-08-15] — Submission artifacts
`[DEMO]` `[ARTICLE-1]` `[ARTICLE-2]` `[ARTICLE-3]`

**Goal / user intent**
Make the work explicable to a judge who never runs it, and preserve article material while
it is still accurate.

**Implementation**
`README.md`, `docs/ARCHITECTURE.md`, `docs/architecture.{mmd,svg}`,
`docs/HACKATHON_SCORECARD.md`, `docs/DEMO_SCRIPT.md`, `docs/DEVPOST_DRAFT.md`,
`docs/ARTICLE_NOTES.md`, `docs/COST_NOTES.md`. Status: **implemented**.

**Validation**
Diagram rendered with `@mermaid-js/mermaid-cli` and visually checked. The README status
table and the scorecard both mark every cloud item as unverified, matching reality.

**What we learned**
Writing the scorecard exposed that the *only* materially incomplete category is "nothing
has run in the cloud". Everything else is done and tested. Knowing that precisely is more
useful than a long generic backlog.

**Article fodder**
All three. `ARTICLE_NOTES.md` now carries the failures and dead ends from entries #0003–
#0009 while they are still accurate, which was the entire point of starting the journal
before the build.

**Relevant commits / files**
`README.md`, `docs/*`

---

### #0011 — [2026-08-16] — Community as a first-class boundary, and the canonical lifecycle
`[ARCH]` `[PRODUCT]` `[ARTICLE-1]`

**Goal / user intent**
Take Pool from a polished neighbourhood prototype to the canonical product: a
collective-purchasing coordinator with Communities, a paid fulfilment side, real financial
commitment, purchase execution, and physical handoff.

**Starting state**
A working v1: `Household` / `NeedDeclaration` / `Offer` / `Pool` / `Membership`, a
`CANDIDATE → INVITING → THRESHOLD_MET → CONFIRMED` lifecycle, Smart Join, dropout recovery,
198 app tests + 21 infra tests passing, lint clean. Verified by running the baseline before
touching anything, rather than trusting the previous run's summary.

**Decision**
Extend rather than rebuild. Map the old concepts into the canonical model:

| Old | Canonical |
| --- | --- |
| `Household` | kept — it *is* the account unit; a Community membership is a separate entity |
| implicit "neighbourhood" | `Community` + `CommunityMembership` + verification providers |
| `PoolStatus` (8 states) | 13-state canonical lifecycle |
| `MembershipState` | `ParticipationState` — provisional vs funded is now explicit |
| `allocation.py` | `economics.py` — complete landed cost, not merchandise-only |

Deleted `domain/allocation.py` outright rather than keeping a second pricing path. Two
sources of truth about what something costs is the failure mode most worth avoiding here.

**Why**
The brief's non-negotiable is that Community, not campus, is the domain concept. Keeping
`Household` as the account entity avoided a rename that would have churned 198 tests for no
semantic gain — a dorm room is a household. `CommunityMembership` is keyed
`(community_id, household_id)` so one account belonging to several Communities is a schema
fact rather than a future migration.

**Implementation**
`domain/models.py` rewritten (~1,200 lines: 25 entities, 20 enums, 4 config dataclasses).
New: `economics.py`, `viability.py`, `hosting.py`, `timing.py`, `substitution.py`,
`pickup.py`. `state.py` rewritten around the canonical adjacency. Status: **tested**.

**AWS / external services touched**
None.

**Cost-relevant activity**
None. Everything ran offline.

**Validation**
443 application tests + 24 infrastructure tests passing, all offline. The state machine has
property tests rather than a restatement of the table: nothing reaches `LOCKED` except from
`FUNDING`/`RECOVERING`, and nothing rewinds out of a captured state.

**Failures / dead ends**
First attempt kept `allocation.py` alongside `economics.py` "for compatibility". Within an
hour there were two functions that could disagree about a price. Deleted it.

**What we learned**
The single most useful artifact was the two-column table of *what the model may decide* vs
*what deterministic code must determine*. It made the tool surface, the module boundaries,
and the test list all fall out. Writing it before the code would have saved a rewrite.

**Article fodder**
Article 1 — mapping an existing domain onto a larger canonical one without forking it.

**Relevant commits / files**
`services/agent/pool/domain/*`

---

### #0012 — [2026-08-16] — Complete landed economics, and two circular definitions
`[ECONOMICS]` `[ARTICLE-1]` `[ARTICLE-3]`

**Goal / user intent**
Make the buyer-facing price include every modelled cost — merchandise, host pay, card
processing, and Pool's own fee — so Smart Join is evaluated against net savings rather than
a headline number with the operating costs hidden.

**Decision**
Fix an explicit computation order, because two components are circular if computed naively:

1. merchandise and host compensation (independent of fees)
2. **platform fee = share of *gross* savings** — defined without referring to the total it
   belongs to
3. split across buyers by units, largest-remainder
4. **processing grossed up per buyer**: `charge = ceil((share + fixed) × 10000 / (10000 − bps))`
5. all-in = the sum; net savings = retail − all-in

**Why**
A percentage-of-savings fee aligns incentives (no saving, no fee) and reads honestly on an
offer. But savings depend on the total, which includes the fee — so the fee is drawn from
*gross* savings instead, which is well-defined and monotone.

Processing is the subtler one. The processor takes a cut of the amount you charge,
*including* the processing itself. Computing the fee on the pre-fee share under-recovers by
roughly 3% of the fee — a few cents per buyer. Nobody would notice, and it is a silent
platform subsidy, which the brief explicitly forbids.

**Implementation**
`domain/economics.py`. Every value is integer cents; floats never touch money.
Status: **tested**.

**Validation**
`test_economics.py` asserts buyer lines sum to exactly the all-in total, that each component
split sums to its own total, and that the gross-up never under-recovers. Demo output:
$756.00 merchandise + $44.68 host + $28.06 processing + $32.70 fee = $861.44 against
$1127.76 retail — 23.6% net.

**What we learned**
"Include all costs" sounds like an accounting requirement. It is actually two small algebra
problems, and getting either wrong produces a system whose real unit economics differ from
the ones it displays.

**Article fodder**
Article 1 (why transparency is a design constraint), Article 3 (the subsidy failure mode).

**Relevant commits / files**
`services/agent/pool/domain/economics.py`, `tests/test_economics.py`

---

### #0013 — [2026-08-16] — Zero speculative surplus became a solver, not a refusal
`[ECONOMICS]` `[PRODUCT]` `[ARTICLE-1]`

**Goal / user intent**
Honour the rule that Pool never quietly buys the leftovers of a part-filled case.

**Starting state**
The first implementation was a *check*: if case rounding left surplus, refuse to lock. Ran
the demo and the pool refused — 29 units against 12-unit cases leaves 7 unallocated. The
rule was working and the product was unusable.

**Decision**
Make it a solver. `fit_to_cases` chooses the buyer subset whose quantities sum to a multiple
of the case size and clear the minimum — a bounded exact search over reachable totals,
capped a few cases above the minimum, preferring members whose need is already due over
demand pulled forward from the future.

**Why**
"Do not buy speculative stock" is only half a rule. The other half is "so choose a buyer set
that doesn't require any". Rejecting is honest; solving is a product.

This also turned the flexible-future-demand mechanic from decoration into load-bearing
machinery. In the demo, current demand is 18 units against a 24-unit minimum and a 12-unit
case size — the *only* way to a viable pool is pulling forward exactly six units from
members who authorised an early purchase.

**Implementation**
`fit_to_cases` in `domain/economics.py`, wired into `evaluate_opportunity`.
Status: **tested**.

**Validation**
`test_economics.py` covers exact fill, priority preference, refusal when nothing lands on a
boundary, refusal below the minimum, and determinism across repeated runs. The end-to-end
scenario now produces exactly 2 cases, 24 units, 0 surplus.

**Failures / dead ends**
Considered "allow explicit extra-unit decisions" (ask a buyer to take a spare). Rejected for
v1: it is a real product option but it puts a question in front of a human to solve a
problem the system can solve itself, which is backwards.

**What we learned**
A constraint that only ever rejects is usually a constraint you have not finished
implementing.

**Relevant commits / files**
`services/agent/pool/domain/economics.py`

---

### #0014 — [2026-08-16] — The fulfilment side: candidates, ranking, and refusing politely
`[HOSTS]` `[PRODUCT]` `[ARTICLE-1]`

**Goal / user intent**
Model fulfilment as a real economic side: recruited, ranked, paid, and refusable.

**Decision**
- Candidates come from **two** sources: standing hosts, and pool members who click "offer to
  host" on this specific pool. A buyer needs no prior registration.
- Offering is **not** claiming. Several people may offer; a deterministic evaluator filters
  and ranks; the top eligible candidate receives an offer; decline or expiry moves to the
  next. No first-come-first-served path exists in the code.
- Eligibility is **factual and fails closed**: availability, vehicle, capacity, weight,
  supplier travel, pickup-site suitability, and their own minimum compensation. A candidate
  who breaks one is ineligible with a stated reason, not merely lower-ranked.
- Ranking optimises the **whole transaction** — buyer travel is weighted more heavily than
  host cost, because buyers outnumber the host.
- Compensation scales with work and splits into **earned** (the run) and **contingent** (the
  handoff), so a buyer no-show cannot erase pay for work already done.

**Why**
A host who is paid the same for 5 orders and 30 will stop showing up. And a system that
lets someone claim a job by clicking first optimises for reflexes rather than for the group.

**Implementation**
`domain/hosting.py` (evaluation, ranking), `services/hosting.py` (recruit, offer, accept,
decline, expire, assign). Status: **tested**.

**Validation**
`test_hosting.py` covers every refusal reason individually plus the "pricier but more
central host wins" case. In the demo, four candidates are evaluated: two eligible, one
refused for wanting more than the job pays, one refused for having no vehicle for a 55 kg
load.

**What we learned**
Exposing the score *components* rather than just the score turned an opaque decision into
something a judge can read off the screen — and made a ranking bug obvious during
development, because the component that was wrong was visible.

**Relevant commits / files**
`services/agent/pool/domain/hosting.py`, `services/agent/pool/services/hosting.py`

---

### #0015 — [2026-08-16] — Payments: authorise late, capture at lock, and refuse live keys
`[PAYMENTS]` `[SECURITY]` `[ARTICLE-3]`

**Goal / user intent**
Real financial commitment semantics without any possibility of real money moving.

**Decision**
- `PaymentProvider` abstraction with a deterministic in-process simulated provider and a
  Stripe **TEST-only** provider.
- `StripePaymentProvider` **refuses to construct** with anything that is not an `sk_test_`
  key. No flag, no environment override, no argument relaxes it.
- Saving a payment method is separate from authorising a pool charge. Nobody's card is
  touched when they add a recurring need.
- Authorise **after** the host is selected and the quote refreshed; capture **at lock**.
- Explicit internal payment states mapped to provider states. There is no `paid = true`
  anywhere in the system.
- Webhook signatures verified with Stripe's documented scheme using only `hmac`, with
  event-id deduplication and timestamp tolerance.

**Why**
The hackathon environment must not be able to silently fall back to live Stripe. Making that
a construction-time exception rather than a runtime check means a misconfigured environment
fails loudly before it can do anything.

Implementing signature verification ourselves rather than via the SDK keeps it testable
offline with no secret in the repository — and it is thirty lines.

**Implementation**
`adapters/payments.py`, `services/payments.py`. The simulated provider declines any method
reference containing a marker string, which is how the failure branch is triggered
deterministically rather than waited for. Status: **tested** (simulated),
**implemented-unverified** (Stripe — never contacted Stripe's servers).

**AWS / external services touched**
None. No Stripe API call has ever been made from this repository.

**Validation**
`test_payments.py` — 43 tests including live-key refusal, duplicate capture, capture
failure, replay rejection, stale-timestamp rejection, and a late authorisation event failing
to walk a capture backwards. An infra test asserts no Stripe marker appears in the
synthesized CloudFormation template.

**What we learned**
"Never use live keys" as a documented rule is worth much less than one unconditional
`raise` in a constructor. The rule cannot be forgotten, mis-configured, or overridden by a
future well-meaning change.

**Article fodder**
Article 3 — safety properties that are structural rather than procedural.

**Relevant commits / files**
`services/agent/pool/adapters/payments.py`, `services/agent/pool/services/payments.py`

---

### #0016 — [2026-08-16] — Recovery was over-recruiting, and reporting its own success wrong
`[BUG]` `[AGENT]` `[ARTICLE-3]`

**Goal / user intent**
Make payment-failure recovery real: when an authorisation fails, find compatible replacement
demand and restore the order.

**Starting state**
The first implementation computed the shortfall as `threshold − funded_units`. Ran the
scenario: recovery recruited three replacements for a two-unit gap, taking the pool from 24
units to 29 — against a 12-unit case size, which then correctly refused to lock on surplus.

**Decision**
Two fixes, both conceptual:

1. **Distinguish lost demand from pending demand.** A buyer who has not yet answered their
   final offer has not left. Only failed authorisations, withdrawals, and declines are a
   hole. `in_play_units` counts funded *plus* awaiting-decision; `lost_units` is the gap
   against that.
2. **Replacements must sum to *exactly* the gap.** "At least enough" reintroduces the
   speculative-surplus problem the case-fitting solver exists to prevent. Implemented as a
   small bounded exact-sum search; when nothing sums to the gap, recovery fails honestly.

Then a third, found by a test: recovery still reported `recovered=False` when the pool was
whole, because success was measured against *funded* units — which cannot be complete while
humans are still deciding. Recovery's job is to fill the hole, not to finish the pool.

**Why**
Over-recruiting trades a funding problem for an inventory problem. And an operation measured
against something it does not control will misreport its own outcome in a way that tests
happily pass.

**Implementation**
`services/coordination.py` — `in_play_units`, `lost_units`, `_select_replacements`, and the
`recovered` criterion. Also propagated into the agent's work-queue tool so the planner acts
on lost units rather than on a raw threshold gap. Status: **tested**.

**Validation**
`test_coordination.py::test_recovery_replaces_exactly_what_was_lost` and
`test_an_unanswered_buyer_is_not_treated_as_a_hole_to_fill`. The end-to-end scenario now
goes 24 → 22 (a card declines) → 24 (exact replacement), never above 24.

**Failures / dead ends**
The greedy "largest contributors first until covered" selection from the v1 dropout recovery
was carried over unchanged and was exactly wrong for a case-boundary world. It had been
correct when surplus cost was simply shared across buyers.

**What we learned**
The best bug in the project so far. Two systems that were individually right — recover the
shortfall, never buy surplus — combined into something wrong, and only an end-to-end run
surfaced it. Neither unit test suite could have.

**Article fodder**
Article 3, prominently. This is the concrete story for "the failure modes of an agent system
are mostly at the seams".

**Relevant commits / files**
`services/agent/pool/services/coordination.py`

---

### #0017 — [2026-08-16] — Pickup credentials, and a planner that watches what it did
`[FULFILLMENT]` `[SECURITY]` `[AGENT]`

**Goal / user intent**
Physical handoff that is proved rather than asserted, and an agent loop that can move a pool
through several steps in one run.

**Decision — credentials**
Each buyer allocation gets a one-time credential: a long token for the QR and a short
human-readable code for when scanning is awkward. **Only hashes are stored.** The plaintext
exists exactly once, in the response that issued it; re-issuing invalidates the previous
pair. Verification is constant-time. The short-code alphabet excludes I, L, O, U, 0 and 1 so
a code read aloud at a pickup table cannot be mistyped into someone else's allocation.

A host cannot mark an order collected without a credential. The only other route is an
operator override that requires a stated reason, preserves the previous state in the audit
record, and revokes any outstanding credential.

**Decision — planner**
The offline planner re-reads its work queue after acting, capped at twice per run.

**Why**
Storing plaintext credentials would mean a database dump is a free-goods coupon book.
Hashing costs nothing and makes re-issue meaningful.

On the planner: a loop that reads its queue once, acts, then decides from a stale view will
never notice that the pool it just repaired has become lockable. But unbounded re-reading is
polling with extra steps — hence the cap, which is also below the duplicate-call bound that
would have caught it anyway.

**Implementation**
`domain/pickup.py`, `services/fulfillment.py`, `agent/offline_model.py`.
Status: **tested**.

**Validation**
`test_fulfillment.py` covers single use, wrong-pool rejection with a distinct reason,
unknown-credential rejection, re-issue invalidation, and the absence of any host-facing
"mark all collected" path. The scenario re-scans one used credential on purpose and it is
rejected.

**Failures / dead ends**
First version of the scenario replayed *every* credential to prove the property. It worked,
and it buried the activity feed under ten rejection events. Now it proves it once; the
exhaustive coverage lives in the test suite. Demonstrating a property and testing it are
different jobs.

**What we learned**
"Observe after acting, at most twice" turned out to be the whole difference between a
planner that needs three separate invocations and one that can carry a pool from final offer
to lock in a single bounded run.

**Relevant commits / files**
`services/agent/pool/domain/pickup.py`, `services/agent/pool/services/fulfillment.py`,
`services/agent/pool/agent/offline_model.py`

---

### #0018 — [2026-08-16] — Four surfaces, and a transcript that told the truth in the wrong order
`[UX]` `[DEMO]`

**Goal / user intent**
Buyer, host, operator, and judge experiences on the canonical API, plus a demo transcript a
judge can follow without reading code.

**Implementation**
`apps/web/src/{api,views,App}.tsx` rebuilt on the new API. Six views: community dashboard
with Decision Inbox, pool detail with the cost breakdown and the eleven viability checks,
needs, host job with a working code scanner, operator console, agent trace, impact.
Status: **tested** (typecheck, build, and driven in a real browser).

**Validation**
Ran the full scenario from the UI in a browser: all six views render, no console errors, no
horizontal overflow at 375 px on any view, dark mode correct. Screenshots of the cost
breakdown and host ranking captured for the demo.

**Failures / dead ends**
Three real fixes came out of browser QA that no test would have caught:

1. The demo transcript reported `funded_units` *after* recovery had already run, so the
   payment-failure step showed a number that contradicted its own narrative. The steps were
   in the wrong order. Fixed by capturing the failure snapshot before the inbox step and by
   sourcing the recovery evidence from the activity log rather than assuming which run did
   it — the agent legitimately recovers in whichever run notices first.
2. A stale pool id in a client that had outlived a server restart produced an alarming error
   banner. A missing pool now just refreshes the list.
3. The needs table showed identical values in the "restock lead" and "will buy early"
   columns, because the seed set them equal — hiding the exact distinction the copy was
   explaining.

**What we learned**
The transcript bug is the interesting one. Every individual number was true; the *order*
made them read as a contradiction. A demo that reports live state at render time rather than
at the moment things happened will eventually tell a true story dishonestly.

**Relevant commits / files**
`apps/web/src/*`, `services/agent/pool/services/demo.py`, `services/agent/pool/data/seed.py`

---

### #0019 — [2026-08-16] — First real Bedrock inference, and the bug that only a live call could find
`[AWS]` `[AGENT]` `[COST]` `[ARTICLE-2]`

**Goal / user intent**
The smallest honest proof that the chain is real: Bedrock model → Strands agent → an
existing typed Pool tool → deterministic result → recorded outcome. No AgentCore, no
persistent resources, no scaffolding of a second agent.

**Starting state**
AWS authenticated for the first time: profile `pool-dev`, region `us-east-1`, non-root
IAM user `pool-admin` (account 860325090409). A direct Converse call to
`amazon.nova-lite-v1:0` had already succeeded (9 in / 6 out / 314 ms). Everything in this
repository had run offline until this point; `MODEL_PROVIDER=bedrock` had never executed.

**Decision**
Change only the model leg. Keep the production `PoolCoordinator`, the twelve existing
tools, every bound, and every other adapter (in-memory store, deterministic routing,
simulated payments) exactly as they were.

**Implementation**
Three changes, all in the model/provider path:

1. **`agent/coordinator.py` — fixed a real bug.** `BedrockModel` was being constructed as
   `BedrockModel(region_name=..., model_config={"model_id": ..., "max_tokens": ...})`.
   It takes its configuration as **keyword arguments**, not as a `model_config` dict. The
   dict was accepted into the config under a key nothing reads, `model_id` was never set,
   and Strands fell back to *its own* default (`global.anthropic.claude-sonnet-4-6`). So
   `BEDROCK_MODEL_ID` was silently ignored — a configured model that would never have been
   the model actually invoked.
2. **`agent/coordinator.py` — profile support.** Added `_boto_session()`: a named profile
   for local development, `None` for the default credential chain that Lambda and
   AgentCore use via execution roles. `BedrockModel` rejects `region_name` and
   `boto_session` together, so whichever applies is passed, never both.
3. **`config.py`** — added `aws_profile`, read from `AWS_PROFILE`, defaulting to empty.

**AWS / external services touched**
- `sts:GetCallerIdentity` — confirmed non-root before anything else.
- `bedrock:ListFoundationModels`, `bedrock:ListInferenceProfiles` — read-only.
- `bedrock-runtime:ConverseStream` — **18 real streaming calls across 3 verification runs**
  (6 per run). Model: `us.amazon.nova-lite-v1:0`.

**No resource was created.** No DynamoDB table, no Lambda, no AgentCore runtime, no
schedule. The AWS resource ledger stays empty. No Stripe call was made and payment
behaviour was untouched.

**Cost-relevant activity**
Per run, consistently across three runs:

| Metric | Run 1 | Run 2 | Run 3 |
| --- | --- | --- | --- |
| ConverseStream calls | 6 | 6 | 6 |
| Input tokens | 35,706 | ~35,700 | 35,836 |
| Output tokens | 418 | ~430 | 439 |
| Wall clock | 6.4 s | — | 5.6 s |
| Iterations (bound 8) | 6 | 6 | 6 |

Roughly **107k input / 1.3k output tokens total** on Nova Lite. Not priced here, because
the current rate has not been checked against the Bedrock price list and a guessed figure
is worse than none — but Nova Lite is the cheapest text model in the account and the
absolute spend is small.

**The number that matters is the ratio, not the total.** 35.7k input tokens for 418 output
tokens is 85:1. The cause is measured, not assumed: `evaluate_pool_economics` returns
**9,015 characters (~2,250 tokens)** of structured JSON, `list_latent_demand` returns
1,311, and Strands resends the whole conversation on every turn — so each large tool
result is re-billed on every subsequent call. This is precisely what `AGENTS.md` §3.3
warns about ("do not resend enormous histories when compact structured state will do"),
and it would have stayed invisible forever on the offline path, which charges nothing for
verbosity. On Nova Lite it is pocket change; on a frontier model the same run would cost
roughly fifty times more, and it grows with community size because the payload carries
every candidate.

Deliberately **not** fixed in this entry — trimming what the model sees is a behavioural
change to the agent and deserves its own decision, not a drive-by edit during a
verification. Logged as Q13.

**Agent behavior**
Model `us.amazon.nova-lite-v1:0` · 12 tools available · 5 called, in this order:

```
list_latent_demand → evaluate_pool_economics → create_candidate_pool
  → find_host_candidates → request_host_acceptance
```

That is the canonical workflow, chosen by the model. Nothing scripted it, and the
sequence was identical across all three runs. 6 iterations against a bound of 8; no bound
fired; terminated `completed` with outcome `pool_created`.

The deterministic half did its own job underneath: a real pool formed at
`host_recruiting` with 10 members against a 24-unit threshold, and four activity events
were written — including the host ranking that offered the job to `hh_marchetti`.

**Validation**
`pool/scripts/verify_bedrock.py`, run three times. It asserts twelve properties including
*real bedrock-runtime HTTPS calls observed in botocore's own endpoint log* — wire-level
evidence rather than our own logging claiming a call happened. All twelve passed each
time.

Then offline: **445 application tests + 24 infrastructure tests passing**, lint clean. The
offline path is unaffected.

Six new regression tests (`TestBedrockModelConstruction`) assert the configured model id
and token ceiling actually reach the model, that no unknown config key is silently
accepted, and that region and session are never passed together. They need **no
credentials** — verified by running them with `HOME` and every AWS variable stripped.

**Failures / dead ends**
1. **`boto3` could not resolve the profile at all**: `MissingDependencyException — using
   the login credential provider requires botocore[crt]`. The profile uses the newer
   `login_session` flow. Fixed by installing `botocore[crt]` into the local venv. It is a
   *local development* dependency only — Lambda and AgentCore authenticate with execution
   roles and never touch that provider — so it was deliberately not added to the runtime
   dependencies.
2. **`ValueError: Cannot specify both region_name and boto_session`** on the first
   corrected construction. The session already carries a region.

**What we learned**
The offline planner is excellent for testing everything *except the thing it replaces*.
A whole configuration path — construction, credentials, region, model id — had never
executed, and it was wrong in a way that no amount of offline testing could surface: the
system would have run happily against a model nobody chose. The lesson is not "test with
real calls"; it is that a substituted component leaves a *specific shaped hole*, and that
hole is exactly where the untested code lives. One real call cost pennies and found two
bugs and a dependency gap.

**Article fodder**
Article 2, and it is now unblocked for its first section. Three concrete findings: the
`model_config` kwargs bug, the `region_name`/`boto_session` exclusivity, and the
`botocore[crt]` requirement for the login credential provider. Plus the 85:1
input-to-output ratio, which is the most transferable cost lesson in the project so far.

**Evidence worth preserving**
`pool/scripts/verify_bedrock.py` output — it prints the botocore wire calls, the tool
sequence with argument digests, the resulting stored state, and the token counts, and it
is re-runnable for a screenshot.

**Relevant commits / files**
`services/agent/pool/agent/coordinator.py`, `services/agent/pool/config.py`,
`services/agent/pool/scripts/verify_bedrock.py`,
`services/agent/tests/test_agent_bounds.py`

### #0020 — [2026-08-16] — The model was paying to re-read what it already knew
`[AWS]` `[AGENT]` `[COST]` `[ARCHITECTURE]` `[ARTICLE-2]`

**Goal / user intent**
Close Q13. The first real Bedrock run spent 35.7k input tokens to produce 418 output
tokens, and the cause was a measured one: large tool results re-sent on every turn.
Reduce what the model *sees* without moving any fact out of deterministic code.

**Starting state**
The canonical local implementation, fully tested, with three consistent real Bedrock
discovery runs on `us.amazon.nova-lite-v1:0`. Tool results went to the model exactly as
the services computed them — `assessment.to_dict()` and friends, in full.

**Decision**
Add a **projection layer** between the deterministic result and the model:
`pool/agent/projection.py`. Tools call the same services, retain the complete
authoritative result on `ToolContext.full_results`, and return a compact view to the
model. Projections are pure selection and aggregation — they compute no money, no
quantity, no verdict.

**Why**
Three alternatives were considered and rejected:

1. **A "fetch the detail" tool** (the shape sketched when Q13 was opened). A thirteenth
   tool costs schema bytes on *every* turn, and any run that used it would spend an
   extra paid iteration to get back what it should have been handed the first time.
2. **Strands context management.** Evaluated against the installed version,
   `strands-agents 1.52.0`. The default `SlidingWindowConversationManager(window_size=40)`
   is already active and never engages: a discovery run produces ~13 messages. Its
   truncation is *reactive* — it fires on `ContextWindowOverflowException`, keeping the
   first and last 200 characters of a tool result, which cuts JSON mid-structure and
   could remove the blocking reason or viability verdict the model needs.
   `SummarizingConversationManager` and proactive compression generate the summary *with
   a model*: an extra paid call, and an LLM paraphrase of deterministic numbers becomes
   the model's version of the truth. That is the exact failure AGENTS.md §5 exists to
   prevent. Not adopted. It is the right tool for long open-ended conversations, and
   this is a bounded 6-turn workflow.
3. **Trimming the domain objects.** Rejected outright — the per-household lines and the
   host reward breakdown are what the operator UI and the audit trail are made of.

**Implementation** — implemented and tested.

Measured first, then cut. Instrumenting the `messages` list handed to `stream()` on
every turn gave the actual amplification, rather than an assumption about which payload
was worst:

| Tool result | Bytes | Re-sent | Amplified | Share |
| --- | --- | --- | --- | --- |
| `evaluate_pool_economics` | 9,015 | ×4 | 36,060 | 71% |
| `list_latent_demand` | 1,311 | ×5 | 6,555 | 13% |
| `find_host_candidates` | 2,241 | ×2 | 4,482 | 9% |
| `request_host_acceptance` | 2,283 | ×1 | 2,283 | 4% |
| `create_candidate_pool` | 446 | ×3 | 1,338 | 3% |

Inside the 9,015 bytes: `candidates` 4,596 (one record per household) and
`economics.lines` 3,673 (a second record per household). Both scale with community size;
neither is decision-critical. Across the rest of the lifecycle the same measurement found
`issue_final_offer` at 4,048 bytes, `inspect_pool` at 2,079, and `lock_pool` at 1,746 —
each dominated by per-household lists or the roster of viability checks that *passed*.

What each projection keeps is the shape of the decision it supports: the verdict, the
blocking reason, the identifiers the next tool call takes, the magnitudes that make an
opportunity worth pursuing, package/surplus status, and counts of the humans involved.

| Tool result | Before | After | Change |
| --- | --- | --- | --- |
| `evaluate_pool_economics` (viable) | 9,015 | 841 | −90.7% |
| `evaluate_pool_economics` (refusal) | 697 | 356 | −48.9% |
| `issue_final_offer` | 4,048 | 534 | −86.8% |
| `request_host_acceptance` | 2,283 | 736 | −67.8% |
| `find_host_candidates` | 2,241 | 694 | −69.0% |
| `inspect_pool` | 2,079 | 977 | −53.0% |
| `lock_pool` | 1,746 | 302 | −82.7% |
| `list_latent_demand` | 1,311 | 1,140 | −13.0% |
| `create_candidate_pool`, `recover_pool`, `execute_purchase`, `list_pools_needing_attention` | ≤ 468 | unchanged | measurement did not justify touching them |

A side effect worth naming: no tool takes a household id as an argument, so the ten
household identifiers per turn were never actionable. They are now counts. That is a
privacy improvement (§4) that happened to be free.

**AWS / external services touched**
`bedrock-runtime:ConverseStream` — **40 real streaming calls**: 14 baseline (2 runs on
the stashed pre-change code, so the comparison is same-session and same-environment), 20
after (5 runs), and 6 confirming the shipped code after two tool docstrings were corrected
to describe what the projections actually return. Model `us.amazon.nova-lite-v1:0`,
profile `pool-dev`, `us-east-1`, non-root IAM. **No resource was created**; the ledger
stays empty. AgentCore was not deployed. No Stripe call was made and payment behaviour was
untouched.

**Cost-relevant activity**

| Discovery run | Before | After | Change |
| --- | --- | --- | --- |
| Input tokens (6-iteration runs) | 35,929 · 35,706 · 35,836 | 19,179 · 19,327 · 19,062 · 19,314 · 19,434 | **−46.2%** |
| Input tokens (8-iteration runs) | 54,710 | 28,148 | **−48.5%** |
| Output tokens | ~430–505 | 444–589 | +14% |
| Input:output ratio | 85:1 | 39:1 | |
| Wall clock | 5.7–7.3 s | 5.1–6.9 s | −8% |
| ConverseStream calls | 1 per iteration | unchanged | |

Offline, where the whole context is measurable rather than inferred: amplified tool-result
bytes across a discovery run fell **35,464 → 8,711 (−75.4%)**, and total context sent
across all turns fell **84,417 → 55,025 bytes (−34.8%)**.

**Agent behavior**
Same model, same seed, same scenario, same bounds. Five of six runs produced the exact
canonical sequence in six iterations:

```
list_latent_demand → evaluate_pool_economics → create_candidate_pool
  → find_host_candidates → request_host_acceptance
```

The sixth went to eight iterations, adding `issue_final_offer` (which the tools correctly
refused — "no host has accepted this pool yet") and `list_pools_needing_attention`. **This
is pre-existing variance, not a regression**: one of the two baseline runs did exactly the
same thing, which is why the baseline was re-run rather than quoted from #0019. Every run
ended `completed` with outcome `pool_created`, a pool at `host_recruiting` with 10 members
against a 24-unit threshold, and four activity events. Final state identical before and
after.

**Validation**
`pool/scripts/verify_bedrock.py` — all twelve checks passed on all six post-change runs,
including wire-level evidence of real `bedrock-runtime` requests in botocore's endpoint
log.

Offline: **472 application tests + 24 infrastructure tests passing**, lint clean, secret
scan clean. 21 of those tests are new (`tests/test_agent_projection.py`) and need no
credentials: they assert that each projection keeps the identifiers the next tool call
takes, that every surviving figure equals the service's own value rather than a re-derived
one, that refusals keep their reasons, that the authoritative result — per-household
lines, reward breakdowns, full check rosters — is still reachable behind the projection,
and that no tool result in the full lifecycle exceeds a 1,500-byte budget. That last one
is the regression guard: it fails the moment someone reintroduces a 9 KB payload.

**Failures / dead ends**
The first draft of the opportunity projection renamed the refusal field to
`blocking_reason`. The offline planner reads `reason` when composing its no-action
message, so the run would have recorded an empty explanation — silently, because nothing
asserts the *content* of that string. Keeping the authoritative field name fixed it. The
lesson generalises: a projection that renames is a projection that breaks a consumer you
forgot about.

**What we learned**
The expensive thing was not the payload — it was the payload times the number of turns
that followed it. Re-reading is where an agent's money goes, and it is invisible until
something bills you per token. Measuring the amplification rather than the size changed
what got cut: `list_latent_demand` is a seventh the size of `evaluate_pool_economics` but
is re-sent more often, and the two rank far closer than their byte counts suggest.

The second lesson is where the fix belongs. Context management, truncation, and
summarization all operate *after* the waste exists. Not generating it is cheaper, exact,
and cannot delete the one field the model needed. The framework's tools were built for
long open-ended conversations; a bounded workflow with typed tools should fix this at the
source.

**Architectural finding**
With the results compact, the largest single term in the model's context is now the **tool
schemas: 6,805 bytes re-sent every turn, 62% of what remains**. Twelve tools with careful
docstrings — the same docstrings that make a small model pick the right tool. Trimming
them trades tool-selection quality for tokens, which is a very different bet from dropping
an audit detail, so it was measured and left alone. Logged as Q15.

**Article fodder**
Article 2, and it is the best cost story in the project: a measured 85:1 ratio, a
measurement that contradicted the obvious culprit ranking, a fix at the source rather than
in the framework, and a 46% reduction verified on the real model with the behaviour
unchanged. Also Article 3, for the boundary it defends: the model is given less, not
trusted with more.

**Evidence worth preserving**
Five post-change and two baseline `verify_bedrock.py` outputs, same session and same
environment, showing tool sequence, token counts, and final state. The per-turn context
measurement table above.

**Relevant commits / files**
`services/agent/pool/agent/projection.py` (new),
`services/agent/pool/agent/tools.py`, `services/agent/pool/agent/coordinator.py`,
`services/agent/tests/test_agent_projection.py` (new), `docs/COST_NOTES.md`

### #0021 — [2026-08-16] — The recovery branch, on a real model, with a lock it was not allowed to take
`[AWS]` `[AGENT]` `[HITL]` `[COST]` `[ARTICLE-2]` `[ARTICLE-3]`

**Goal / user intent**
Q14: only the *discovery* path had ever run on Bedrock. Discovery is the forgiving
branch — nothing is committed, nothing can be over-bought, and a wrong tool choice
costs a wasted iteration. Verify one **consequential** branch before considering
AgentCore: a funded pool loses committed demand and the coordinator has to repair it,
then know whether the repaired pool may lock.

**Starting state**
Canonical local implementation complete. Real Bedrock inference verified for discovery
(#0019) and made 46% cheaper by projections (#0020). AgentCore not deployed, no
persistent AWS resource, no Stripe contact.

**Decision**
Verify the **payment-failure recovery branch** — the smallest existing scenario that is
genuinely consequential — and shape it so the two failure modes we care about are
*distinguishable from each other*, which the showcase scenario does not do.

In `services/demo.py` every human answers their Decision Inbox *before* the recovery run,
so at the moment recovery happens there is nothing pending. Lost demand and unanswered
demand are the same number: zero and the shortfall. A coordinator that confused them
would pass. So the verification runs recovery at the more realistic moment — immediately
after the final offer, while two buyers are still deciding:

| | units |
| --- | --- |
| Order priced against whole 12-unit cases | 24 |
| Funded | 18 |
| **Genuinely lost** (one seeded card declined) | **2** |
| **Merely unanswered** (two buyers still deciding) | **4** |

Recruiting 6 instead of 2 overshoots a 24-unit order that fills exactly two cases, which
is the speculative surplus §48 exists to prevent. Locking at all captures money from a
pool two buyers never approved. Both mistakes are *allowed* by the tool surface and
refused only by deterministic code — which is precisely why a real model had to try.

**Implementation** — implemented and tested.

- `pool/scripts/recovery_scenario.py` (new). The scenario builder, an authoritative state
  snapshot, and the lifecycle invariants as pure functions. No environment setup, no model,
  no I/O beyond the injected repository.
- `pool/scripts/verify_recovery_bedrock.py` (new). **(COSTS MONEY.)** Two bounded real-model
  runs. Adds exactly one thing over the shared module: evidence that Bedrock made the
  decisions.
- `tests/test_recovery_lifecycle.py` (new, 18 tests, credential-free). Runs the *same*
  invariant functions against the offline planner.

The split is the point: the semantics are asserted for free on every `make test`, and the
paid script proves a real model reaches the same place. When they disagree, the difference
is the model's judgement — which is the only thing worth paying to observe.

The situation is scripted; the decision is not. Setup is deterministic service calls with
no model involved, and the instruction is **verbatim from the showcase scenario** — it
names no pool, no tool, and no unit count, and it deliberately invites a lock ("then lock
anything that has become viable") so the deterministic rules have to be the thing that
refuses one.

**AWS / external services touched**
`bedrock-runtime:ConverseStream` — **53 real streaming calls across 6 harness runs**
(12 coordinator runs). Model `us.amazon.nova-lite-v1:0`, profile `pool-dev`, `us-east-1`,
non-root IAM user `pool-admin`. **No resource was created**; the ledger stays empty.
AgentCore was not deployed. No Stripe call was made; payments and purchase were the
simulated providers throughout, and no money moved.

**Cost-relevant activity**

| | recovery run | lock run |
| --- | --- | --- |
| Iterations (bound 8) | 4–5 | 3–6 |
| Tool calls (bound 25) | 4–5 | 2–5 |
| Input tokens | 11.3k–14.5k | 7.1k–17.0k |
| Output tokens | 353–713 | 256–568 |
| Wall clock | 3.9–9.2 s | 2.8–5.8 s |

A full harness run is 7–11 ConverseStream calls and ~19k–32k input tokens. Both branches
sit **well inside** the bounds; nothing came close to firing one. Notably the recovery run
is *cheaper* than a discovery run (~19k) despite being the harder decision — it reads a
468-byte work queue instead of evaluating economics across the whole community.

**Agent behavior**
Six harness runs. The recovery phase produced the same opening every time:

```
list_pools_needing_attention → recover_pool → [inspect_pool | lock_pool] → record_no_action
```

Never `recover_pool` first — the instruction names no pool, so the identifier could only
come from the work queue, and it always did.

**Three of six runs attempted the lock and all three were refused**, with the deterministic
reason, having captured nothing:

```json
{"locked": false, "reason": "20/24 units (funded) against the supplier minimum",
 "viability": {"failed": ["supplier_moq", "buyer_decisions_settled", "funding"]}}
```

That is the single most valuable observation here. The model was explicitly invited to lock,
it tried, and the viability engine — not a prompt, not a guardrail sentence — stopped it.
The model then recorded no further action, and the outcome stayed `pool_recovered`: #0016's
fix (`record_no_action` never overwrites work already done) firing under a real model,
in five of six runs where the model called it last.

Recovery itself was identical in all six: shortfall **2**, one replacement (`hh_petrov`,
2 units) auto-authorised by their own Smart Join policy, in-play back to exactly 24, the
two pending decisions untouched, surplus 0. Phase 2, after the two humans answered:
`list_pools_needing_attention → lock_pool` (locked) and, in four runs, `execute_purchase`.
Final state identical every time — 10 captured payments totalling **$861.44**, exactly
`final_economics.all_in_cents`.

**Validation**
Six runs of `verify_recovery_bedrock.py`; **31 assertions per run** covering the chain
(real `BedrockModel`, configured model id, wire-level botocore evidence, bedrock provider
recorded, tokens consumed), the semantics (replaced exactly what was lost, did not
over-recruit, pending decisions not treated as lost, case boundary preserved, economics
unchanged, outcome not overwritten, did not lock, captured nothing, projections faithful),
and the bounds. **Five of six runs passed every assertion.** The sixth is below.

Offline: **490 application tests + 24 infrastructure tests passing**, lint clean, secret
scan clean. 18 of those are new. They were *run* with `HOME` and every AWS variable
stripped **and** `MODEL_PROVIDER=bedrock` deliberately set, and still passed in 0.27 s:
the tests pin `Settings(model_provider="offline", …)` explicitly rather than reading the
environment, so a stray variable cannot steer the suite at a paid model.

A projection check worth naming: `BoundedRun` records the first 180 characters of the exact
string Strands handed the model, so re-projecting the retained authoritative result and
comparing proves the model saw *that result's projection* — not a paraphrase, and not a
number anyone re-derived. It passed on every tool call in every run.

**Failures / dead ends**

1. **The real model invented a pool identifier.** Run 3, phase 2, first turn — with no tool
   result yet in that run — the model opened with
   `recover_pool(pool_id="short_of_demand_pool")`. A *consequential* tool, called with a
   plausible-looking string it made up.

   What happened: `_require_pool` raised `CoordinationError: unknown pool` before anything
   was read or written, Strands returned the error, and the model corrected itself —
   `list_pools_needing_attention → inspect_pool → lock_pool → execute_purchase` — and the
   run finished correctly with the right pool locked and $861.44 captured. Blast radius:
   zero.

   Diagnosed rather than scripted around. Every consequential tool was then checked against
   an invented identifier: all seven refuse before touching anything, and the run's own
   bookkeeping (outcome, created/advanced/recovered ids, decisions created) stays clean, so
   a refused call cannot make a run report work it did not do. `inspect_pool` is the
   deliberate exception — a *read* answers `{"error": "unknown pool"}` instead of raising,
   which is exactly how the model recovers course without burning the run. Nothing asserted
   any of this before; now `test_recovery_lifecycle.py` does, including an end-to-end
   reproduction with a planner that opens with the same invented call.

   The verification still **fails** that run, on `every tool call the model made was
   accepted`. That check was renamed from "every tool call succeeded" because the original
   name credited the wrong party: the refusal is the system working, and the signal is
   about the model's arguments. It was deliberately **not** relaxed. A hallucinated argument
   to a money-adjacent tool is exactly what a verification run should refuse to wave through,
   even when the outcome was fine.

2. **The first version of the grounding check blamed the wrong call.** It looked at the
   first `recover_pool` in the run, which in the reproduction is the rejected one — so a run
   that recovered correctly from an invented id scored as "not grounded". Fixed to use the
   first *accepted* call: a rejected call neither repairs nor grounds anything. Found by the
   new offline test, not by a paid run, which is the arrangement working as intended.

**What we learned**
A scenario that cannot distinguish two failure modes cannot verify that they are
distinguished. The showcase settles every human decision before recovery runs, so "gone"
and "hasn't replied yet" are never both non-zero at the same instant — and the invariant
that took two attempts to get right in #0016 would have passed a real-model check that
never actually tested it. Moving the run three steps earlier in the lifecycle cost nothing
and made the test real.

The second lesson is about where safety lives. The model was told to lock, tried to lock,
and could not — and separately reached for an identifier that did not exist. Neither is a
prompting failure to be fixed with a better sentence. Both were caught by deterministic
code that checks stored facts before acting, which is the AGENTS.md §5 boundary paying for
itself on the branch where money is involved.

**Article fodder**
Article 3 primarily, and it now has its best concrete scene: an autonomous agent
*attempting* a consequential action and being refused by deterministic rules, with the
refusal reason quotable verbatim. Also Article 2, for the shared-invariant arrangement
(one set of assertions, run free offline and paid on the real model) and for the invented
identifier, which is the most transferable agent-safety finding in the project: give a
consequential tool a name-shaped argument and a small model will eventually guess one.

**Evidence worth preserving**
Six `verify_recovery_bedrock.py` outputs, including run 3 with its rejected call and its
single FAIL. The lock refusal JSON above. The before/after state blocks, which read as a
clean narrative for the demo: 18 funded / 2 lost / 4 undecided → repaired to 24 in play →
refused the lock → humans answer → locked and captured $861.44.

**Relevant commits / files**
`services/agent/pool/scripts/recovery_scenario.py` (new),
`services/agent/pool/scripts/verify_recovery_bedrock.py` (new),
`services/agent/tests/test_recovery_lifecycle.py` (new), `Makefile`

### #0022 — [2026-08-16] — The deployment CLI had been replaced, and a refusal you could not see
`[AWS]` `[ARCHITECTURE]` `[COST]` `[AGENT]` `[ARTICLE-2]`

**Goal / user intent**
Prepare an Amazon Bedrock AgentCore deployment and take it as far as a dry run, without
provisioning anything. Then harden three things the dry run exposed before asking for
approval to bootstrap CDK and deploy for real.

**Starting state**
The local implementation was complete and Bedrock-verified (#0019–#0021). AgentCore had
never been deployed and no AWS resource had ever been created. `Makefile`,
`docs/PILOT_READINESS.md` and the entrypoint docstring all documented the deployment as
`agentcore configure --entrypoint agentcore_app.py && agentcore launch`.

**Decision**
Adapt to the current CLI rather than preserve the repository's assumption, and keep the
existing coordinator and entrypoint exactly as they are.

**Why**
`bedrock-agentcore-starter-toolkit` — the CLI every one of those commands belongs to — is
now marked **legacy**. AWS ships `@aws/agentcore` (npm) instead, which binds the same
`agentcore` command name, so having both installed is itself a documented hazard. The
commands in this repository would not have failed with "deprecated"; they would have run
whichever CLI happened to be on `PATH`.

The new CLI is CDK-based and wants a project directory. `agentcore create` is the only
official way to make one, and it scaffolds a *replacement* — its own `agentcore.json`,
its own `aws-targets.json`, and an `app/<AgentName>/main.py` agent next to the real
coordinator. So the project config was hand-written against the published schema instead,
pointing `codeLocation` at `services/agent/` so the entrypoint deploys where it already
lives. `CodeZip` over `Container`: no Dockerfile, no ECR repository, no CodeBuild project,
and no local container runtime — the smaller and cheaper of the two (§3.5, §3.7).

**Implementation**
Implemented and tested; **not deployed**.

1. **`agentcore/agentcore.json`, `agentcore/aws-targets.json`** (new, committed) — one
   runtime, `PYTHON_3_13`, `PUBLIC`, `HTTP`, `AWS_IAM` inbound auth, fifteen environment
   variables carrying the model id and every bound.
2. **`agentcore_app.py` — unchanged in substance.** The runtime HTTP contract did not
   move: `BedrockAgentCoreApp`, `@app.entrypoint`, `POST /invocations`, `GET /ping`. The
   only edits are the docstring and the tool-call reporting below.
3. **`services/agent/pyproject.toml`** — `bedrock-agentcore` and
   `aws-opentelemetry-distro` moved into runtime dependencies. CodeZip installs the image
   straight from this file, and the synthesized start command is
   `["opentelemetry-instrument", "agentcore_app.py"]` — so a missing OTel distro fails the
   container at start, not merely its tracing.
4. **`scripts/agentcore_cdk_init.sh`** (new) + `make agentcore-cdk` — rebuilds the
   generated `agentcore/cdk/` from the installed CLI's own bundled assets. Refuses to
   overwrite without `--force`, warns when the installed CLI is not the verified version.
5. **Tool-call reporting** — the entrypoint returned `[t.name for t in run.tool_calls]`.
   It now returns `{"name", "ok", "summary"}` per call, the same shape the API already
   used for run detail. Output only: no tool description, schema, prompt, or domain
   semantics changed.
6. **`scripts/secret_scan.sh`** — the AgentCore staging cache is pruned by exact rooted
   path, plus `scripts/secret_scan_selftest.sh` (new) to prove the prune is that narrow.

**AWS / external services touched**
`sts:GetCallerIdentity`, `cloudformation:DescribeStacks`/`ListStacks`,
`bedrock-agentcore-control:ListAgentRuntimes`, `s3:ListBuckets`,
`ecr:DescribeRepositories`, `iam:ListRoles`, `codebuild:ListProjects` — all read-only,
all used to confirm the account was and stayed empty.

**No resource was created.** No CDK bootstrap, no runtime, no bucket, no role. The ledger
stays empty and the account still holds nothing but three AWS service-linked roles. No
Stripe call was made; no Stripe-related resource appears anywhere in the synthesized
template.

**Cost-relevant activity**
No model tokens were spent. Every local verification ran on the offline planner, because
the Bedrock leg was already verified in #0019–#0021 and re-running it would have proved
nothing new.

Two cost decisions are baked into the config. `lifecycleConfiguration` sets
`idleRuntimeSessionTimeout: 60` and `maxLifetime: 300` against API defaults of **900 s and
8 h**. AgentCore Runtime bills memory per second across a session's life and CPU only
while processing, so the default would have billed a fifteen-minute idle memory tail after
every invocation of a workflow already bounded at 120 s — exactly the "long-running
AgentCore sessions" risk in §3.4.

Two costs the first real deployment will introduce, both recorded now so they are not
discovered later: the CDK bootstrap creates a persistent S3 staging bucket that
accumulates ~44 MB per deployed artifact version, and the runtime's CloudWatch log group
is created by the service outside the stack with **no retention policy** — unlike
`PoolStack`, which caps everything at 14 days.

**Agent behavior**
Unchanged by design, and that is the point of item 5. A run still selects tools, still
terminates on a deterministic condition, still refuses invented identifiers. What changed
is that the refusal is now visible from outside the runtime.

**Validation**
- `agentcore validate` → `Valid`. `agentcore deploy --dry-run` reaches
  `Synthesize CloudFormation` and stops at `Check bootstrap status`, which is a hard gate
  before the plan summary — clearing it needs `--yes`, which auto-bootstraps, so the
  dry run cannot print its own plan on an unbootstrapped account. The synthesized template
  is the authoritative answer instead: **4 resources** — one
  `AWS::BedrockAgentCore::Runtime`, one execution role, one inline policy, CDK metadata.
- The execution role's inline policy is Bedrock invoke on inference profiles and
  foundation models, CloudWatch Logs scoped to `/aws/bedrock-agentcore/runtimes/*`, and
  X-Ray. No DynamoDB, S3, or Location access — correct for this configuration.
- **The built artifact was inspected, not assumed**: 43.7 MB zipped / 107.5 MB unpacked
  against a 250 MB limit, containing `pool/`, the entrypoint, Strands, and OTel — and no
  `.env`, `.venv`, `.git`, or AWS config.
- **`agentcore/cdk/` was deleted and rebuilt from scratch** to prove a fresh clone works:
  the dry run failed exactly as documented, `make agentcore-cdk` reconstructed it, and
  validation and synthesis both succeeded again. The resource set was byte-identical apart
  from the code asset hash, which moved because the entrypoint changed.
- **499 application tests + 24 infrastructure tests**, lint clean, typecheck and web build
  clean. Nine of those tests are new and credential-free.
- **The deployed start command was run locally** — `opentelemetry-instrument` wrapping the
  entrypoint — serving `/ping` and `/invocations`, with the AgentCore session id threaded
  through to the SDK's own logs.
- `make secret-scan-selftest` plants fake AWS and Stripe credentials in seven locations
  and asserts each is caught, including one inside a `.cache` directory elsewhere in the
  repository, then asserts only `agentcore/.cache/` is exempt.

**Failures / dead ends**
1. **The first dry run failed on a missing `agentcore/cdk/`**, and the CLI's advice —
   "Run 'agentcore create' first" — is the one command that would have overwritten Pool.
   Resolved by taking the CLI's own assets, which turned out to contain no template
   placeholders at all, so copying them is deterministic rather than an approximation.
2. **The second failed on `sh: tsc: command not found`.** The CLI's "Sync CDK
   dependencies" step completed in 2 ms without installing anything: it expects
   `node_modules` to already exist, because `create` normally runs `npm install`.
3. **The 120 MB staging cache broke `make secret-scan`** — on botocore's own
   `AKIA…EXAMPLE` documentation and the PEM header constant inside `cryptography`. The
   first fix, `--exclude-dir=.cache`, was too broad: `--exclude-dir` matches a basename, so
   it would have blinded the scanner to every `.cache` directory in the repository. Now
   pruned by exact rooted path, at a cost of about half a second.

**What we learned**
Two things, and the second is the more useful.

A deployment path that has never been executed can rot without anyone touching it. The
commands in this repository were correct when written and had since been replaced by a
different tool with the same name. Nothing failed, because nothing had ever run.

And **a safety property that cannot be observed from outside the system is not yet a
safety property you can demonstrate.** #0021 proved that an invented pool identifier is
refused before any state moves, and regression tests pin it. But the hosted entrypoint
reported only tool *names* — so a `recover_pool` rejected for an invented id and a
`recover_pool` that repaired a pool produced identical output. With `POOL_REPOSITORY=memory`
the run record dies with the microVM, so there would have been nothing to query afterwards
either. The guard was real; the evidence was not reaching anyone.

**Article fodder**
Article 2, strongly. Three findings that transfer: a legacy CLI that shares its successor's
command name; a dry run that cannot complete without a provisioning step, which is worth
naming honestly rather than papering over; and the observability lesson above, which is
really an argument about what "verified" means once code is somewhere you cannot reach.

**Evidence worth preserving**
The synthesized `AgentCore-Pool-default.template.json` (four resources, and the execution
role's policy). The `make agentcore-cdk` reconstruction transcript. The
`make secret-scan-selftest` output — it reads as a table of what the scanner does and does
not look at. And a `/invocations` response showing `ok` and `summary` per tool call.

**Relevant commits / files**
`agentcore/agentcore.json` (new), `agentcore/aws-targets.json` (new),
`scripts/agentcore_cdk_init.sh` (new), `scripts/secret_scan_selftest.sh` (new),
`services/agent/tests/test_agentcore_entrypoint.py` (new),
`services/agent/agentcore_app.py`, `services/agent/pyproject.toml`,
`scripts/secret_scan.sh`, `Makefile`, `.gitignore`, `README.md`,
`docs/PILOT_READINESS.md`, `docs/ARTICLE_NOTES.md`

---

### #0023 — [2026-08-16] — Deployed for real, and the observability it switched on without asking
`[AWS]` `[ARCHITECTURE]` `[COST]` `[AGENT]` `[ARTICLE-2]`

**Goal / user intent**
With explicit approval, perform the two operations #0022 stopped short of: the standard CDK
bootstrap for 860325090409/us-east-1, and the first real deployment of the already-reviewed
AgentCore stack. Then prove the deployed path end to end with the smallest live test that
could prove it, and leave the runtime standing for review.

**Starting state**
Account empty apart from three AWS service-linked roles. AgentCore CLI 0.27.0, config
`Valid`, synthesized stack reviewed at four resources, never deployed, never bootstrapped.

**Decision**
Bootstrap with the default `hnb659fds` qualifier and the default `AdministratorAccess`
execution policy, then deploy the existing stack unchanged. No custom execution policy —
the approval said standard unless standard failed, and it did not fail.

**Why**
The synthesized stack requires bootstrap version 6; the standard bootstrap writes 32. A
hand-scoped CFN execution policy is real work to get right and would have had to be
re-derived on every future resource change, for a hackathon account that holds nothing
else. The cheap correct thing was the documented one.

**Implementation**
Pre-flight first, because the approval was conditional on it: `sts:GetCallerIdentity`
returned `arn:aws:iam::860325090409:user/pool-admin` — a non-root IAM user — in
`us-east-1`. `agentcore/cdk/` already existed and the CLI was the verified 0.27.0, so it
was not rebuilt; `cdk.out` *was* deleted and re-synthesized from scratch. The regenerated
template was the same four resources, and the code asset hash came back byte-identical
(`ab8ae6b7…c8147`), which is the reproducibility claim in #0022 holding up.

1. **`cdk bootstrap`** → `CDKToolkit`, `CREATE_COMPLETE`, **11 resources**, ~48 s.
2. **`agentcore deploy --yes`** → `AgentCore-Pool-default`, `CREATE_COMPLETE`, **4
   resources**, **84 s** wall clock. Runtime `Pool_PoolCoordinator-TmVqSN9H56`, `READY`.
3. **Retention set immediately**, per the approval and `docs/COST_NOTES.md`'s "14 days
   everywhere": the runtime log group had none, and so did a second log group the deploy
   created without mentioning it.

**AWS / external services touched**
CloudFormation, S3, ECR, SSM, IAM, Bedrock AgentCore (control + data plane), Bedrock
(`us.amazon.nova-lite-v1:0`), CloudWatch Logs, X-Ray. **No Stripe call. No DynamoDB, no
EventBridge, no Amazon Location, no AgentCore Memory/Gateway/Browser/Code-Interpreter** —
confirmed empty by API, not by assumption: `list-gateways`, `list-memories`,
`list-browsers`, `list-code-interpreters` all returned zero. `PoolStack` was not deployed.

Every created resource is in the ledger at the top of this file.

**Cost-relevant activity**
Six live invocations, ~114k input / ~2.9k output tokens on Nova Lite, ~30 s total runtime
processing. No always-on compute: the runtime bills per invocation, and idle sessions are
capped at 60 s by the `lifecycleConfiguration` chosen in #0022.

**The one thing that was not in the plan.** `agentcore deploy` made **two** account-level
X-Ray changes and mentioned them in a single trailing note: it enabled **Transaction
Search** (`UpdateTraceSegmentDestination` → `CloudWatchLogs`), and it **raised the
account-level `Default` X-Ray indexing rule to `DesiredSamplingPercentage: 100.0`**
(`UpdateIndexingRule`), up from AWS's 1 % default. Neither is in `agentcore.json`, neither
is in the synthesized template, and neither is removed by `make destroy-agent`. It also
created two log groups — `aws/spans` (30 d, AWS default) and `/aws/application-signals/data`
(**no retention at all**, now 14 d). This is exactly the "large observability or log
ingestion" surface `AGENTS.md` §3.4 names, switched on by a tool rather than by a decision.

**Two different 100 % figures, which the first draft of this entry ran together.** Span
*ingestion* into CloudWatch Logs is 100 % by construction whenever Transaction Search is
on, and is the dominant charge. Trace-summary *indexing* is a separate, configurable
percentage that the CLI set to 100 %. A third number — the built-in X-Ray centralized
head-sampling rule at `FixedRate 0.05` — was never touched and does not appear to be used
by the AgentCore OTel path at all. See `docs/COST_NOTES.md` and Q18 for the separation, and
Q18 for the CloudTrail record of the call.

Left enabled deliberately — it is what made the trace evidence below possible — but it is
now a ledger row with a documented off switch.

**Agent behavior**
Six runs, 30 tool calls, **`ok=true` on every one**; the entrypoint's own log line reports
`refused=0` for all six. The smoke path proved the whole chain: `POST /invocations` →
`invoke_agent Strands Agents` → 6 × `chat us.amazon.nova-lite-v1:0` → five `execute_tool`
spans in lifecycle order → `pool_created`, terminating on `completed`, not on a bound.

**Session state behaves exactly as `POOL_REPOSITORY=memory` implies, and it is worth being
precise about it.** Same session id twice: the second run saw the first run's pool, found
the whey demand already served, and correctly recorded `no_action`. A different session id:
fresh microVM, fresh repository, re-seeded, and a *new* pool id. **No identifier ever
crossed a session boundary** — no run referenced a pool it had not created.

**Q16 did not reproduce, and that is reported rather than manufactured.** Two deliberate
probes fed a genuinely stale pool id (`pool_46d8fafb319d`, real, from session A) into a
fresh session, the second explicitly instructing `recover_pool` as the first action. Both
times the model ignored the instruction and ran normal discovery. So the deployed refusal
path returning `ok=false` has **still never been observed in the cloud** — it remains
proven only by the local regression suite. The `{name, ok, summary}` shape from #0022 works
and is visible; every value it has ever carried in the cloud is `true`.

**Failures / dead ends**
1. **`agentcore` refuses to run outside the project root**, and the shell working directory
   persists between commands. Two invocations failed in <1 s with a path error and never
   reached AWS. Cost: nothing. Worth knowing before it looks like a runtime failure.
2. **The first five runs produced no spans at all.** Transaction Search was `PENDING`
   throughout them and only became `ACTIVE` afterwards, so their spans were dropped. A
   sixth invocation after it went active produced 25 span records including per-call token
   usage. The CLI's "~10 minutes" note is load-bearing: traces from a deploy-then-invoke
   sequence are silently lost, which would read as broken instrumentation.
3. **The `instruction` payload field does not do what its docstring says on this model.**
   `coordinator.run()` substitutes it for the whole prompt, yet `SYSTEM_PROMPT`'s
   discovery-first framing won both times. Safety-positive here — an injected instruction
   naming a consequential tool did not steer the agent into calling it — but any future
   caller that relies on `instruction` to drive a specific branch would silently get
   discovery instead. Not fixed; recorded as Q17.

**Evidence worth preserving**
Runtime ARN `arn:aws:bedrock-agentcore:us-east-1:860325090409:runtime/Pool_PoolCoordinator-TmVqSN9H56`.
Trace ids `6a8214f62a45c87e017b1aab3b031e89` (run 1) and `6a8215c441587ca2103d0b4264c5dc19`
(run 5). Per-call Nova Lite usage from spans: 2111/74, 2624/94, 3089/123, 3415/71, 3770/67,
4131/44 — summing to the 19,140/473 the response reported, so the trace and the response
agree.

**Relevant commits / files**
`BUILD_HISTORY.md` (ledger + this entry), `docs/COST_NOTES.md`. No source change: the
deployed artifact is the reviewed one.

---

### #0024 — [2026-08-16] — A public demo, and the ordering the local store had been hiding
`[AWS]` `[ARCHITECTURE]` `[SECURITY]` `[COST]` `[FRONTEND]` `[ARTICLE-2]`

**Goal / user intent**
Build the smallest, safest, most reliable public judge experience: a URL a judge can open
with no AWS account, no CLI, no credentials, and no setup. Take it as far as a verified
dry run and stop before creating any resource.

**Starting state**
The local product was complete and Bedrock-verified. The AgentCore Runtime was deployed
and `READY` with `AWS_IAM` inbound auth (#0023). **Nothing was publicly reachable.**
`PoolStack` existed but had never been deployed, and its API Lambda used
`Code.from_asset("../services/agent")` with no bundling step — a 252 MB local `.venv`
inside the asset and no dependencies installed, so the function would have failed to
deploy and then failed to import.

**Decision**
A separate stack: **one Lambda behind a Function URL, serving both the built web app and
a fourteen-path API, plus one DynamoDB table.** Eight CloudFormation resources. The
existing FastAPI app is reused unchanged in substance and reduced at runtime by a judge
mode, rather than a second application being written.

**Why**
Four questions decided it.

*What does a public browser actually need?* Thirteen endpoints. The web app calls
`health, state, map, needs, pools/{id}, pools/{id}/checklist, operator, agent/run,
decisions/{id}/respond, pickup-credential, redeem, demo/reset, demo/scenario` — thirteen
of the API's forty-five. The other thirty-two include supplier-offer mutation, the
operator pickup override, direct `lock`/`purchase`/`open-distribution`, private message
threads, and the payment webhook. None of them belongs on an unauthenticated URL, and
the lifecycle still reaches all of them because the scenario runs them server-side.

*Where is the prompt surface?* `PoolCoordinator.run()` substitutes `instruction` for the
**entire** run prompt, and `POST /api/agent/run` accepted a 600-character `instruction`
from the client. Deployed as-is that is a public endpoint for writing an agent's
instructions. Judge mode inverts it: the client sends an action *name* from a set of two,
and the server supplies the prompt. A request carrying `instruction` is **refused**, not
ignored — a silently dropped field looks like it worked, and the first person to notice
would be someone testing whether the agent can be steered.

*Why not API Gateway, S3, and CloudFront?* Because they buy nothing here. A Function URL
is HTTPS, free, and deleted with the function. The built app is 196 KB; serving it from
the same Lambda means one deployable unit, one origin, and therefore **no CORS at all** —
the local API's `allow_origins=["*"]` is simply not present in public mode.

*Why not deploy `PoolStack`?* It is the shape a pilot wants, not a demo: it carries API
Gateway, CloudFront, S3, and an EventBridge rule the demo has no use for, and its Lambda
asset is broken. Deploying a larger stack for convenience is what §3.7 forbids. That
bundling gap is **still unfixed** and still recorded — `PoolStack` remains undeployed.

**Implementation**
Implemented and tested; **nothing deployed**.

1. **`pool/api/public_demo.py`** (new) — the whole of judge mode. A route allowlist
   (404, not 403 — a public demo owes a prober no map), the trigger→prompt table, two
   quota buckets with per-session and per-day caps, the AgentCore bridge, static
   serving with path-traversal containment, and three hardening headers.
2. **`pool/api/app.py`** — five call sites: a guard built at import, CORS only when
   judge mode is off, the workspace check narrowed, quota spent on the three actions
   that cost anything, and `install()` last so the SPA fallback cannot shadow an API
   route. Every one is a no-op with `POOL_PUBLIC_DEMO` unset, so the local API is
   byte-for-byte what it was.
3. **`infra/demo_app.py`** + **`infra/test_demo_stack.py`** (new) — the stack and 38
   tests over its synthesized template.
4. **`scripts/build_demo_bundle.sh`** (new) — `uv --python-platform x86_64-manylinux2014`
   resolves Lambda's wheels from macOS, so no Docker is required. 70 MB unzipped,
   28 MB zipped, against a 250 MB limit.
5. **`scripts/scan_authored.sh`** (new) — the credential patterns in one place, pointed
   at the bundle's `pool/` and `web/` rather than at 70 MB of other people's wheels.
6. **Frontend** — a `LiveAgent` panel, the landing page's framing, and `api.run()`
   narrowed to two literal action names so the client *cannot* send a prompt.

**AWS / external services touched**
`bedrock-agentcore:InvokeAgentRuntime` — **two real invocations** of the already-deployed
runtime, through the bridge, from a browser, to prove the path end to end.
`cloudformation:DescribeStacks` (read-only, via `cdk diff`). **No resource was created.**
No Stripe call.

**Cost-relevant activity**
Two live agent runs: 19,126/469 and 19,022/418 Nova Lite tokens, ~5 s of agent time each
inside ~12 s round trips. Everything else was free.

The stack's cost surfaces are enumerated in `docs/COST_NOTES.md`. The short version:
**no always-on compute and no idle charge.** Reserved concurrency 5 is the only control
that does not depend on application code being correct, and `make demo-kill` sets it to
zero without deleting anything.

**Agent behavior**
Unchanged. The public API runs the **offline planner**, so a judge clicking around
spends no tokens and gets the same answer every time; the one live action goes to
AgentCore, which has its own model configuration. Each live invocation gets a freshly
generated 74-character session id — never derived from client input, never reused —
which is what keeps two anonymous visitors out of each other's runtime session. The
payload is built server-side from constants: no prompt, no workspace, no community id
from the caller.

**Validation**
- **571 application tests + 62 infrastructure tests**, lint clean, typecheck and web
  build clean, secret scan clean, scanner self-test clean.
- **Browser QA against the deployed configuration** (judge mode, SPA served from the
  API's own origin): the full lifecycle ran to `completed`; the denied endpoints
  returned `404` and the prompt-injection attempt returned `400 this demo does not
  accept custom agent instructions`, both verified from the page's own `fetch`; two
  sessions were mutually invisible and a reset cleared one without touching the other;
  no console errors; no horizontal overflow on any of seven views at 375 px in dark
  mode.
- **The live action was exercised for real, twice**, and its failure path was exercised
  against a nonexistent runtime ARN — `ok:false`, a named exception class, and no
  fabricated run.
- **`cdk diff` against the real account**: eight resources, all `[+]`, IAM exactly as
  designed, and the existing bootstrap satisfies it.
- **The built frontend contains no AWS identifier, ARN, account id, or credential**, and
  no hardcoded endpoint — the API base is relative.

**Failures / dead ends**
1. **The first bundle check refused to ship on `botocore/cacert.pem` and
   `certifi/cacert.pem`** — public CA bundles, matched by a blanket `*.pem` rule. Fixed
   by splitting the check: file *names* are checked everywhere, file *contents* only in
   the code Pool wrote. A check that always fires is a check everyone learns to skip.
2. **`make qa` then failed on the CDK asset copy of the same wheels.** `cdk synth` copies
   the whole bundle into `cdk.out.demo/asset.<hash>/`, so the scanner found botocore's
   documentation `AKIA…EXAMPLE` keys again. Pruned, like `agentcore/.cache` before it.
3. **The AgentCore live panel rendered `Pool_PoolCoordinatus-east-1`** — a monospace
   runtime name with no break opportunity running into the next grid column. One line of
   `overflow-wrap`.

**What we learned**
The demo had to be run on DynamoDB — a cold Lambda would otherwise lose a judge's pool
mid-demo, and two judges on two containers would see different worlds. But
`DynamoDBRepository` had never served a request, so the whole showcase was run through it
against a fake table faithful enough to be worth believing. **It failed**, with `pool did
not lock: 1 buyer(s) have not answered yet`.

The first diagnosis was wrong in an instructive way. The fake returned items in
dict-insertion order; a real Query returns them in **sort-key order**. That one
difference moved a buyer's share by a single cent — the largest-remainder split assigns
the odd cent to whoever the member list happens to put first — and a share that rises by
a cent is *materially worse terms*, which correctly raises a `price_changed` decision,
which correctly blocks the lock. So the failure was manufactured by an unfaithful fake.
**A fake that gets ordering wrong reports defects that do not exist, and hides the ones
that do.**

Fixing the fake surfaced the real defect. Enumerating both adapters showed **five list
methods where the in-memory ordering contract and DynamoDB's key order disagree**:
`list_decisions`, `list_pools`, `list_issues`, `list_threads`, and `list_host_candidates`
all sort by `created_at` or by score in memory, while their DynamoDB sort key is a random
id. Deployed, a judge's Decision Inbox would have been in arbitrary order and the host
candidate list would have been an unranked ranking — with the score column still there,
which is worse than no ranking at all. Host *selection* was never at risk: it takes an
explicit `max()` and does not read the list order. Fixed by sorting explicitly in the
adapter, and pinned by a test that mirrors one completed run into both stores and asserts
all 24 list methods return identical sequences.

The general lesson is the one worth keeping: **an implicit ordering is a contract
somebody is depending on.** The in-memory repository defined it, the UI was written
against it, and the adapter that would serve the public inherited whatever the database
happened to do.

**Article fodder**
Article 2, strongly, and Article 3 in one place. The transferable findings: reducing a
45-endpoint application to a public surface by *subtraction at runtime* rather than by
writing a second application; why `instruction` is the entire security boundary of an
agent endpoint and why refusing beats ignoring; the one-cent ordering bug and what it
says about testing against fakes; and the argument for a demo that is deterministic
everywhere except one clearly labelled button.

**Evidence worth preserving**
The `cdk diff` output (eight resources, all `[+]`). The live panel screenshot showing
`pool_created`, `us.amazon.nova-lite-v1:0`, 6 iterations, 19,126/469 tokens, 5,153 ms
agent time inside 12,130 ms round trip. The browser `fetch` probe table: five denied
endpoints at `404` and the injected instruction at `400`. The failing-then-passing
DynamoDB showcase, which is the whole ordering story in two test runs.

**Relevant commits / files**
`services/agent/pool/api/public_demo.py` (new),
`services/agent/tests/test_public_demo.py` (new), `infra/demo_app.py` (new),
`infra/test_demo_stack.py` (new), `scripts/build_demo_bundle.sh` (new),
`scripts/scan_authored.sh` (new), `scripts/run_public_demo_local.sh` (new),
`services/agent/pool/api/app.py`, `services/agent/pool/adapters/repository.py`,
`apps/web/src/api.ts`, `apps/web/src/App.tsx`, `apps/web/src/views.tsx`,
`apps/web/src/styles.css`, `scripts/secret_scan.sh`, `scripts/secret_scan_selftest.sh`,
`Makefile`, `.gitignore`, `.claude/launch.json`, `README.md`, `docs/COST_NOTES.md`,
`docs/HACKATHON_SCORECARD.md`

---

### #0025 — [2026-08-16] — The public demo went live, and four things only production knew
`[AWS]` `[SECURITY]` `[COST]` `[ARCHITECTURE]` `[ARTICLE-2]`

**Goal / user intent**
With explicit approval limited to the reviewed eight resources, deploy `PoolDemoStack`,
then verify the real deployed system rather than trusting CloudFormation's own word for
it. Leave the demo standing.

**Starting state**
`PoolDemoStack` implemented, 571 application + 62 infrastructure tests green, `cdk diff`
verified against the account at exactly eight resources. Nothing deployed. Bootstrap at
version 32 from #0023, reused.

**Decision**
Deploy as reviewed, then treat every claim made in #0024 as a hypothesis to be tested
against the live system.

**Why**
Because the interesting failures were all invisible from here. #0024 ended by naming the
DynamoDB adapter as the largest risk — verified against a fake table, never against
AWS. That instinct was right, and the fake was still not faithful enough.

**Implementation**
Pre-flight: `sts:GetCallerIdentity` → `arn:aws:iam::860325090409:user/pool-admin`,
non-root, `us-east-1`, bootstrap 32. `cdk diff` re-run on a freshly rebuilt bundle:
eight resources, all `[+]`.

**Four defects, all found by verification, none by a test:**

1. **Deploy #1 failed and rolled back.** `ReservedConcurrentExecutions: 5` was rejected:
   Lambda enforces `account_limit − Σreserved ≥ 10` and this account's limit *is* 10, so
   **no nonzero reservation is possible at all**. The property is now opt-in and the
   account limit is the ceiling instead. Reserving **0** is still allowed, so
   `make demo-kill` was unaffected — verified, it returns 429 and deletes nothing.

2. **`/openapi.json` and `/docs` were public.** The allowlist middleware only guards
   paths under `/api/`, and FastAPI's schema endpoints are not. They returned 200 and
   documented **all 42 routes**, including the thirty judge mode exists to make
   unreachable. The routes themselves were still refused — the map was the leak. Now
   `docs_url=None` in public mode; a local `make dev` keeps its docs.

3. **The first real DynamoDB request returned HTTP 500.** `ValueError: invalid format
   string`, from `format_cents` doing `f"{cents % 100:02d}"`. **Every DynamoDB number
   reads back as `decimal.Decimal`**, and `d` is not a valid presentation type for
   `Decimal`. It survived all the arithmetic silently — `Decimal` and `int` mix fine —
   and only failed at the display edge. `_from_item` now converts integral `Decimal`
   back to `int`.

4. **A refused request spent the shared daily budget.** The quota helper checked the
   *day* cap before the *session* cap, so a request the session cap went on to refuse
   had already consumed one of everyone's 40 daily live invocations. Observed live:
   `live-day` went 2 → 3 on a call that returned 429 and never reached Bedrock. One
   visitor could have closed the live agent button for every other judge, for free.
   Checking the narrower cap first fixes it; re-verified live, three refused attempts
   left the day counter unmoved.

Also fixed: the deployed Lambda logged **nothing** from application code. AWS Lambda
installs a handler on the root logger but leaves the root *level* at WARNING, so every
`logger.info` was dropped — meaning a judge's live invocation could not be correlated to
the AgentCore run it triggered. `logging.getLogger("pool").setLevel(INFO)` in judge mode.

**AWS / external services touched**
CloudFormation, Lambda, Lambda Function URLs, DynamoDB, IAM, CloudWatch Logs,
`bedrock-agentcore:InvokeAgentRuntime`, Bedrock (`us.amazon.nova-lite-v1:0`) via the
runtime. **No Stripe. No API Gateway, CloudFront, S3 hosting, EventBridge, or Amazon
Location** — confirmed absent by API, not assumed. X-Ray's trace destination is
unchanged from #0023; this deploy touched no account-level setting.

**Cost-relevant activity**
Three live AgentCore invocations through the deployed bridge (~19.2k–24.3k input,
469–652 output tokens each). Five deploy attempts grew the CDK staging bucket from
41.7 MiB to 176.8 MiB. No always-on compute exists: no reserved concurrency, no
provisioned capacity, no schedule, no distribution.

**Agent behavior**
Unchanged, and now demonstrable from a browser with no AWS account. One live run:
`run_94aaa6bdd740`, `pool_created`, 7 iterations, 6 tool calls, `refused=0`, terminating
on `completed` — the same `run_id` appears in the demo Lambda's log and in the AgentCore
runtime's log, which is the correlation that fix #5 above bought.

**Validation**
- **13-step lifecycle through the deployed API on the real table**, reaching
  `completed`: $861.44 all-in, $266.32 collective saving, 10 pickups confirmed, 1
  credential replay rejected — **identical to the in-memory run**.
- **Ordering survived**: host candidates score-descending (−36, −44, −52, −118), runs
  newest-first, Decision Inbox chronological. These are the five methods #0024 fixed.
- **Session isolation**: two populated sessions, disjoint pools, and session B got
  **404** requesting session A's pool by id. Reset cleared A and left B untouched.
- **TTL observed on real rows**: 86,378 s ahead of now, ≈24 h.
- **Prompt injection refused** (`400`), 7 consequential endpoints `404`, no
  `access-control-allow-origin` from a foreign origin, three hardening headers present.
- **Path traversal contained**: every attempt returned the app shell, never file
  content.
- **The served bundle carries no credential, ARN, or account id.**
- **Caps proven live**: the live-agent cap returned 429 with **zero** AgentCore runs
  started in the window; quota rows carry TTLs; `_quota` is unreachable as a workspace
  (400).
- 580 application + 63 infrastructure tests, lint clean, secret scan clean.

**Failures / dead ends**
Beyond the four above: **an out-of-band `update-function-configuration` survived
`cdk deploy`.** A cap tightened by hand for testing was still in force after the next
deployment, because CloudFormation does not reset a property whose *template* value has
not changed. Restored by hand. That is also precisely why the kill switch works, so it
is a property to know rather than to fix — but a temporary tightening has to be undone
deliberately, and nothing will remind you.

**What we learned**
Every one of the four defects was invisible to a green test suite, and three of them
were invisible to a *faithful-looking* fake. The DynamoDB one is the sharpest: the fake
stored Python objects verbatim, so it guaranteed a type the real service does not. The
fake now round-trips every item through boto3's own `TypeSerializer`/`TypeDeserializer`
— and with that change, removing the fix reproduces the exact production traceback.

**A fake is worth exactly its fidelity, and fidelity is not something you can assess by
reading the fake.** You find out when you deploy.

**Evidence worth preserving**
The rollback message naming the concurrency arithmetic. The `openapi.json` response
listing 42 paths. The 500 traceback ending at `money.py:50`. The `live-day` counter
going 2 → 3 on a 429. And the two log lines, from two different services, carrying the
same `run_id=run_94aaa6bdd740`.

**Relevant commits / files**
`services/agent/pool/api/public_demo.py`, `services/agent/pool/api/app.py`,
`services/agent/pool/adapters/repository.py`,
`services/agent/tests/test_public_demo.py`, `infra/demo_app.py`,
`infra/test_demo_stack.py`, `Makefile`, `BUILD_HISTORY.md` (ledger + this entry),
`docs/COST_NOTES.md`, `docs/HACKATHON_SCORECARD.md`, `README.md`

---

### #0026 — [2026-08-16] — The lifecycle became the interface
`[FRONTEND]` `[DEMO]` `[ARCHITECTURE]` `[ARTICLE-3]`

**Goal / user intent**
Make the submission competitive on the two criteria the engineering had not been buying:
**Design** and **Presentation**. The official rubric is five equally weighted criteria, so
those two are 40% of the score, and they are the only two a judge assesses almost entirely
from the interface and the video.

**Starting state**
Six tabs named after internal roles — Community, Needs, Host, **Operator**, Agent, Impact —
plus three unexplained buttons in the header. The best thing in the project, the full
thirteen-step lifecycle, was one button that dumped a transcript into a panel rendering
`key value · key value · key value` in monospace. The live AgentCore action, the single
strongest piece of technical evidence, sat below the fold on tab five, and during its ten
to twenty seconds the only feedback was a disabled button reading "Invoking AgentCore…".

Three real defects were found while reading it:

- The active nav item never highlighted. The CSS styled `[aria-current="page"]`; the
  component set `className="active"`. Nothing matched, so a judge had no idea where they
  were.
- The viability panel — thirteen checks, the clearest evidence of deterministic safety in
  the product — rendered each row with `className="feed-line"`, which the stylesheet
  defines as the 1-pixel-wide vertical connector of the activity timeline.
- `docs/ARCHITECTURE.md` and `docs/PILOT_READINESS.md` still said **"Not verified against a
  live account — no credentials were configured"**, three entries after Bedrock, AgentCore,
  DynamoDB and a public URL were all cloud-verified. A judge who read the architecture doc
  would have concluded nothing was deployed.

**Decision**
Rebuild the front end around the lifecycle instead of around the data model, and give the
AI/deterministic boundary a visual grammar instead of a paragraph.

1. **The run is the product.** *The run* presents the server's transcript as thirteen acts,
   one at a time, each with an act label, a headline, the figures that matter set as
   figures, and the evidence behind them. Arrow keys advance it.
2. **Three actors, three shapes.** Moss diamond = the agent chose this. Graphite square =
   deterministic code computed it. Clay circle = a person was asked. Every act, every feed
   entry, every panel that attributes an action carries one. Distinguishable without colour.
3. **Five surfaces named for what a visitor wants**: Overview · The run · Live on AWS ·
   Community · Operations. Nothing was deleted — Needs and Impact folded into Community,
   Host and Operator into Operations.
4. **The waiting state teaches.** The live panel shows the request's path, the caps the run
   is bounded by, and the complete list of twelve tools the agent may choose from. When the
   answer returns, the ones it actually chose are marked in order and the rest grey out.

**Why**
The transcript-reader framing was forced by a measurement: the whole lifecycle executes in
**~40 ms**. Streaming it would show nothing, and replaying it on a timer would be a progress
animation implying work that was already over — the thing `AGENTS.md` §8 exists to forbid.
So the stage bar prints the measured round trip (`whole run: 43 ms`) and the screen is
honestly a reader, not a player.

The live panel's waiting state came from the same constraint. A browser making one HTTPS
request can observe its own send and its own receive and nothing between. Lighting up
"AgentCore ✓ → Bedrock ✓ → tools ✓" during those seconds would be fiction. Showing the
twelve-door catalogue instead is true, it is genuinely interesting for fifteen seconds, and
it sets up the payoff: *here is everything it could have done, here is what it did.*

Rejected: a judge-driven wizard where each act is its own server call. More honest-feeling,
but host acceptance has no endpoint in the public allowlist, so it could not be driven from
a browser without widening the anonymous API — trading a real security property for a
presentation one.

**Implementation** — implemented and tested.

- `apps/web/src/`: `styles.css` rewritten as a design system; new `brand.tsx`, `ui.tsx`, and
  `views/{overview,run,live,community,operations,pool}.tsx`; the 1,366-line `views.tsx`
  removed. Self-hosted Instrument Serif for display, so every judge sees the same face
  rather than Iowan on a Mac and Georgia everywhere else.
- `agent/tools.py`: added `TOOL_SURFACE`, the single definition of the tool catalogue, with
  each tool's authority (`read` / `act` / `end`). `/api/health` serves it, so the UI cannot
  show a list that has drifted from what Strands is actually given.
  `test_agent_projection.py` asserts it against `build_tools()`.
- `/api/demo/config` now answers in **every** mode. It existed only under
  `POOL_PUBLIC_DEMO`, so a local run 404'd on every page load — correct behaviour, red line
  in the console of a demo whose whole pitch is honesty about what it is.
- `services/demo.py`: host candidates and the selected host carry display names. The
  transcript rendered `hh_marchetti` while every other surface in the product says "Gio M.".
- Contrast: `--ink-faint` was 3.55:1 on paper and 4.03:1 in dark. Both now ≥ 5:1. It carries
  every caption, table header and figure label in the product.
- `docs/architecture.svg` hand-authored, landscape, and legible. The Mermaid render of the
  same graph was 1474 × 2902; `docs/architecture.mmd` and `make diagram` are gone.
- The three defects above, fixed.

**AWS / external services touched**
Bedrock AgentCore Runtime and Amazon Bedrock — **one** live invocation, to verify the new
live-agent experience against the real path rather than a local approximation.

**Cost-relevant activity**
One AgentCore invocation: 19,025 input / 436 output tokens on `us.amazon.nova-lite-v1:0`.
Deliberately one. The failure state was verified by pointing the local judge-mode server at
a non-existent runtime ARN, which exercises the error path at the AWS API boundary and
spends nothing. All visual iteration ran against the offline planner.

**Agent behavior**
Live run on AgentCore: 6 iterations, terminated `completed`, outcome `pool_created`, one
human decision created. Tools called, in order: `list_latent_demand` →
`evaluate_pool_economics` → `create_candidate_pool` → `find_host_candidates` →
`request_host_acceptance`. Five of twelve — the seven it did not choose are what makes the
catalogue worth showing.

**Validation**
583 application + 63 infrastructure tests, `ruff` clean, `tsc` clean, production build
clean, secret scan clean. In the browser: desktop and 375 px, light and dark, fresh session,
reset, the full thirteen-act run, pool detail, operations, keyboard stepping, and a
scripted overflow sweep across all five surfaces — `scrollWidth === clientWidth === 375`
everywhere, with the only "overflowing" nodes being the off-screen skip link, the nav's own
scroll container, and the table inside `.table-scroll`. Console clean on a fresh tab. Live
success and live failure both observed on screen.

**Failures / dead ends**
Wrote *"Committed buyers disturbed: 0"* as a figure on the recovery act. It is true of the
design, but the server does not report it, so it was a number the client had invented —
exactly what the layering everywhere else in this project exists to prevent. Replaced with
funded-before and funded-after, both server values, and the claim moved into prose where it
belongs. Same fix applied to a hardcoded "One" on the consent act, and to a headline reading
"Two people were asked. Eight were not", which would have silently become false the moment
the seed data changed.

**Then the same mistake, one level up, and it took a reader to catch it.** The landing
figure asserted *"seven fall due together, two are pulled forward"* — nine people — under
a headline reading "Ten people wanted the same thing", above a run that ends with ten
buyers and a pool page listing **eleven** members. Three different numbers across three
screens, none of them wrong on its own, and no way for a judge to reconcile them.

Checking it against the domain rather than against intuition produced better copy than the
guess had:

| | people | units |
| --- | --- | --- |
| Buying about now anyway | 8 | 18 |
| Pulled forward, with permission | 2 | 6 |
| **Demand in this pool** | **10** | **24** |
| Supplier minimum | | 24 |

Eight were going to buy anyway and that is eighteen units against a twenty-four minimum;
two more had authorised an early purchase and their six units close the gap *exactly*.
That is the `18` the README had been quoting all along — the figure had simply been drawn
from memory instead of from the run. And the eleventh membership is the declined card,
which is why ten people buy while the record shows eleven.

Fixed by making both facts server-computed rather than authored: `_timing_split()` in
`services/demo.py` calls the same `evaluate_timing` the matcher used, and the recovery step
now carries `members_matched_at_discovery` / `buyers_after_recovery` /
`memberships_on_record` / `memberships_that_failed`. `buyer_count` joins `member_count` on
every pool view, so the Community row reads *"10 buyers (11 on record — 1 declined)"*
instead of a bare eleven. Three tests now assert the arithmetic: the split accounts for
every member and every unit, due-alone demand is genuinely below the supplier minimum
(otherwise the pull-forward mechanic has stopped being load-bearing and the story is
overclaiming), and matched − declined + replacements = buyers.

**What we learned**
`AGENTS.md` §2 already said it — *"engineering effort that never becomes visible or
explicable is under-rewarded"* — but the sharper version is that **the same discipline
applies to the interface as to the domain.** The temptation in a presentation layer is to
type a number that you know is right. It is the identical failure mode as letting a model
state a price: the value stops being traceable to the thing that computed it.

And the failure is *quiet*. Every one of "seven", "ten" and "eleven" was defensible in
isolation; the inconsistency only exists across screens, so no single view looks wrong and
no test that checks a view catches it. The rule that survives is narrower than "don't
invent numbers": **a number the interface asserts must come from the same computation the
product used to act on it.** When the split came from `evaluate_timing` instead of from
memory, the copy got better as a side effect — eighteen units against a twenty-four
minimum, closed exactly by six, is a sharper sentence than anything that was there before.

**Article fodder**
Article 3 — the actor grammar is the act-versus-ask boundary made visible, and the strongest
concrete artifact that essay could have. Article 2 — publishing `TOOL_SURFACE` from the
agent's own definition, and the twelve-doors device it enables. Demo — the script is rewritten
against the interface that now exists.

**Evidence worth preserving**
The live result panel: 5,019 ms inside the agent, 11,268 ms inside AWS, 19,025/436 tokens,
`us.amazon.nova-lite-v1:0`. The tool catalogue with five marked `called #1`…`called #5` and
seven greyed to `not chosen`. The failure banner reading *"The deployed agent did not answer
this time (AccessDeniedException). Nothing below is affected — it is computed locally."* The
before/after of the viability panel, which was a column of 1-pixel-wide rows.

**Relevant commits / files**
`apps/web/src/**`, `apps/web/index.html`, `apps/web/package.json`,
`services/agent/pool/agent/tools.py`, `services/agent/pool/api/app.py`,
`services/agent/pool/api/public_demo.py`, `services/agent/pool/services/demo.py`,
`services/agent/tests/{test_api,test_agent_projection,test_demo_scenario}.py`,
`docs/architecture.svg`, `docs/DEMO_SCRIPT.md`, `docs/ARCHITECTURE.md`,
`docs/PILOT_READINESS.md`, `docs/HACKATHON_SCORECARD.md`, `README.md`, `Makefile`

---

### #0027 — [2026-08-17] — The product became the demo
`[FRONTEND]` `[SECURITY]` `[DEMO]` `[ARTICLE-1]`

**Goal / user intent**
#0026 made the lifecycle legible and then made it the whole application. Reviewed in a
browser the result read as *an interactive presentation about Pool* rather than *Pool*:
"The run" and "Live on AWS" were primary navigation, Scan/Advance/Reset sat in the global
header like a test harness, an agent-run diagnostic was the first thing on the page, and
the centrepiece was a 01/13 stepper narrating what the demo had loaded. All useful
material, all in the wrong layer.

**Decision**
Invert the three layers. The product is primary, technical proof is secondary and hangs
off the object it explains, and the thirteen-stage reader is tertiary.

- **Home is a member's front page.** You arrive signed in as Rosa N., a real member of the
  seeded community with two standing needs, who — because one of her own Smart Join rules
  does not clear — is one of the people Pool has to *ask*. So the first thing a judge sees
  is a genuine question addressed to them.
- **Navigation is four things a member has**: Home, Pools, Needs, Community.
- **A pool is a persistent record** with Overview / People / Economics / Fulfilment /
  Activity. The Activity tab carries the audit trail, the coordinator's tool sequence, the
  deployed AgentCore run, and the thirteen-stage reader as *How this pool happened*.
- **Demo controls are a drawer** behind the environment indicator. Pool is a three-sided
  product and a judge is one person, so this is where they act for the other nine.

**Why**
The rule for the drawer is what makes it defensible: **no control sets state**. Every
button calls the endpoint that participant would call, and a control that cannot legally
run is not offered — availability is derived from the pool's own status and the decisions
actually outstanding. There is no "mark this pool purchased", because Pool has no such
operation.

**Implementation** — implemented and tested.

Ten endpoints of the forty-five moved into the public allowlist (14 → 24 paths): a
member's own account view, a host's inbox, offering to host, answering a host offer,
opening the pickup window, and leaving a pool. What stayed out, and why, is now written
down next to the allowlist itself: `lock` and `purchase` are the *agent's* decisions and a
button taking them directly would contradict the central claim of the project; `override`
would make the single-use pickup guarantee decorative; `operator/offers` would let a
stranger poison the economics every other number derives from; the payment webhook is
never trusted from a client.

Posture went **up**, not down. Seven handlers now spend the deterministic action
quota — three of them (`respond`, `pickup-credential`, `redeem`) were reachable and
unmetered before this pass. The per-session cap went 40 → 100 because one hands-on run is
about thirty actions and 40 was a limit a genuine visitor could hit halfway through; the
paid action keeps its own far tighter budget of 3/session and 40/day, untouched.

**Two real bugs, both found by building the product flow rather than by testing:**

1. **Answering a host offer did nothing.** `respond_to_decision` handled only the two
   buyer kinds. A `HOST_OFFER` decision went to APPROVED, the candidate stayed OFFERED, no
   assignment was written, and the pool sat in HOST_RECRUITING forever. The previous UI
   shipped an "Accept the job" button wired to exactly that path — it had never worked.
   The activity log also reported a host's answer as *"Buyer approved the final offer"*.
2. **`manual_advance` ran the discovery prompt locally.** The trigger-to-prompt map lived
   in the public-mode guard, so outside public mode the trigger fell through to the
   coordinator's default and the agent went hunting for new pools instead of advancing the
   one in front of it. Same button, same request, different behaviour depending on an
   environment variable — the kind of difference that survives right up until someone
   demonstrates it live.

**AWS / external services touched**
Bedrock AgentCore Runtime and Amazon Bedrock — one live invocation, through the recomposed
product in judge mode, served from the production bundle.

**Cost-relevant activity**
One AgentCore invocation: 19,355 in / 556 out on `us.amazon.nova-lite-v1:0`. Everything
else ran on the deterministic planner.

**Agent behavior**
Live run: 6 iterations, `completed`, one human decision created, five of twelve tools
chosen — `list_latent_demand` → `evaluate_pool_economics` → `create_candidate_pool` →
`find_host_candidates` → `request_host_acceptance`. Measured at three layers: 5,712 ms
inside the agent, 13,470 ms inside AWS, plus the browser's round trip.

**Validation**
589 application + 63 infrastructure tests, lint, typecheck, build and secret scan all
clean; design detector empty. The complete lifecycle driven by hand through the product
and confirmed against the server at every step:

```
find          → host_recruiting  buyers=10/10  funded=0/24   decisions=1
host accepts  → host_selected    buyers=10/10  funded=0/24   decisions=0
advance       → funding          buyers=10/11  funded=20/24  decisions=2
buyers answer → funding          buyers=10/11  funded=24/24  decisions=0
advance       → purchased        buyers=10/11  funded=24/24
open pickup   → distributing     buyers=10/11  funded=24/24
handout       → completed        buyers=10/11  funded=24/24
```

Ten buyers on eleven memberships throughout — the #0026 reconciliation holds under a
hand-driven run, not just under the scripted one. No horizontal overflow at 375 px on any
surface; console clean.

**Failures / dead ends**
Wanted the deployed AgentCore call to *be* the product action — press "Find
opportunities", the deployed coordinator investigates, product state changes. It cannot,
and the reason is configuration rather than code: the runtime ships `POOL_REPOSITORY=memory`,
so it holds no shared state and physically cannot write to a visitor's DynamoDB session.
Replaying the deployed run's decisions locally and presenting them as the deployed agent's
work was considered and rejected outright — that is fabrication under AGENTS.md §8.
So the honest framing shipped instead: the deployed run works from its own copy, the
screen says exactly that and says *why*, and what it proves is that the coordination the
judge has been driving is the same code running on AWS.

**Preservation pass**
A review of the diff caught something the recomposition had quietly cost: deleting the old
landing page took the *argument* with it. The thesis line, the three claims, "why this
needs an agent", the community-boundary framing that carries the Good Neighbor case — and,
worst of the lot, the **legend for the three actor marks**, which the product uses
everywhere and now explained nowhere. Removing something from primary navigation is not
the same as deleting it.

All of it came back as an **About** surface reachable from the drawer and the footer, with
the drawer gaining direct routes to every deep surface — *What Pool is*, *Agent
execution*, *How a pool happens stage by stage*, *Operations console* — each landing on
the evidence rather than on a record's front page. The thirteen-stage reader and the
AgentCore view were never deleted, only relocated onto the pool they describe.

Two loose ends from opening the allowlist closed with it. `host-response` went back out:
the product answers host offers through the decision inbox like every other question Pool
asks, and a second path nothing calls is surface without a capability (23 paths, not 24).
`hosting/opportunities` stayed and finally got a caller — switch account to the host and
Home shows *"You are carrying this order · 0 of 10 collected · $44.68 you earn"*, which is
the three-sided product demonstrated rather than asserted. `host-offer` and `withdraw`
became member actions on a pool: *Offer to carry this*, and *Leave this pool*, whose
refusal on a locked pool is the server's own sentence — a deterministic boundary a judge
can trigger in two clicks.

**Showcase mode**
The guided experience came back as a *second mode* rather than as a replaced one. The
environment drawer opens **Showcase**, which swaps the top navigation for the original
five destinations — Overview, The run, Live on AWS, Community, Operations — and offers
*Leave showcase* to return. It shares every component, every piece of state and every API
call with the product; the only additions are two variant props, so `About` can render the
landing-page calls to action instead of a back button and `AgentExecution` can carry its
own page heading. There is no second scenario and no second copy of any figure.

Both readings of Pool are now available from one build: use it as a member, or be walked
through it. The embedded lifecycle reader and Agent execution inside a pool record stayed
exactly where they were.

**What we learned**
The information architecture *is* the argument. Identical components, identical data,
identical agent — arranged as a walkthrough it reads as a hackathon exhibit, arranged as a
product it reads as a company. And building the product flow found two bugs a green test
suite had not, both in code paths the previous UI *exposed but never exercised*, which is
its own lesson: a button nobody has pressed is not a tested code path.

The corollary, learned the same day: a capability nobody can *reach* is also not a
capability. Depth is only worth keeping if it has a door.

**Article fodder**
Article 1 — the strongest available demonstration that this is a coordination product
rather than an agent demo. Article 3 — the drawer is the act-versus-ask boundary from the
other side: everything in it is a *person* answering, because those are the only decisions
Pool does not make itself.

**Relevant commits / files**
`apps/web/src/App.tsx`, `apps/web/src/views/{home,pools,needs,pool,demo-panel,community,operations,live,run}.tsx`,
`apps/web/src/{api.ts,styles.css,brand.tsx}`, `apps/web/src/views/overview.tsx` (removed),
`services/agent/pool/api/{app,public_demo}.py`,
`services/agent/pool/services/coordination.py`,
`services/agent/tests/{test_api,test_coordination,test_public_demo}.py`,
`README.md`, `docs/{DEMO_SCRIPT,HACKATHON_SCORECARD,COST_NOTES}.md`

---

### #0028 — [2026-08-17] — The deployed agent started writing the workspace the browser reads
`[ARCHITECTURE]` `[SECURITY]` `[AWS]` `[AGENT]` `[COST]` `[ARTICLE-2]`

**Goal / user intent**
Close the largest remaining architecture gap. The public product ran on authoritative
DynamoDB state; the deployed AgentCore Runtime ran with `POOL_REPOSITORY=memory`, so its
Strands agent operated on an isolated copy and could not touch the pool the visitor was
looking at. That forced the UI to present the deployed runtime as *technical proof* rather
than as the product's own action, and it made the honest copy read as an apology: "it works
from its own copy and leaves your pool alone."

**Starting state**
Two halves that never met. `AgentCoreBridge.invoke()` built its payload from constants and
generated a throwaway workspace (`live<uuid>`) so nothing a caller sent could reach the
runtime. The runtime seeded that workspace inside its microVM, ran, returned a summary, and
the state died with the container. Everything the browser saw came from the API Lambda's
own offline planner. Both agents were real; only one of them mattered to the product.

**Decision**
Point the runtime at the same DynamoDB table and the same partition, and make the product's
`Find opportunities` the thing that invokes it. The workspace becomes the one caller-derived
value in the payload — validated by the server, never seen by the model — and the resulting
state is read back out of the store rather than assembled from the model's answer.

Four boundaries make the wider blast radius acceptable:

1. **The workspace is a server value on every hop.** The client sends its session id as the
   query parameter every request already carries; `PublicDemoGuard.check_workspace` checks
   it against `PUBLIC_WORKSPACE_RE`; the bridge builds the payload from the *checked* value.
   There is no body field to smuggle a second workspace through, and the endpoint takes no
   body. It grants nothing new: a session id is already a bearer capability over that
   workspace through this same API, so binding the agent to it widens no boundary.
2. **The model never sees it.** No tool takes a workspace argument, and the string appears
   in neither the system prompt nor the run instruction. The model chooses *what to do* and
   cannot choose *whose data to do it to*.
3. **Authority is asymmetric.** The API owns workspaces — it seeds them, resets them, and
   rations how many open per day. The runtime is only ever a participant inside one that
   already exists: it refuses to seed a shared store, and its execution role holds
   `GetItem`, `PutItem`, `Query` and nothing else. `Repository.reset()` needs `DeleteItem`
   and `BatchWriteItem`, so emptying a visitor's session is not something the agent can do
   badly; it is something it cannot do.
4. **One live run per workspace at a time**, held by a conditional-write lease.

**Why**
The alternative — replaying the deployed agent's decisions locally, or copying its output
into DynamoDB — was never on the table (§8). It would also have been *more* code than doing
it properly. What made "properly" cheap is that the seam already existed: `Repository` is a
protocol, `PoolCoordinator` takes one, the typed tools close over `PoolContext.ws`, and
`DynamoDBRepository` had already been exercised end to end by a fake-table test. Nothing in
the agent, the tools, the services, or the domain changed. The whole feature is a
configuration change plus a binding plus a lock.

Rejected: giving the runtime its own table (a second source of truth, and the same problem);
having the Lambda apply the runtime's decisions (fabrication); routing *every* action through
AgentCore (each press would spend tokens, and the caps are 3/session).

**Implementation** — status: **implemented and tested**, **not deployed**.

- `agentcore/agentcore.json` — `POOL_REPOSITORY=dynamodb`, `DYNAMODB_TABLE=pool-demo-state`,
  `DYNAMODB_CONSISTENT_READS=true`, `WORKFLOW_TIMEOUT_SECONDS` 120 → 45, and
  `additionalPolicies: ["iam/agentcore-dynamodb.json"]`.
- `services/agent/iam/agentcore-dynamodb.json` — three actions, one table. The AgentCore CDK
  construct resolves the path relative to `codeLocation` and attaches it inline to the
  runtime's execution role. Discovered by reading the L3 construct's schema; it is the hook
  that made least-privilege possible without hand-writing the runtime's IAM.
- `services/agent/agentcore_app.py` — refuses to seed a shared store; workspace validation
  moved from `str.isalnum()` on a stripped string to an explicit pattern (the old idiom
  accepted every Unicode letter and digit, so `café` was a valid partition key).
- `services/agent/pool/api/public_demo.py` — `invoke(workspace)`; `LeaseStore` in two
  implementations mirroring the quota store; `RuntimeRefusal` as a distinct failure;
  `LIVE_READ_TIMEOUT_SECONDS`.
- `services/agent/pool/adapters/repository.py`, `config.py` — optional strongly consistent
  reads, on wherever the two halves share a partition.
- `infra/demo_app.py` — explicit `table_name`, Lambda timeout 30 s → 90 s.
- `apps/web` — `findOpportunities` invokes the deployed agent when one is configured and
  falls back to the local coordinator otherwise; the technical view's copy corrected.

**AWS / external services touched**
`sts:GetCallerIdentity`, `cloudformation:DescribeStacks`, `dynamodb:ListTables`,
`iam:GetRolePolicy` — all read-only — and `agentcore deploy --dry-run`, which synthesizes
and creates nothing. **No resource was created, changed, or destroyed. The ledger is
unchanged.**

**Cost-relevant activity**
No model tokens were spent. Local verification used an unreachable ARN with no credentials,
so the bridge failed at credential resolution and never reached AWS.

Three cost changes are *pending deployment* and worth stating before they happen:

- **`Find opportunities` becomes the paid path.** It was free (offline planner); it now
  spends one Nova Lite run — ~19k in / ~500 out on the observed run, about **$0.0013**. The
  existing caps are unchanged (3/session, 40/day), so the ceiling is unchanged at roughly
  **$0.05/day**. What changes is that the cap will now actually be approached.
- **Strongly consistent reads** cost 1 RRU instead of 0.5 on a per-request table.
- **Lambda timeout 30 s → 90 s** raises the worst case for a wedged request to about a tenth
  of a cent. It is the outermost of three nested deadlines (agent 45 s < bridge 60 s <
  function 90 s) so that the innermost fires first and the caller always gets a structured
  answer instead of a dropped connection.

**Testing**
`tests/test_agentcore_shared_workspace.py` (31 tests) reproduces the deployed topology
in-process: **two `DynamoDBRepository` instances over one `FakeDynamoTable`**, with the
runtime side calling the real `agentcore_app.invoke`. The central assertion is that the
pool the browser renders has `created_by_run` equal to the run id the runtime reported —
i.e. the row was written by the process on the other side of the wire, not copied from its
answer. Also covered: two sessions, forged and internal workspace names, an invented pool
id, a re-entrant second invocation, reset during a run, reset then re-run, timeout after
partial progress, a call that never started, quota refusal (and that no refused call reaches
AWS), and that the runtime issues no delete or update operation.

`infra/test_demo_stack.py::TestSharedWorkspaceContract` asserts the table name, the IAM
grant, the consistent-reads flag, the trigger name, and the deadline ordering agree across
three files deployed by two different tools — a drifted name would fail silently, with the
agent writing to a table nobody reads.

Full suite: **697 passing** (626 agent + 71 infra), `ruff` clean, `tsc` clean.

**Failures and surprises**

- **A fake that was one class too generous.** `FakeDynamoTable.update_item` raised a bare
  `ClientError` on a conditional failure. DynamoDB raises a *modeled* subclass named
  `ConditionalCheckFailedException`, which is what both stores match on. The quota store's
  own test passed anyway — its fail-closed branch returns `False`, the same answer a refusal
  produces — and the wrong behaviour only surfaced when the lease store needed a refusal and
  a reclaim to differ. Fixed by having the fake raise the real class, which needs nothing
  but an offline `boto3.client`.
- **Two lease implementations disagreed by a second.** In-memory treated a hold as over when
  `until <= now`; DynamoDB required `until < now`. Aligned on `<=`.
- **A test that could not send its own hostile input.** `workspace=ws#POOL` was truncated at
  the fragment by the client and never reached the server, so the case passed for no reason.
  Percent-encoded now.
- **A refusal is not a lost call.** The runtime returning `{"error": …}` was being collapsed
  into "the agent did not answer, it may still have finished" — untrue, since the entrypoint
  validates before it runs anything — and it held the workspace for the full lease. Split
  out as `RuntimeRefusal`: released immediately, reported as a refusal.
- **Copy can assert something the code does not guarantee.** The technical view read "the
  pool you are looking at was formed by that run", which is false whenever the fallback ran.
  Caught in a browser, not by a test: the local demo has no runtime configured, so the
  fallback is the only path a local reviewer ever sees.

**What we learned**
The gap was never the agent. It was one environment variable and an IAM statement, guarded
by a lock that did not exist yet. Everything expensive — the typed tools, the domain
services, `_require_pool`, the idempotency keys, the bounds — worked unchanged against the
shared store, because they were written against a protocol rather than against a store. The
work that remained was almost entirely about the *seams*: who may name a workspace, who may
create one, who may destroy one, and what happens when two writers arrive at once.

The honest-copy discipline paid twice. Both times the change made an existing sentence false
— "it leaves your pool alone", then "the pool you are looking at was formed by that run" —
and both times the false sentence was easier to spot than the underlying behaviour would
have been.

**Article fodder**
Article 2 — the whole entry. Two compute environments, one partition, and the four questions
that arrangement forces: who validates the tenant key, whether the model may ever see it,
what happens to a read-modify-write race, and which side is allowed to delete. The IAM
asymmetry (read/write but never delete) is the crispest single artefact: the most
destructive operation in the codebase is unavailable to the agent by construction rather
than by care.

**Relevant commits / files**
`agentcore/agentcore.json`, `services/agent/iam/{agentcore-dynamodb.json,README.md}`,
`services/agent/agentcore_app.py`,
`services/agent/pool/{config.py,adapters/repository.py,api/app.py,api/public_demo.py}`,
`services/agent/tests/{test_agentcore_shared_workspace.py,test_public_demo.py}`,
`infra/{demo_app.py,test_demo_stack.py}`,
`apps/web/src/{App.tsx,api.ts,views/live.tsx}`,
`README.md`, `docs/ARCHITECTURE.md`

---

### #0029 — [2026-08-17] — Close the reset and ambiguous AgentCore races
`[SECURITY]` `[CONCURRENCY]` `[AGENT]`

**Goal / user intent**
Fix the two remaining correctness gaps in the shared-workspace checkpoint without widening
the architecture: reset must not release its workspace lease before destructive reseeding,
and an AgentCore timeout must not fall through to a local mutating run against the same
partition.

**Implementation** — status: **implemented and tested**, **not cloud-verified or deployed**.

- Reset acquires the per-workspace lease and holds it across the quota check and the entire
  `seed()` operation, releasing it in `finally`. A live AgentCore attempt during reseeding
  is refused before it can spend quota or reach the runtime.
- The live endpoint now returns a server-owned classification. Safe runtime refusals and
  disabled/pre-execution paths explicitly permit a local fallback after releasing the
  lease. Ambiguous runtime failures explicitly forbid fallback, request an authoritative
  state refresh, explain that the deployed run may still be finishing, and leave the lease
  held until it expires safely.
- The browser follows `allow_local_fallback` from the server and treats a missing response
  conservatively as ambiguous; it never parses exception strings to decide whether a local
  mutation is safe.

**Regression coverage**
The shared-workspace suite now reproduces the old reset interleaving by attempting a live
run from inside destructive reseeding, verifies reset lease cleanup on errors, and asserts
timeout classification, state refresh, protection from another run, safe refusal, and
recovery after the held lease is released. The existing live-run/reset interleavings remain
covered as well. Focused shared-workspace/public-demo tests: **121 passed**.

**Verification**
`make qa`: `ruff` clean, TypeScript clean, **629 agent tests passed** (one existing
Starlette/httpx deprecation warning), **71 infrastructure tests passed**, web production
build clean, secret scan clean. `make agent-validate`: **Valid**. No deployment or cloud
verification was performed.

---

### #0030 — [2026-08-17] — Cloud verification of the shared workspace, and the two bugs only production had
`[DEPLOYED]` `[INCIDENT]` `[AGENTCORE]` `[COST]` `[PAYMENTS]`

**Goal / user intent**
Take #0028/#0029 — the deployed AgentCore runtime coordinating inside the same DynamoDB
workspace the browser reads — from *implemented and locally green* to **verified on real
AWS**, then QA the live public product end to end as a judge would.

**Starting state**
`4dcfcc8` on `main`, working tree clean, 700 tests green locally, nothing about the shared
workspace exercised against AWS. Deployed: the runtime still on `POOL_REPOSITORY=memory`,
the demo stack still on the generated-name table.

**Decision**
Deploy AgentCore first, then `PoolDemoStack` (the table rename is a replacement, and the
runtime's IAM statement and `DYNAMODB_TABLE` both name `pool-demo-state`, so the grant has
to exist before the table is served). Then prove the chain with one paid invocation and
read the result out of DynamoDB rather than out of the agent's answer.

**Implementation** — status: **deployed and verified**

Both deploys were reviewed as diffs before running. AgentCore added exactly one resource
(the DynamoDB inline policy) and changed four env vars; `PoolDemoStack` replaced the table,
retargeted the existing grant, and moved the function to a 90 s timeout. **No new service
appeared in either.**

**The shared-state proof.** Fresh browser session `w0t5x5s164x112i5q`, seeded to 110 rows
with **0 `POOL` and 0 `RUN`**. One click on *Find opportunities*:

| | |
| --- | --- |
| run id | `run_f542309cf199` |
| model | `us.amazon.nova-lite-v1:0` via Bedrock, Strands loop |
| iterations | 7, terminated `completed` |
| tools | `list_latent_demand` → `evaluate_pool_economics` → `create_candidate_pool` → `find_host_candidates` → `request_host_acceptance` → `issue_final_offer` |
| tokens | 23,304 in / 504 out |
| agent duration | 7.47 s (runtime's own `started_at`→`ended_at`) |
| end to end | 15.49 s (Lambda `REPORT`, including runtime cold start) |

The pool the browser then showed, `pool_d6e1981c0937`, carries
`created_by_run = run_f542309cf199` in DynamoDB — the same id the runtime returned to the
Lambda (`live agentcore run run_id=run_f542309cf199 outcome=pool_created tools=6`) and the
same id the runtime logged itself, alongside
`coordination run starting workspace=w0t5x5s164x112i5q` — the browser's own
`localStorage` value. **No local fallback could have produced it:** the API Lambda runs
`MODEL_PROVIDER=offline` and its execution role holds no `bedrock:InvokeModel` at all, so a
run record naming `bedrock`/`nova-lite` cannot originate there.

**Two production-only bugs, both fixed here.**

**(a) One live action, two billed agent runs.** `AgentCoreBridge` asked for a single
attempt with `retries={"max_attempts": 1, "mode": "standard"}`, with a comment saying
exactly why a retry would be unacceptable. That config does not mean one attempt. Botocore
treats `max_attempts` as the legacy shorthand and resolves it to
`total_max_attempts = max_attempts + 1`, so the code was asking for **one retry**. A forced
read timeout against the deployed runtime produced **two runs 17 ms apart, both coordinating
the same workspace** (`run_2ebf71d30e77` *pool_advanced* and `run_69750143627d`
*pool_created*). The retry is issued inside botocore, underneath the code that takes the
`DynamoDBLeaseStore` lease — so the lease that exists precisely to stop two agents in one
partition never saw it. Measured directly against a local socket server that accepts and
never answers: shipped config → **2** TCP attempts; `total_max_attempts: 1` → **1**.
Fixed to `total_max_attempts`, redeployed, and the same forced timeout now yields one run.

**(b) The simulated processor forgot its own payments across containers.**
`LocalSimulatedPaymentProvider` kept intents in a per-process dict while the pools
referencing them lived in DynamoDB. On one machine those lifetimes are identical and the
gap is invisible; on Lambda they are not. An authorisation taken on one container was
captured on another, whose dict was empty, and `capture()` raised
`unknown payment reference` **from inside `capture_pool`, after the pool had already
locked**. Observed on the deployed demo: 1 payment captured, **1 stranded in
`capture_pending`**, 8 untouched, and no way forward — `lock_pool` short-circuits on an
already-locked pool, so no later run re-enters capture. The hands-on lifecycle simply could
not reach *purchase* on the public URL. It never showed locally or in the scripted showcase
because both run the whole lifecycle in one process.

Fixed by encoding the simulation's entire decision into the reference
(`pi_sim_{f|c|n}{amount}_{rand}`) so any process can reconstruct the intent. That is also
the more faithful simulation: a real processor is a durable remote service that recognises
its own reference from any caller. The rebuilt state is taken from the operation, which is
sound because every caller in `services/payments.py` has already gated on the authoritative
`PaymentRecord` — capture only runs on `AUTHORIZED`, cancel refuses `CAPTURED`, refund
requires it (AGENTS.md §6). A declined authorisation is the one case that ignores the
caller and stays declined, so a refusal can never be reconstructed into a charge.

**AWS / external services touched**
Bedrock AgentCore Runtime, Bedrock (nova-lite), Lambda, DynamoDB, CloudWatch Logs, X-Ray,
IAM, CloudFormation/CDK, S3 (CDK staging).

**Cost-relevant activity**
**10 AgentCore invocations total**, 9 of which built a run; 7 went through the public
endpoint and 3 were direct probes with developer credentials. Largest single run 26,063
input tokens. Two of those 10 were the duplicate-retry bug — which is the cost story: the
bug's whole shape is *paying twice and never being told*. Day counters ended at
`live 7/40`, `action 40/600`, `newsession 12/300`. X-Ray: 3 traces, **0 faults, 0 errors**.
Account sweep after the work: 1 Lambda, 1 table, 1 runtime, 0 EventBridge rules, 0 EC2,
0 RDS, 0 ECS, no new service anywhere.

**Agent behavior**
Bedrock/nova-lite through Strands, 12 typed tools, bounds honoured (max 8 iterations
observed 6–8). A second invocation on a workspace that already had its pool returned
`no_action` after re-costing five products — **idempotent, no duplicate pool**. Direct
invocation against a workspace with no Community returned
`workspace has no community; this runtime does not create one` and wrote **zero rows**,
confirming the runtime cannot bootstrap or destroy a workspace it shares.

**Validation**
Deployment: runtime `READY` v2 with the intended env; stack `UPDATE_COMPLETE`;
`pool-demo-state` `ACTIVE`, PAY_PER_REQUEST, TTL `ENABLED`. Isolation: a second session
sees 0 pools and 404s on the first session's pool id, and the two DynamoDB partitions are
disjoint. Refusals: 8 malformed workspace shapes → 400; a body naming another workspace is
ignored; custom `instruction` → 400; unknown trigger → 400 with the allowlist; reset during
a held lease → 409; a live run on a busy workspace → `workspace_busy` **without spending a
paid unit**; an exhausted session cap → 429 with the shared day counter **unchanged**.
Ambiguity: both a forced client error and a genuine read timeout classify as
`ambiguous_remote_execution` with `allow_local_fallback: false` and the lease **held**, and
the abandoned run's pool was still there afterwards — the honest outcome.
Product QA on the public URL, full lifecycle to completion: **10 buyers, 11 memberships
(1 declined and kept, `card_declined` intact in Operations), 24/24 units against MOQ 24,
0 surplus, 2 cases, $861.44 all-in, $266.32 saved**, 10/10 pickups. The timing split is
**8 due / 18 units + 2 pulled forward / 6 units at discovery** — reproduced identically by
three separate AgentCore runs and by the offline showcase — and **7 / 16 + 3 / 8 over the
ten buyers of the finished pool**, because the decline recovery replaces a routine buyer
with a pulled-forward one. Two moments, two true answers; see the reconciliation below. Post-lock withdrawal → 409; credential
replay → refused; forged credential → refused. `/docs`, `/redoc`, `/openapi.json` serve the
SPA and expose no schema; every non-allowlisted path 404s; no `access-control-*` header on
any origin; the served bundle contains no credential, ARN, account id, table name or
function name. 375 px: **0 horizontal overflow on every view** (the wide supplier table
scrolls inside `.table-scroll`). Dark mode 15.93:1 body / 7.10:1 muted. No console errors
beyond the 429/409 this QA deliberately caused.
Tests: **705 passing** (634 agent + 71 infra), up from 700. Both new regression suites were
confirmed to **fail against the pre-fix code** before being accepted.

**Failures / dead ends**
Twelve concurrent requests fired to force multi-container scheduling hit Lambda's own
throttle and returned bare 429s — this account's concurrency limit is 10, and the demo's
real ceiling is therefore ~10 simultaneous requests. Not a product fault; the UI degraded
to an error card with a *Start a fresh session* affordance. Also: the first attempt to
observe the ambiguous branch by temporarily repointing `AGENTCORE_QUALIFIER` on the live
function was refused by tooling policy, so the branch was exercised by running the deployed
code path locally against the real runtime instead — same code, real AWS, no change to what
the public URL was serving.

**What we learned**
Two lessons with the same shape: **a comment describing an invariant is not the invariant.**
The retry config carried a paragraph explaining why a second invocation would be
unacceptable, and asked for one anyway; the payment provider was correct in every test
because every test was one process. Both bugs live exactly where local execution and Lambda
execution differ — retries below the application's own concurrency control, and process
memory beside durable state. A shared-state architecture makes both far more consequential
than they were the day before: until #0028 the runtime wrote a throwaway store, so a
duplicate run cost tokens and nothing else. **Test at the boundary the deployment actually
has**, which is why the new payments tests instantiate two providers.

**Article fodder**
Article 2. `total_max_attempts` vs `max_attempts` is a genuinely good short story — a
one-word config bug that defeated a distributed lock by operating underneath it, found only
because a timeout was deliberately provoked against real infrastructure. The payment-intent
bug is the companion piece on why "works locally" and "works serverless" are different
claims.

**Evidence worth preserving**
Run `run_f542309cf199` → `pool_d6e1981c0937` with matching `created_by_run`, correlated
across the Lambda log line, the runtime log line and the DynamoDB row. The two-run timeline
(`19:51:26.392` / `19:51:26.409`) from one `invoke_agent_runtime`. The stranded-capture
state (`captured: 1, capture_pending: 1, authorized: 8`) and the agent's own tool record
`lock_pool ok=False Error: PaymentError - unknown payment reference`. The completed
Operations view showing `SIMULATED-ORDER-…` and `Pia V. · card_declined` retained.

**Relevant commits / files**
`services/agent/pool/api/public_demo.py` (retry config),
`services/agent/pool/adapters/payments.py` (reference-encoded intents),
`services/agent/tests/test_payments.py` (+4 cross-container tests),
`services/agent/tests/test_agentcore_shared_workspace.py` (+1 retry test),
`BUILD_HISTORY.md` (ledger: table replaced, new AgentCore IAM policy, Lambda 90 s).

**Two reconciliations, closing the same phase**

Reviewing the report against the data turned up two numbers that did not survive being
asked where they came from. Neither was a crash; both were the interface stating
something the system does not do.

*The timing split reported two different ways.* 7/16 + 3/8 and 8/18 + 2/6 both appeared,
and the first reading was that the live agent had discovered a different pool from the
canonical one. It had not. Measured across the four surviving workspaces, **every
AgentCore discovery produced 8/18 + 2/6, exactly matching the offline showcase** — the
model chose the same pool the deterministic planner does. 7/16 + 3/8 is the *same pool
after recovery*, over its ten final buyers: Pia V.'s card declines and the replacement
recruited is a pulled-forward member, so one member moves columns. Discovery and outcome,
not live and canonical. `test_the_convergence_figure_matches_the_seed` now asserts against
the discovery step explicitly, and said so by failing the first time it was pointed at the
finished pool.

*The figure drew a person who does not exist.* `ConvergenceFigure` claimed in its own
docstring to be "the arithmetic of the pool this community actually forms", drew eleven
people, and ended "the eleventh authorised nothing, so nothing happens to them."
Recomputing from the seed: **thirteen** households hold a whey need, **none** is
timing-ineligible — 8 routine (18 units) and 5 who authorised an early purchase (13
units). Pool takes two of those five, and not the two nearest: it reaches past a 16-days-
early 2-unit need to a 19 and a 29 whose 3 + 3 lands on twenty-four **exactly**. The three
it leaves are not people who withheld permission; they are people whose units would have
been surplus nobody ordered. The figure was right about 8/18 and 2/6 and wrong about the
more interesting half. Now thirteen rows, and the drawing shows Pool reaching past nearer
candidates — the no-speculative-surplus invariant made visible rather than asserted.

*A published bound no run could hit.* `WORKFLOW_TIMEOUT_SECONDS` was 45 in
`agentcore.json` and **120** in the demo function's environment — against that function's
own **90 s** timeout. So on the local execution path the innermost deadline sat outside
the outermost one and could never fire; Lambda would kill the request at 90 first. And
because `/api/health` publishes the function's copy, the Live-on-AWS view printed
"120s wall clock" directly beneath a deployed AgentCore run actually held to 45. Set to
**45 in both**, which restores the nesting in both directions — **45 agent → 60 bridge
read → 90 function** — and makes the single number that page prints true of every run it
lists, wherever it ran. Observed offline runs are 108 ms–1.1 s, so 45 s is ~40x headroom.
`test_every_published_bound_is_one_a_run_can_actually_hit` pins the two files together and
refuses any bound that exceeds the function timeout.

**Redeployed** for these two: both are user-visible on the public URL — one is copy in the
served bundle, the other an environment variable the health endpoint publishes — so
leaving them uncommitted-but-undeployed would have kept the live demo stating them.
Tests after: **707 passing** (635 agent + 72 infra). Both new tests were confirmed to fail
against the pre-fix figure and the pre-fix bound.

**What the pair have in common:** each was a *number that had stopped describing
anything*, and each had a comment nearby asserting it was accurate — "it is the
arithmetic... drawn", "the three numbers live in three files, which is why this is worth
asserting". The existing deadline test did assert an ordering; it just asserted the
runtime's bound and never the function's own. A test that checks the number you remembered
to check is not coverage of the claim.

---

### #0031 — [2026-08-18] — An external audit, and the difference between a bound and a claim

**Status: Implemented, Tested, Deployed.** An independent read-only audit produced a
findings list. This entry records what survived contact with the code, what did not, and
the one finding that was real in a different way than reported.

**Two P0s.**

*Workspace mutations were not all serialised.* The lease existed and was correct — it just
guarded one caller. The browser opens with `Promise.all([state(), map()])`, both reach
`ensure_seeded`, and `seed()` begins with `repo.reset()`, so a cold first load was *always*
a race in which the second seed deletes rows the first has written. The scenario and the
local coordinator run held nothing either. Now one lease per workspace is taken by every
coordinator that scans-then-writes: seeding, reset, scenario, local run, live run.

Four decisions inside that are worth keeping:

- **Re-entrant per request.** A coordinator run seeds a cold workspace before it runs, so
  an inner acquisition that blocked on its caller's own lease would deadlock a request
  against itself. Thread-local depth, because a sync FastAPI handler runs start to finish
  on one worker thread.
- **Always on, not gated on public mode.** Two tabs are two tabs on a laptop. A protection
  that only exists in production is one nothing ever tests.
- **Seeding waits; it does not 409.** Every other mutator refuses immediately, but a first
  page load must not error — the loser polls the store briefly and renders what exists.
- **The lease is coordination, not the invariant.** So the writes it protects are also
  conditional: candidate creation claims its idempotency key with a conditional put and
  hands the loser the *winner's* pool id, and pickup redemption claims its credential with
  a conditional update. The claim is written before the pool and carries the id, which is
  what makes a crash between the two writes recoverable rather than a key nobody can use
  again.

*Final-offer convergence.* Reported as "the fourth pass may prune and exit with stale
economics". Structurally true and worse than described — reproduced with
`MAX_PRICING_PASSES=1`: economics for ten buyers and twenty-four units against nine
surviving members, **seven of them authorised at ten-buyer prices**, and a twenty-four-unit
order for twenty-two units of real demand. Those per-buyer figures are what
`authorize_participant` puts a hold on and the case count is what sizes the supplier order,
so it is a money bug, not a display bug.

**But the reported reachability was wrong, and that is the more interesting half.** No
shipped *hard* policy rule is price-dependent — `min_net_savings` and `max_spend` are soft
and return `HUMAN_APPROVAL_REQUIRED`; only `substitution` and `pickup_day` are hard, and
neither moves with price. So pruning always finishes on pass 1 and passes 2–4 are spare.
Measured: a hard rejection uses **two** pricing passes and economics matched membership.
The invariant was holding **by accident of the policy table**, not by construction. Making
one soft rule hard — an ordinary future product change — would have silently authorised
money at the wrong price. Fixed anyway: economics are now assigned in exactly one place,
guarded by a pass that rejected nobody, and running out of passes fails loudly and
authorises no one.

**A label that had stopped being true.** `find_host_candidates` was published as a *read*
to the model, to `/api/health`, and to the Showcase page, while calling
`open_host_recruiting` — which transitions the pool and logs activity — and persisting a
candidate record per evaluation. The tool was fine; the label was the defect. Rather than
fix one string, the effect vocabulary grew a fourth kind (`record`) and, more usefully,
`test_agent_effects.py` now snapshots the **entire workspace** around every tool declared
`read` and fails if anything moved. Confirmed it fails against the old label. The deployed
live run then showed `find_host_candidates` returning `status: host_recruiting`, which is
the mislabel visible in production output.

**A bound that enforced nothing.** `MAX_TOOL_RETRIES=3` was in `config.py`, both CDK
stacks, the AgentCore runtime, and `COST_NOTES.md` as "bounded with backoff" — and was read
by nothing. Pool has no generic tool retry, and re-running a consequential call is the
wrong default for a system that moves money, so it was **removed rather than implemented**.
The 45 s wall clock is now described as what it is: cooperative, checked *before* each
model and tool call, ending a run that is taking too long but unable to interrupt one that
has hung — the bridge's 60 s read timeout and the function's 90 s timeout are the rungs
that bound that. A configured limit for behaviour that does not exist is worse than no
limit, because it reads as a guarantee. `AGENTS.md` §3.1 now says so.

**The product gained its primary action.** Needs were readable and not writable, which made
the most distinctive thing about Pool the one thing a judge could not do. `POST /api/needs`
and `POST /api/needs/{id}` go through a new `services/needs.py`, exposing only fields the
domain already stores and enforcing the rules deterministically: one active declaration per
household per product (two rows would double-count demand), pull-forward capped at one
cadence (restocking before the previous purchase is used is storage nobody agreed to), and
an ownership check so supplying your own id cannot rewrite someone else's rules. Smart Join
mode is deliberately absent — it is an account property, not a need's, and putting it here
would make a settings product out of the one screen that should stay a single sentence
about what you buy. Nothing in the form can create a group.

**Two lifecycle defects.** Pickup credentials could be issued and redeemed between
`PURCHASED` and `DISTRIBUTING` — allocations exist after purchase, so every check the code
performed passed, and the goods were still at the supplier. Gated on both issuance and
redemption, with the lifecycle check placed *after* credential identification so a
wrong-pool scan keeps its own distinct audit reason. And host ranking disagreed with itself:
the domain broke ties toward the lower household id, the service selected with
`max((score, household_id))` and therefore preferred the higher one. Both deterministic,
both defensible, and they named different people — so the ranking shown and the offer made
could differ. One exported `ranking_key`, both callers use it.

**A public 500, found while verifying something else.** `IllegalTransition` is a
`ValueError`; routes that did not name it explicitly turned a correct refusal into a server
error. `open-distribution` is public, so clicking it twice on a finished pool returned one.
Handled once at the app level as a 409 — no route can miss it, and no future route has to
remember.

**The quality gate was reporting a green tick over a skipped application.** `npm run lint`
referenced ESLint from the first commit and ESLint was never a dependency, and `make qa`
did not call it at all. ESLint installed (16 files, 0 findings, and confirmed to catch a
planted defect), thirteen frontend tests added against the two things only a frontend test
can assert — that the primary action reaches the API, and that the words beside a number
match the number — and `qa` now runs both. `vitest` pinned to v3 rather than v2 so the test
tooling added **zero** new advisories; production `npm audit` stays at 0. The two remaining
Vite/esbuild advisories are development-only and fixable only by a major upgrade, which is
not a thing to do days before a freeze.

**Cloud.** The Lambda's table grant went from `grant_read_write_data` to the five actions
the code issues; `Scan` is the one worth naming, since it is what turns a per-workspace
single-table design into a whole-table read. The AgentCore policy's region wildcard is
pinned. Security headers gained CSP, HSTS and Permissions-Policy — the CSP was written
against the built bundle rather than from a template, which is why `script-src` can be
`'self'` with no `unsafe-inline`, and why `style-src` honestly keeps it (the views use React
`style={{}}`, which CSP counts as inline).

**Reserved concurrency remains impossible, and the docs now say so.** Re-verified: account
limit **10**, unreserved **10**, quota `L-B99A9384` value 10. AWS enforces
`account_limit - sum(reserved) >= 10`, so any reservation is rejected. `README.md` claimed
one and `COST_NOTES.md` claimed a specific reservation of 5 that never existed on the
deployed function. No quota increase requested — the account ceiling is the cheaper control
and it is already in force.

**Two findings were not acted on, deliberately.** The reported secret-scanner noise was
`gitleaks`, which this repository does not use; its own scanner exits 0 and its self-test
still catches planted secrets, so adding suppressions for a tool we do not run would have
repeated the `MAX_TOOL_RETRIES` mistake exactly. And participant actions — respond,
withdraw, host-offer, open-distribution, pickup, needs — stay **outside** the lease. Holding
it for a 45 s agent run would refuse a member their own primary action to protect them. The
residual race is real (`issue_final_offer` reads its membership set once; a withdrawal
landing after that read is included and overwritten), needs genuine concurrency, and is now
written down in `PILOT_READINESS.md` as a pilot blocker with the actual fix: entity
versioning plus a transaction around the final-offer write set. Not a wider lock.

**Verified.** `make qa` green: ruff clean, ESLint clean, **731** agent tests (was 635),
**75** infrastructure (was 72), **13** frontend (was 0), secret scan and self-test clean,
production audit 0. AgentCore deployed first (runtime **v4**, `READY`), then `PoolDemoStack`
— both diffs reviewed before applying, and the IAM change is strictly a removal.

One live proof run, fresh workspace `w414eca3df8c044ff`: run `run_c754d9acf69d`,
`pool_created`, `completed`, 7 iterations, Nova Lite, 23,842 in / 516 out, 7,090 ms in
AgentCore and 14,395 ms end to end, tools
`list_latent_demand → evaluate_pool_economics → create_candidate_pool → find_host_candidates
→ request_host_acceptance → issue_final_offer`, producing `pool_b6dfdce9fc19` whose
`created_by_run` matches the run id, confirmed by a consistent read of
`w414eca3df8c044ff#POOL` and by what `/api/state` serves the browser.

Production regression: two-tab first load seeded **once**; two simultaneous resets returned
**409 + 200** across Lambda containers, which is the lease working in the environment it
was written for; workspace isolation held; needs create/edit/re-read and both refusals
behaved; no duplicate pool after a second run; the canonical **$861.44 / $266.32 / 24
units** unchanged on the deployed stack; ten pickups completed with one replay rejected; no
500s; 390 px with zero overflow on every view and zero console errors.

**What the audit was most useful for.** Not the defects — those were findable. It was that
four separate items were the same shape: a **number or a label that had stopped describing
anything**, each with a comment nearby asserting it was accurate. A retry bound nothing
read. A tool kind contradicted by the tool. A concurrency reservation that never existed. A
convergence invariant holding by coincidence. #0030 hit the same shape twice and drew the
same conclusion — "a test that checks the number you remembered to check is not coverage of
the claim" — which is why the fixes here are mostly *mechanisms* rather than edits: a
workspace snapshot around every read tool, a test that fails on any bound nothing enforces,
an endpoint count asserted against the router, and a lint gate that actually runs.

---

### #0032 — [2026-08-18] — Freeze the one-run Product proof before the final visual pass
`[DEMO]` `[ARCHITECTURE]` `[FRONTEND]` `[AGENT]` `[COST]`

**Goal / user intent**
Make the normal Product demonstrate one continuous causal path — standing need to one
live discovery to the resulting pool to same-run proof — while reconciling the Community
impact model, transaction language, dates, architecture and submission narrative. This is
the last structural/presentation patch before a separate visual-polish pass.

**Starting state**
`Find opportunities` already invoked the deployed AgentCore runtime and candidate pools
already stored `created_by_run`, but the Product linked judges to a generic technical
surface whose primary control invited a second paid run. The browser did not expose a
server-verified pool/run relationship. Date-only need values passed through instant/time-zone
parsing, Community architecture was mostly implicit, and several labels blurred
authorization, capture and host payout. The detailed architecture also carried stale route,
bound, tool-effect and EventBridge claims.

**Decision**
Treat the first Product invocation as its own technical proof. The API follows the pool's
stored `created_by_run` to that exact run in the same repository workspace; after a
successful live bridge response and same-workspace run readback, the API adds an
idempotent server-owned AgentCore-origin marker to the existing run record. A missing or
dangling relationship produces no proof. A fresh invocation remains available only in a
collapsed secondary control. No AgentCore runtime code or configuration changed.

The Community addition remains a compact explanation of existing state: verified fixture
memberships, independent need declarers and designated fixture pickup sites, followed by
the narrow responsibility model `Community enables → Pool coordinates → Members choose
and collect`. It explicitly denies institutional partnership, inventory funding, group
creation, money collection and payment chasing.

**Implementation**
Status: **Implemented and Tested; not yet Deployed.** Added the exact pool/run proof
projection, persisted execution-origin evidence, server-backed Community enablement
projection, direct `Pool → Activity → Technical proof for this run` navigation, an honest
AgentCore wait strip, a proof-first evidence card and compact deployed/readback path.
Corrected semantic date-only formatting and judge-visible authorization/capture/host
compensation language. Reconciled `README.md`, the rehearsal script, Devpost draft,
scorecard, release/cost notes and both architecture explanations. The 13-stage lifecycle
reader and canonical domain/economics code were not changed.

**AWS / external services touched**
No AWS resource was touched in this implementation/QA phase. The official Devpost rules,
FAQ, overview and resources were rechecked on 2026-08-18. The next action is deliberately
limited to updating the existing `PoolDemoStack` because only its Lambda/API and bundled
web changed. AgentCore runtime v4 will not be redeployed.

**Cost-relevant activity**
No Bedrock or AgentCore invocation was made. The planned demo-stack update will upload one
new hashed Lambda bundle into the already-ledgered CDK bootstrap bucket and update existing
resources; the infrastructure diff must show no new service or logical resource before it
is applied. After deployment, exactly one Product-originated live AgentCore rehearsal is
authorized in a fresh disposable workspace. No retry run is authorized merely to obtain a
clean result.

**Validation**
`make qa`: ruff clean, ESLint clean, TypeScript clean, **734 agent/API/domain tests**, **75
infrastructure tests**, **20 frontend tests**, production build, and repository secret scan
all passed. `make secret-scan-selftest` passed in an isolated serial run. `npm audit
--omit=dev` reported **0 production vulnerabilities**. `git diff --check` and
`xmllint --noout docs/architecture.svg` passed. Browser inspection of the patched local
Home, Community and disclosure drawer found the new server-derived content and no console
errors. AgentCore validation was not run because no AgentCore entrypoint, package, runtime
configuration or environment configuration changed.

**Failures / dead ends**
The first sandboxed `make qa` reached 734 passing service tests, then CDK's jsii runtime was
denied permission to touch its existing cache timestamp; the identical command passed with
cache access. The first npm audit could not resolve the registry inside the restricted
network and passed once network access was granted. The secret-scanner self-test was
accidentally launched twice against one shared fixture directory, so the overlapping runs
deleted each other's planted files; neither result was accepted. A single serial rerun
passed every planted-secret and cleanup assertion.

**What we learned**
Provenance is a relationship, not a telemetry panel: the useful evidence is the exact
stored pool pointing to the exact stored run, plus a server-owned record of how that run
was invoked. The same distinction applies to Community impact — exposing modeled
boundaries and responsibilities is stronger than claiming adoption the project does not
have.

**Relevant files**
`services/agent/pool/api/app.py`, `apps/web/src/views/live.tsx`,
`apps/web/src/views/pool.tsx`, `apps/web/src/views/community.tsx`, `apps/web/src/api.ts`,
`docs/DEMO_SCRIPT.md`, `docs/architecture.svg`, `docs/ARCHITECTURE.md`, `README.md`.

---

### #0033 — [2026-08-18] — One Product run remains its proof through the completed order
`[DEMO]` `[AWS]` `[AGENT]` `[FRONTEND]` `[COST]`

**Goal / user intent**
Deploy only the presentation patch, rehearse the proposed Product path once in clean
disposable state, and prove that the pool shown at the end still names the exact live run
that created it. Do not record the video and do not spend a second AgentCore invocation.

**Deployment**
Status: **Deployed and Tested.** AWS identity was explicitly verified as the non-root
`pool-admin` user in account `860325090409`, profile `pool-dev`, region `us-east-1`.
The strict CDK diff contained one existing `AWS::Lambda::Function` code-asset update and a
stack-description character correction; no resource, IAM permission or service was added
or removed. `PoolDemoStack` reached `UPDATE_COMPLETE`. AgentCore runtime v4 was not
redeployed because its entrypoint and configuration did not change.

The rehearsal exposed one stored activity sentence whose bare “Captured” wording relied
on the drawer to disclose the simulated provider. The service now records “Simulated
capture recorded”, the feed derives the same explicit kind label from authoritative
`provider_mode`, and lock activity says simulated capture is beginning. Two focused Python
tests plus frontend test/lint/typecheck passed, then the same code-only Lambda diff was
reviewed and deployed. The live discovery was **not** rerun.

**Live rehearsal evidence**
The existing disposable browser workspace was reset through the Product control before
the rehearsal, leaving a clean seed with zero pools. Workspace:
`w0z2b3v2r6c3b0q6l`.

- The Rosa whey declaration was changed from 20% to 21%, saved and read back. The need
  card and form both showed **Aug 29**; the calendar date did not shift by timezone.
- `Find opportunities` was clicked **exactly once**. The honest wait named Amazon Bedrock
  AgentCore and this session's DynamoDB workspace without staged progress.
- Live run `run_3954c1d2d97f`: `pool_created`, termination `completed`, 6 iterations,
  Bedrock / `us.amazon.nova-lite-v1:0`, 6,382 ms inside the runtime, 14,282 ms measured by
  the Lambda bridge, 19,515 input / 493 output tokens.
- Exact tool sequence: `list_latent_demand → evaluate_pool_economics →
  create_candidate_pool → find_host_candidates → request_host_acceptance`.
- Resulting pool `pool_e36b32c84ee2`. A strongly consistent DynamoDB read returned
  `created_by_run = run_3954c1d2d97f`, status `completed`, threshold 24. The run row carries
  the server-owned note `execution_origin=bedrock_agentcore_runtime:us-east-1`.
- The Product proof showed the same run id twice (run and `created_by_run`), the same pool
  id, live service/region/model, exact tools, `run + pool present in the same workspace`,
  and a verified run→pool link. It survived recovery, completion, a Lambda redeploy and a
  browser reload. Home deep-linked back to this exact proof. `Run again` remained collapsed
  and was never opened.
- Canonical transaction state remained unchanged: **10 buyers / 11 memberships**, one
  retained declined authorization, **24/24 units**, two cases of 12, zero speculative
  surplus, **$861.44 all-in**, **$1,127.76 retail**, **$266.32 collective savings**, and
  **10/10 handoffs**. Host compensation was $44.68, recorded in a simulated transaction;
  no payout rail was claimed.
- Drawer disclosures were correct: live AgentCore/Bedrock discovery, deterministic
  lifecycle, simulated payments and supplier purchase. The Community close showed all
  server-backed enablement counts, the responsibility split and no partnership claim.
- Browser console errors: **0** throughout. Every Product/drawer action returned and the
  completed state reloaded successfully.

The browser-controlled journey from Needs to the Community close took about **3 minutes
36 seconds including deliberate inspection pauses and screenshots**. The live response was
visible about 17 seconds after the click. No unexplained backtracking was required; the
drawer was used at the two planned lifecycle moments, recovery was clearest on People, and
the proof card held both ids together so no id had to be remembered from an earlier screen.
The planned ~4:50 narrated path remains feasible. Typography, responsive polish and denser
proof-card legibility are explicitly handed to the next `/impeccable` pass rather than
changing structure here.

**Cost and resource reconciliation**
Exactly **one** paid AgentCore/Nova invocation was made. No schedule was created or run.
The post-deploy account-wide EventBridge rule count is **0**. The one existing
`Pool_PoolCoordinator` runtime remains `READY` and incurs usage only when invoked. The
existing demo stack still contains the same nine logical resources. Two reviewed Lambda
uploads were needed because the rehearsal found the copy defect; both produced hashed
objects in the already-ledgered bootstrap bucket. That bucket now measures **36 objects,
544,983,237 bytes**; the live resource ledger was updated. No temporary AWS resource is
unrecorded.

**Final validation**
`make qa` on the final code: ruff clean, ESLint clean, TypeScript clean, **734
agent/API/domain tests**, **75 infrastructure tests**, **20 frontend tests**, production
build, and secret scan all passed — **829 tests total**. The serial secret-scanner
self-test passed, `npm audit --omit=dev` reported 0 production vulnerabilities,
`git diff --check` and the SVG XML check passed. AgentCore validation was not owed because
no runtime code or configuration changed.

**Relevant evidence / files**
`docs/IMPECCABLE_HANDOFF.md`, `docs/DEMO_SCRIPT.md`, `docs/RELEASE_CHECKLIST.md`,
`services/agent/pool/api/app.py`, `services/agent/pool/services/payments.py`,
`services/agent/pool/services/coordination.py`, `apps/web/src/views/live.tsx`,
`apps/web/src/views/community.tsx`.

---

### #0034 — [2026-08-18] — Make the proof scan like software without removing the proof
`[DEMO]` `[FRONTEND]` `[AGENT]`

**Goal / user intent**
Audit the Product and Showcase copy after the structural pass, then reduce reading effort
without changing the information architecture, product semantics, Product/Showcase roles,
demo path, same-run proof, thirteen-stage reader or real/synthetic/simulated boundaries.

**Starting state**
The correct information was present, but many Product views explained what their controls,
figures and records already showed. Activity placed its strongest same-run evidence after a
long event feed. The technical page mixed primary causal proof with secondary architecture,
tool-catalogue and invocation detail, while the lifecycle reader repeated editorial explanation
beside already-complete figures and stored stage summaries.

**Decision**
Keep status, actions, numbers and truth boundaries visible; compress explanatory prose; turn
supporting mechanics into native disclosure; and lead Activity with the exact stored relationship
and execution chain. The thirteen server-recorded stage summaries and every stage destination
remain intact. This is hierarchy and copy work only, not a visual-system or component redesign.

**Implementation**
Status: **Implemented and Tested; not Deployed.** Product introductions, empty states and
contextual explanations were shortened across Home, Pools, Needs, Community and the pool tabs.
Community responsibilities, viability details, host-candidate ranking, credential mechanics,
fee rationale and secondary run traces remain available in disclosures. The Product Activity
overview now leads with run id, pool id, `created_by_run` equality, authoritative same-workspace
readback, AgentCore live status, exact tool sequence and the complete browser-to-browser causal
chain. The technical view gives the same evidence priority while disclosing hop detail, bounds,
tool catalogue, run history and deployment tiers. Showcase Overview, drawer and Operations copy
was compressed without weakening synthetic, simulated, payment, purchase or payout language.
All thirteen lifecycle stages remain navigable; deterministic figures and server-recorded stage
summaries stay visible, while supporting explanation is progressively disclosed.

**AWS / external services touched**
None. No AWS resource was read, changed, created or destroyed, and no AgentCore or Bedrock run was
invoked.

**Cost-relevant activity**
None. Local fixture tests and a local frontend production build only; no schedules or paid tools.

**Validation**
Frontend Vitest passed **22 tests in 8 files**, including new assertions for proof priority and
all 13 lifecycle destinations. ESLint, TypeScript typecheck, Vite production build and
`git diff --check` passed. Route wiring in `App.tsx` and the Product/Showcase navigation constants
were inspected and are unchanged. Existing responsive rules were inspected for the 1512×804 and
approximately 390px layouts: grids collapse below 940px, facts use wrapping minimum columns,
long ids wrap, and mobile panel padding and lifecycle height rules remain in force. Actual rendered
browser inspection at those viewports was **not completed in-session**: the in-app browser rejected
both the local and deployed origins under its navigation policy, and the local API bind escalation
was unavailable due the approval service's usage limit. No alternate browser was used to bypass
that policy.

**Update — 2026-08-18.** The human owner launched the full local stack (`services/agent` API on
:8000, `apps/web` Vite dev server on :5173) outside this session's browser restriction and
manually inspected the modified Product and Showcase views. Hierarchy, disclosures, density and
layout received manual visual sign-off. The viewport-inspection gap noted above is resolved by
that sign-off; no further screenshot capture is pending.

**Failures / dead ends**
The first local API start could not bind inside the sandbox. The required escalation was rejected
because the approval service had reached its usage limit. The in-app browser then rejected both
the local Vite origin and deployed origin, so visual viewport QA and a click-through demo rehearsal
could not be claimed. An initial Vitest invocation included a Jest-only `--runInBand` option; the
normal repository test command was used instead and passed.

**What we learned**
Technical proof becomes easier to trust when its causal keys and equality checks are the visual
entry point. Progressive disclosure is safest for explanation and catalogues, not for identities,
outcomes, financial state or truth boundaries.

**Evidence worth preserving**
Manual visual sign-off (2026-08-18) covered Home, Pools, Needs, Community, a pool's Activity tab
and technical proof, and the Showcase 13-stage run at desktop and mobile widths. No screenshot
artifact was captured during that session; a future pass may still want one for the written record,
but it is not blocking.

**Relevant files**
`apps/web/src/views/home.tsx`, `apps/web/src/views/pools.tsx`,
`apps/web/src/views/needs.tsx`, `apps/web/src/views/community.tsx`,
`apps/web/src/views/pool.tsx`, `apps/web/src/views/about.tsx`,
`apps/web/src/views/run.tsx`, `apps/web/src/views/live.tsx`,
`apps/web/src/views/operations.tsx`, `apps/web/src/views/demo-panel.tsx` and their focused tests.

---

### #0035 — [2026-08-18] — The visual-polish pass, and one identity bug it surfaced
`[DEMO]` `[FRONTEND]` `[ARCHITECTURE]`

**Goal / user intent**
Run the final visual, responsive, interaction and accessibility pass over the frontend before
presentation work, against the frozen scope in `docs/IMPECCABLE_HANDOFF.md`. No product,
information-architecture, demo-choreography or proof-semantics changes.

**Starting state**
Entry #0034 left the Product and Showcase copy compressed and the proof evidence prioritised, but
that pass could not complete rendered browser QA in-session and relied on the owner's manual visual
sign-off afterwards. The design system itself had not been audited: disclosure affordances,
disabled states, focus behaviour, heading structure and touch targets were whatever each view had
reached for locally.

**Decision**
Fix causes at the system level rather than per view, and treat the technical proof's central claim
as a layout problem rather than a copy problem.

**Why**
Three of the worst defects were one defect each, repeated. Every `<summary>` styled as a flex row
(`.panel-head`) silently suppressed the native disclosure marker, so five panels that open looked
exactly like panels that do not. Disabled controls were a 45% opacity ghost of the enabled control,
which fails both legibility and inertness at once and fails worst on a recorded screen. Every view
jumped `h1 → h3`, and Showcase's run reader began at `h2` with no `h1` above it.

The proof card's central claim — the pool carries the id of the run that created it — was four
sibling cells in an auto-fit grid, with the equality asserted in a trailing text fragment
(`· matches run id`). Two identifiers being *equal* is not something a flat grid can show. Setting
them as a ledger, on consecutive rows, in the same column, makes the match visible rather than
readable. No evidence was removed to achieve it.

**Implementation**
Status: **tested**. Deployment is recorded in a separate update below, once observed.

Shared primitives: `ProofIdentity` and `ExecutionPath` in `ui.tsx`, now the single source for the
proof block in both Product's compact Activity card and the full technical view — the two had been
independent copies of the same markup. `Block` gained an explicit heading level. `TracePills` gained
an ordered form, because the order *is* the evidence.

Design system: one disclosure grammar (drawn rotating chevron, hover on the whole header); disabled
as a flat unlit surface with a legible label, with the primary action keeping its shape while a run
is in flight; focus rings drawn inside controls that sit in horizontal scroll rails, where an offset
ring was being clipped; `.token`, `.push`, `.grid-lede`, `.facts-wide`, `.figure-tail` and the
`.provenance` block, the last sized by container query so it re-flows from the width it is given
rather than the viewport.

Accessibility: corrected heading outline across all views; real tab semantics on the pool record
(`aria-controls`, `role="tabpanel"`, roving tab order, arrow-key navigation); the demo drawer became
a true modal (`aria-modal`, focus in on open, Tab held inside, focus restored to the opener);
`role="status"` on action outcomes; the Operations one-time-code input moved from `.btn` to
`.control`. The pool tab strip now scrolls its selected tab into view — entering the record directly
on Activity left the tab, and the proof behind it, invisible on a phone.

**One semantic defect fixed, deliberately and separately.** Home's opportunity card and its
"technical proof for this run" action arrived at their pool independently: the card rendered
`state.pools[0]`, and `App.tsx` looked up `state.pools[0]` again inside the handler. In the
canonical single-pool scenario they always agree, which is exactly what makes it worth fixing — the
failure only appears once a second pool exists, and by then it is a judge being shown the wrong
run. The card now emits the id of the pool it drew and the handler opens that pool.

**AWS / external services touched**
None. No AWS resource was read, changed, created or destroyed during the pass. The local API ran
offline with the deterministic planner; no AgentCore or Bedrock run was invoked.

**Cost-relevant activity**
None during the pass. No schedules, no paid tools, no model calls.

**Validation**
`make qa` passed in full: Python ruff, ESLint, TypeScript, Python tests, frontend Vitest
**23 tests in 9 files**, Vite production build, secret scan. `git diff --check` clean.

Rendered browser QA was completed this session, closing the gap #0034 recorded. Inspected at
1512×804, 1920×1080, 1024×1366 and 390px, plus a dark-scheme pass: Home (empty and with a pool),
Pools, Needs including the open form, Community, all five pool tabs, Activity → technical proof in
both compact and full form, the 13-stage reader at stages 1, 8 and 13, the demo drawer, and all five
Showcase destinations. Measured across those screens: no contrast failure below 4.5:1 / 3:1, no
body-level horizontal overflow, no element overflowing the viewport. Console clean on a fresh tab
after a full traversal; all `/api/*` requests 200.

The proof-link fix has a focused regression test (`apps/web/src/views/home.test.tsx`) using a
two-pool fixture. It was confirmed to **fail against the previous code** before being accepted —
the old handler received a React synthetic event rather than a pool id.

**Failures / dead ends**
Three Vitest failures appeared mid-pass. Two were changes to strings the tests correctly guard —
the readback separator and the stage counter — and were reverted to the asserted wording rather
than having the tests edited around them. The third was real: `scrollIntoView` is absent under
jsdom and was crashing `PoolRecord`; the call is now guarded. Bolding the current stage index split
`01 / 13` across elements for no proportionate gain, so the emphasis moved to CSS instead. An
attempt to name the current act in the stage bar was reverted — it duplicated the act label twenty
pixels below it.

**What we learned**
A design system's worst defects are usually one defect repeated. The disclosure markers, the
disabled state and the heading levels were each a single rule, and each was wrong in every view at
once. Separately: an identity bug that is invisible in the canonical scenario is not a small bug —
it is a bug that will first appear in front of an audience.

**Article fodder**
Article 2 and the demo. The provenance block is the clearest artifact of the project's central
technical claim: same-run proof shown as alignment rather than asserted as prose.

**Evidence worth preserving**
Before/after of the technical proof card — a flat four-cell fact grid versus the aligned provenance
ledger with the two identical run ids stacked, the `matches run id` chip, and the checked
authoritative readback verdict.

**Relevant commits / files**
`apps/web/src/styles.css`, `apps/web/src/ui.tsx`, `apps/web/src/App.tsx` and every view under
`apps/web/src/views/`, plus the new `apps/web/src/views/home.test.tsx`.

**Update — 2026-08-18, deployment blocked on credentials.** The commit is pushed to `origin/main`,
but `make deploy-demo` was **not run**: the `pool-dev` profile's session has expired
(`aws login` reauthentication is an interactive flow belonging to the human owner, not to a coding
agent). Nothing was deployed, and the public demo is still serving the previous build. This entry's
implementation status therefore remains **tested**, not deployed.

What *was* verified is the artifact the deploy would have shipped. `scripts/build_demo_bundle.sh`
produced the Lambda bundle (70 MB unzipped, import check and credential scan clean), and the built
web app was then served by the same FastAPI app in the same public-demo mode the Lambda uses, on a
local port. Against that production bundle — not the Vite dev server — the canonical path was
walked: `Find opportunities`, the resulting pool's Activity → technical proof, the full 13-stage
lifecycle to stage 13, the Needs form, the demo drawer, Product ↔ Showcase in both directions and
all five Showcase destinations, at 1512px and 390px. No console errors, every `/api/*` response 200,
no horizontal overflow on any screen, and the tab strip scrolled its selected tab into view on the
phone width. The only sub-24px controls are the two inline prose links in the footer.

The proof-link fix was exercised end to end in that bundle: the pool the card drew
(`pool_1612a42cf6d6`) is the pool whose proof opened, carrying `run_6d02f8fa0250`.

No AgentCore or Bedrock run was invoked at any point. The two POSTs involved — `/api/agent/run` and
`/api/demo/scenario` — are the offline bounded coordinator and the deterministic lifecycle; neither
spends model tokens.

**Update — 2026-08-18, deployed.** AWS authentication was refreshed and `make deploy-demo` ran from
a clean tree at `719585a`. `PoolDemoStack` reached `UPDATE_COMPLETE` in 16.9s, updating only the
`DemoApi` Lambda — no new AWS resource, so the ledger is unchanged. The bundle live at the demo URL
is the reviewed commit, confirmed by asset hash: production moved from `index-C4sU9Sjx.js` to
`index-DO-itO5M.js`, the hash the deploy's own rebuild reproduced from the committed tree. The stack
shipped with `LiveAgentAction` set to the `Pool_PoolCoordinator-TmVqSN9H56` runtime, so the live
path is enabled rather than silently off. **This entry's implementation status is now deployed.**

The live AgentCore proof was rendered in production for the first time, from **one** paid run
(`run_df149d669b95`, `pool_b4393b23ade9`, 7 iterations, 23642/478 tokens, 7070 ms inside the agent,
14456 ms inside AWS): the live chip, the two matching run ids aligned in the provenance ledger, the
verified same-workspace readback, the six-tool sequence, the `browser → Lambda → AgentCore →
Bedrock / Strands → typed tools → DynamoDB → browser` path, and the live invocation details with the
real tool trace. Product, Needs, the pool record, both Showcase directions, the 13-stage reader, the
demo drawer and the 390px layout were smoke-tested against production with no application console or
network errors.

---

### #0036 — [2026-08-18] — A demo-first audit, and the three of its own findings it reversed
`[DEMO]` `[FRONTEND]`

**Goal / user intent**
Work backward from one question — *if you had five minutes with the AWS judges, what would you
actually show?* — then implement whatever survived a second, adversarial pass over the audit's own
recommendations. Explicitly not another visual-polish pass, and explicitly not permission to
implement a recommendation merely because it had been written down.

**Starting state**
Entries #0032–#0035 left the Product structurally correct, the same-run proof strong and the visual
system finished. What none of them had examined is whether a *member* can see what Pool did for
them. Four things the audit found by driving a full local lifecycle in a browser:

1. Home's card was headed **"Your order"** and contained only community-level facts — ten members,
   twenty-four units. Rosa's own two tubs, her $71.83, her saving and her pickup window appeared
   nowhere on her own home screen.
2. The decision card explained the autonomy boundary as *"your rule `autonomy_mode` did not
   pass"*, rendering an identifier, while `facts.policy_checks` already carried the policy engine's
   own sentence: *"member is on Ask Me — commitment requires explicit approval."*
3. **"What Pool may decide for you"** listed four limits and omitted `autonomy_display.mode`, the
   master switch that decides whether any of them are ever consulted. The panel therefore implied
   Pool could act, one screen before Pool asked.
4. `coordination_actions_automated` / `human_decisions_requested` / `commitments_without_asking` —
   18 / 3 / 8 on the canonical run, and the single best evidence that an agent absorbed human
   coordination — existed only ~2,200 px down the Community page, in the second column of a
   two-column ledger.

Two further defects surfaced while implementing: the Fulfilment tab offered *"Issue Chidi A.'s
code"* to a signed-in Rosa, and `pct()` in the client rounded basis points while
`bps_to_pct_str()` on the server truncated them, so one purchase read 23.6% and 23.5% six lines
apart once the member's own figure was surfaced next to the decision's.

**Decision**
Recompose Home as a state-driven narrative — *what Pool needs from me → what it found for me →
what it handled on its own → what I buy anyway → what it may decide for me* — with every section
appearing only when it has something to say. Fix the four findings above at the source rather than
by adding explanation. Reorder Community so both currencies (money created, coordination avoided)
occupy the first viewport. Move the three authorisation constraints in the need form behind one
disclosure that states their values, leaving the four intent fields primary. Reuse existing server
values throughout; add no derived figure to React.

Three of the audit's own recommendations were reversed on revalidation, and the reasoning matters
more than the changes:

- **A backend `estimated_savings` field on the pool view was dropped.** The audit wanted it because
  the live AgentCore run leaves a pool at `host_recruiting`, where `_pool_view` reads only
  `final_economics` and the payoff frame renders a dash. Implementing the member-scoped card showed
  the estimate was *already* exposed per membership as `estimated_cost_cents` / `baseline_cents`,
  written at pool creation. The card now reads **"Your 2 tubs · about $71.93 instead of $93.98"**
  with the tail saying **"Not final yet — a fulfiller's pay is part of the price."** No new
  derivation, no second source of truth for a savings figure, and a better frame: the reason the
  price is not final teaches the host-before-authorization invariant instead of hiding behind it.
- **The 8-hop `HopChain` was not moved onto Home, and its in-flight spinner was removed instead.**
  The audit proposed reusing it during the ~17 s live wait. Rendered, it put eight AWS service names
  on a consumer screen, and it spun every unobserved hop while the panel's own caption said *"no
  intermediate stage is being inferred."* A browser making one HTTPS request cannot observe that any
  hop is executing — not even the first, which can still fail at DNS or TLS. The Product wait is now
  three rows: the send (resolved), the destination named but not claimed, and the answer; plus the
  region, the runtime and a real elapsed clock. On the technical view no hop is ever marked active.
- **The global typography change was dropped.** The audit flagged 90 uses of 12 px `.tiny`, 43 of
  them `.faint`, from reading the CSS. Measured in the browser, `--ink-faint` on `--paper` is
  **5.09:1**, comfortably past WCAG AA for normal text. The targeted fix was enough: Home now
  contains **zero** `.tiny`, having moved its captions to `.small`.

**Showcase was inspected and deliberately left untouched.** It duplicates the navigation and adds no
unique content, which is what the audit objected to — but the video never enters it, the drawer
gates it behind an explicit mode switch with a visible exit, and it genuinely serves a judge who
would rather be walked through Pool than use it. Restructuring `App.tsx` routing is the
highest-regression-risk change available for zero demo gain, so it was not made.

**Implementation**
Status: **Implemented and Tested; not Deployed.** Frontend composition only; no domain, agent,
tool, viability, economics, IAM, CDK or AgentCore change, and no new API field.

- `views/home.tsx` rewritten. Member-scoped opportunity card (own units, own price against own
  baseline, own saving, pickup window), estimate labelled *about* with the invariant in the tail,
  state-dependent heading, `failure_reason` surfaced where the member is. One community block
  replaces the previous two, leading with what Pool did on its own and stating the premise —
  *members · standing needs · groups anyone organised: 0* — before anything has run. The autonomy
  disclosure leads with the mode in a member's words and collapses the limits. The last-run
  `<details>` was deleted; it duplicated the pool record's proof card at L5 depth on an L1 screen.
- `labels.ts` gained `blockingRuleExplanation()` (returns the matching `policy_checks[].detail`
  verbatim, empty rather than invented) and `autonomyModeCopy()`.
- `ui.tsx` gained the shared `Elapsed` and a rewritten `CoordinatorWait`; `views/live.tsx` now
  imports `Elapsed` rather than keeping a second copy.
- `views/community.tsx` reordered to money → attention → enablement → pools/map → decisions →
  money ledger → feed → operations, with the attention ledger promoted from half a column to a
  full-width section of three figures.
- `views/needs.tsx` moved minimum saving, spend ceiling and substitution behind one disclosure whose
  summary states both numeric values. Defaults in `blankDraft` are byte-for-byte unchanged.
- `views/pool.tsx` `FulfilmentTab` now prefers the signed-in identity for a pickup credential
  (*"Show my code"*), falling back to naming the subject for anyone not in the pool.
- `api.ts` `pct()` now truncates the tenth digit exactly as `bps_to_pct_str` does.
- `brand.tsx` convergence caption reduced to one sentence with the arithmetic behind a disclosure.
- `docs/DEMO_SCRIPT.md` rewritten to ~4:45 for the new surfaces. The rehearsal now edits the
  days-early window rather than the savings floor — same proof that the run answers current stored
  state, but it edits the primary field the coordinator actually consults minutes later — and it
  **holds** the live wait rather than cutting it, because the wait is now evidence.

**AWS / external services touched**
None. No AWS resource was read, changed, created or destroyed. No AgentCore or Bedrock invocation
was made; the deployed `GET /api/demo/config` and `/api/health` were read once each, which are
unauthenticated reads that spend nothing. A second local server was started on :8011 with a
deliberately invalid runtime ARN so the live wait could be rendered, and the browser stubbed
`POST /api/demo/agentcore` to a never-resolving promise so no request left the page.

**Cost-relevant activity**
None. Local fixture runs, local builds, and one local judge-mode server.

**Validation**
`make qa` green: ruff clean, ESLint clean, TypeScript clean, **734** agent/API/domain tests, **75**
infrastructure tests, **48** frontend tests (was 20), production build, secret scan clean.
`git diff --check` clean. Rendered browser QA was completed in-session this time, at 1512×804 and
390px, across passive, running, opportunity, approval, active, distributing, completed and failed
Home states, the Needs form open and its disclosure expanded, all five pool tabs, the technical
proof, Community, Operations, Showcase Overview and Showcase Live on AWS: zero console errors, all
network responses 200, no horizontal overflow at 390px. Home's busiest state fell from seven
sections to five (1,668 px); passive Home is 1,321 px.

Twenty-eight frontend tests were added, pinning the claims rather than the layout: that no hop
resolves below the request the browser sent and none is marked active in flight or after a failure;
that the wait names AgentCore and the region without claiming to watch the request arrive; that Home
reports `state.metrics` unmodified and states the premise rather than a row of zeroes; that the card
leads with the signed-in member's own allocation and shows nobody else's; that a pre-final pool says
which invariant is holding instead of showing a dash; that the decision card renders the policy
check's sentence and never the rule identifier; that the autonomy panel leads with the mode; that
the credential belongs to the signed-in member; that the need form's collapsed constraints are still
present and still send their original values; that Community places both currencies above the model
that explains them; and that `pct()` agrees with `bps_to_pct_str`.

**Failures / dead ends**
The first implementation of the member-scoped card produced a visible contradiction — *"Your 2 tubs
· $71.93"* directly above *"Not priced yet"* — because it surfaced `estimated_cost_display` while
the tail still assumed no price existed. That contradiction is what made the dropped backend field
unnecessary: the fix was to label the estimate and let the tail carry the reason it is not final.
Separately, the autonomy disclosure initially reused `.section-title` for its summary and rendered a
seventy-character sentence in 13 px uppercase; it now uses a short uppercase label beside the answer
in ordinary case.

**Relevant evidence / files**
`apps/web/src/views/home.tsx`, `apps/web/src/views/community.tsx`, `apps/web/src/views/needs.tsx`,
`apps/web/src/views/pool.tsx`, `apps/web/src/views/live.tsx`, `apps/web/src/ui.tsx`,
`apps/web/src/labels.ts`, `apps/web/src/api.ts`, `apps/web/src/brand.tsx`,
`apps/web/src/styles.css`, `apps/web/src/App.tsx`, `apps/web/src/ui.test.tsx`,
`docs/DEMO_SCRIPT.md`, `README.md`.

---

### #0037 — [2026-08-19] — A real product catalogue, and the boundary that keeps it honest
`[PRODUCT]` `[FRONTEND]` `[DOMAIN]` `[DATA]` `[LICENSING]`

**Goal / user intent**
Fix the actual first-use experience. A cold visitor could open Pool, see "24 members
declared 33 standing needs" above a button marked *Find opportunities*, and have no idea
what they were supposed to do. The one thing the product asks of a person — say what you
buy — was a `<select>` over six invented products (Northfield, Voltside, Clearwash).

**Starting state**
`Product` / `Offer` / `substitution` / `economics` were well-separated and heavily tested.
The missing piece was narrow and specific: **no layer existed between free text and a
`product_id`.** Two earlier passes established this (`docs/CATALOG_RESEARCH.md`); this
entry is the implementation.

**Decision**
Add a consumer identity + resolution layer *above* `product_id`, and change nothing
beneath it. Concretely:

- A curated 294-product snapshot of Open Food Facts (plus Open Beauty/Products Facts),
  committed as `pool/data/catalog.json` with 289 committed images.
- Search is SQLite-free: an in-process pure function over that snapshot, ranked
  deterministically. No index server, no vector store, no model call.
- `Product` gained optional identity fields (`gtin`, `image_ref`, `synonyms`,
  `display_size`, `source`, …). `from_dict` already defaulted every non-core field, so
  **zero data migration** was required.
- Rosa's flagship whey declaration was removed from the seed. She makes it herself — in
  the form, or in the scripted showcase, both through the real `declare_need` service.

**Why**
Three findings from the research drove every one of those choices.

*The API cannot be a dependency.* Open Food Facts documents 10 searches/min and warns
against using search for autocomplete. In practice it returned **HTTP 503 repeatedly at
~8.5 req/min** while this catalogue was being built — the build script needed exponential
backoff and five retries to get through some categories. A demo whose first interaction
depends on that breaks in front of judges. Hence: bundled snapshot, and a test that
asserts search makes no socket call.

*Identity is not structure.* Sampling US protein powders returned package sizes of
`"43.2 oz ("`, `""`, `"80 x 31g"`, `"I tablesp"` and `"30.5 g"` (a serving, not a package)
— seven formats in eight records. The real US Gold Standard barcode returns a correct
name, brand and photograph with **no quantity at all**. Pool's economics live entirely in
package structure, so the catalogue supplies identity and nothing else; `display_size` is
a string for humans and nothing multiplies it.

*Household goods have no open catalogue.* Probing Open Products Facts for US rows
returned **0 laundry detergents, 0 toilet papers, 1 paper towel**. Those five products are
curated by hand and carry no brand — inventing one would put a fictional brand beside two
hundred real ones. They render with the category fallback tile, which is also how that
path gets exercised for real rather than only in a test.

**Implementation** — implemented and tested.

- `scripts/build_catalog.py` — the offline builder. Cached, resumable, backoff-aware.
- `pool/data/catalog.py` — load, rank, materialise. Four `lru_cache`s and a `reset_cache`.
- `pool/data/catalog.json` + `apps/web/src/assets/products/*.jpg` (294 rows, 289 images,
  2.6 MB) + `pool/data/CATALOG_LICENSE.md`.
- `GET /api/products/search`, `POST /api/products/custom`; both added to the public
  allowlist (counts moved 40→42 total, 24→26 public).
- `apps/web/src/product-search.tsx`, `products.ts`; Needs rebuilt as product-first;
  Home leads with the member's action instead of the coordinator's.
- `services/demo.py: declare_flagship_need()` — idempotent, shared with
  `scripts/recovery_scenario.py`.

**AWS / external services touched**
None at runtime. The build script fetched Open Food Facts from a laptop, once.

**Cost-relevant activity**
$0. No Bedrock, no AgentCore, no deployment. The catalogue costs nothing to serve because
it is a file, and search costs nothing because it is a function.

**Validation**
- 770 Python tests pass (was 734; +36, of which 32 are the new `test_catalog.py`).
- 57 web tests pass (was 48).
- `make qa` green: lint, typecheck, both suites, production build, secret scan.
- Canonical end state re-audited directly from `run_showcase`: **10 buyers, 11 membership
  rows, 1 `authorization_failed` retained for audit, 1 exact replacement, 24 funded units,
  24 purchased, 2 cases, $756.00, no surplus.** Unchanged.
- Determinism: five full scenario runs with a fresh random `need_id` each time produce one
  distinct outcome signature.
- Visual QA at 1512×804 and 390×844: search, selection, save, no-result, completed pool.
  Zero console errors; **every network request is same-origin**.

**Failures / dead ends**
- First pinned `0748927028669` as the vanilla whey. It is Double Rich Chocolate. Caught by
  looking the barcode up rather than trusting the guess; the vanilla product with a usable
  photograph turned out to be a different SKU entirely.
- Wrote a `_JUNK` regex containing literal control characters, which made the build script
  unparseable ("source code cannot contain null bytes").
- The first `ProductCard` put the click handler on a `<button>` nested inside
  `role="option"`. Invalid ARIA, and the tests caught it as a real bug: clicking the option
  did nothing.
- `test_catalog.py` cleared three of the module's four caches, so the missing-file test
  silently poisoned every later search assertion. Fixed by giving the module a
  `reset_cache()` that knows about all four.
- Vite inlined 12 sub-4 kB product images as `data:` URIs, which quietly falsified the CSP
  comment claiming `data:` existed "for exactly one thing: the inline SVG favicon". Set
  `assetsInlineLimit: 0` rather than let a security comment drift — and the bundle got
  smaller anyway (368 K → 312 K; 137 K → 94 K gzipped).

**What we learned**
The sharpest lesson is the barcode one. Pool holds a *synthetic* quote for the six seeded
products — a 5 lb tub, twelve to a case. The Open Food Facts record whose photograph makes
the product recognisable is a specific retail SKU, and the vanilla one is a 24.05 oz tub.
Publishing that barcode beside an invented case structure would assert a correspondence
that does not exist, and a barcode is exactly the field a careful judge would check. So
the rule became: **a product Pool quotes a synthetic price for is identified at the level
that is true — brand, product line, flavour, photograph — and claims no SKU.** Catalogue
products Pool has no offer for carry their full identity, barcode included, because
nothing there can contradict them.

Second lesson: making the product feel real made the truth boundary *sharper*, not
blurrier. "Synthetic community and catalogue" was adequate when everything was invented.
With Optimum Nutrition on screen it is not, and About now says which specific things are
invented — every supplier price, case size and minimum — and that no manufacturer has any
involvement.

**Article fodder**
Article 1 and the demo. The demo opening is now a causal chain a judge can watch rather
than a dashboard they have to be talked through: *she types two words → recognises a tub →
taps it → answers two questions → Pool finds seven strangers who need the same thing.*
Also good Article 2 material on where a model belongs and where it does not: there is no
LLM anywhere on the search path, and the reasons are cost, latency, determinism, and the
fact that an LLM one step from choosing somebody's product is an LLM one step from
choosing whose purchases are interchangeable.

**Evidence worth preserving**
The seven-formats-in-eight-records package-size sample; the 503s under documented rate
limits; the 0/0/1 household coverage probe; before/after of the Home first-use screen.

**Relevant commits / files**
`scripts/build_catalog.py` · `services/agent/pool/data/{catalog.py,catalog.json,seed.py,CATALOG_LICENSE.md}` ·
`services/agent/pool/domain/models.py` · `services/agent/pool/services/{needs.py,demo.py}` ·
`services/agent/pool/api/{app.py,public_demo.py}` · `apps/web/src/{product-search.tsx,products.ts,api.ts}` ·
`apps/web/src/views/{home.tsx,needs.tsx,about.tsx}` · `services/agent/tests/test_catalog.py`

---

### #0038 — [2026-08-19] — Whose account is this?
`[PRODUCT]` `[FRONTEND]` `[DOMAIN]` `[IDENTITY]` `[PRIVACY]`

**Goal / user intent**
The last consumer-entry problem. A visitor opened Pool and was silently cast as a seeded
student: greeted as "Rosa N.", holding a card they never added, apparently buying paper
towels they had never mentioned, with a dropdown of twenty-four invented people presented
as the account model. Fine as operator scaffolding; wrong as a product. It also undercut
the sentence the whole project rests on — *I tell Pool what I buy and Pool does the rest*
— because it was never clear who "I" was.

**Starting state**
`#0037` had fixed *what* a member declares. This fixes *who* is declaring it.
`DEFAULT_IDENTITY = { id: "hh_navarro", display_name: "Rosa N." }` was a constant compiled
into `App.tsx`.

**Decision**
Four setup screens — who you are, where you are, what you buy, how much Pool may do — and
a hard separation between the consumer and the operator's ability to act for synthetic
participants.

Underneath, deliberately small: exactly one household per workspace is *the consumer*, and
onboarding writes a display name, an autonomy mode, a saved payment method and a
completion timestamp onto it. The household **id never changes**, because matching,
economics, case fitting and every asserted figure key off it.

**Why**

*Identity.* `display_name` was already presentational — grep proved it appears only in
serializers and messages — so renaming the consumer's household is the whole mechanism. No
new entity, no second source of truth, no auth system. That claim is now measured rather
than argued: `test_the_display_name_cannot_change_a_single_number` runs the entire
scenario with a name applied and compares every membership, every per-buyer cent and the
complete economics against a run without one.

*Location — the interesting one.* The obvious build is "Share my location". It was
rejected, and not for effort. The deployed `Permissions-Policy` denies geolocation
outright and this pass leaves that alone. The demo's community is an invented campus at
invented coordinates, and a judge could be in any city; taking a real position and
treating it as a room on that campus would be a lie about the exact thing location is
*for*, while taking one only to discard it would be collecting a sensitive value for
nothing. There is also a margin problem: the consumer sits 1.1 km from the pickup site the
coordinator chooses, against a 1.6 km formation radius, so a location control that moved
their coordinates could silently drop them out of their own pool.

So the step asks the real question and collects nothing. It names the local network, shows
what being in it is worth in real numbers off the server, and says plainly: *Pool has not
asked your browser for your location and has not tried to guess it.* It is impossible to
lie about a coordinate you never took, and the screen works identically from anywhere.

*Payment, decided by measurement not preference.* The plan allowed deferring it. Removing
the consumer's seeded card and running the scenario settled it: a member who reaches a
final offer without a saved method becomes a **second** authorisation failure — twelve
membership rows instead of eleven — quietly breaking the reconciliation the recovery story
rests on. So payment belongs in setup, sharing the autonomy screen because "may Pool spend
without asking" and "here is the money" are one question.

**Implementation** — implemented and tested.
- `Household.onboarded_at` (additive; `from_dict` already defaulted, so no migration).
- `pool/services/onboarding.py` — `consumer_view`, `describe_place`, `complete_onboarding`.
- `POST /api/onboarding`; `consumer` block on `/api/state`; `payment-method` and
  `/api/onboarding` allowlisted (counts 42→43 total, 26→28 public).
- Seed: the consumer household starts with a placeholder name, **no card, no needs**.
- `apps/web/src/views/onboarding.tsx`; identity derived from server state; demo drawer
  reframed to *Act as a synthetic participant* with a persistent "acting as" banner.

**AWS / external services touched**
None. **Cost-relevant activity:** $0 — no Bedrock, no AgentCore, no deploy.

**Validation**
- 794 Python tests (was 771), 70 web tests (was 58). `make qa` green.
- Canonical scenario re-verified from state a human produced: **10 buyers, 11 membership
  rows, 1 retained failure, 1 exact replacement, 24 funded / 24 purchased / 24 pickup
  units, 2 cases, no surplus, $861.44 all-in vs $1127.76 retail.** Unchanged.
- Full loop driven in the browser at 1512×804 and 390×844: fresh → setup → Home → act as a
  synthetic participant → back to you → reset → setup again. No console errors, every
  request same-origin.

**Failures / dead ends**
The good one. Adding `onboarded_at` to the scripted setup broke
`test_the_deployed_store_and_the_local_store_produce_the_same_demo` — deterministically,
in DynamoDB only. Cause: `onboard_consumer` read the household, called
`setup_payment_method` (which writes the row), then wrote back its **stale local copy**,
clobbering `payment_method_ref` to empty. `InMemoryRepository` hands back the *same
object*, so the aliasing hid it completely; DynamoDB deserialises a fresh one, so it did
not. The symptom was not an error — it was the consumer failing authorisation later and
the pool ending with twelve rows.

A store-parity test written for a one-cent ordering bug caught a read-modify-write race
two passes later. That is the argument for testing the seam rather than the symptom.

**What we learned**
Two things worth writing up.

Deciding by measurement beats deciding by taste: "should payment be in onboarding?" was
answered by deleting the seeded card and reading the membership count, not by reasoning
about friction.

And the honest answer to a location-first product in a synthetic demo is not a better
fallback — it is not asking. Every design that requested a position had to end by
discarding it, and a permission prompt whose answer you throw away is worse than the
question you never asked.

**Article fodder**
Article 1 and Article 3. The location decision is the strongest small example in the
project of choosing truthfulness over a demo flourish, and it is falsifiable: the
`Permissions-Policy` still denies geolocation, and a test asserts the setup screen never
calls it.

**Relevant commits / files**
`services/agent/pool/services/onboarding.py` · `services/agent/pool/domain/models.py` ·
`services/agent/pool/data/seed.py` · `services/agent/pool/services/demo.py` ·
`services/agent/pool/api/{app.py,public_demo.py}` ·
`apps/web/src/views/{onboarding.tsx,demo-panel.tsx,home.tsx}` · `apps/web/src/App.tsx` ·
`services/agent/tests/test_onboarding.py` · `apps/web/src/views/onboarding.test.tsx`

---

### #0039 — [2026-08-19] — Final review before push: three things the walkthrough found
`[REVIEW]` `[SECURITY]` `[UX]`

**Goal / user intent**
Stabilisation pass over the four unpushed commits before publishing them. Not a redesign:
re-read the diff, use the product cold, fix only what is defensible, push.

**What the review found**

*A stale-write race reachable from the UI.* `complete_onboarding` writes the whole
household row. **Finish** was disabled only on its own request, so clicking it while the
"Add a test card" request was still in flight would read the row before the payment write
landed and put `payment_method_ref` back to empty. Silent, and then not silent: that member
fails authorisation at the final offer and the scenario ends with twelve membership rows
instead of eleven. Same class as the bug the store-parity test caught in `#0038`, reachable
here by a fast click. Fixed by disabling Finish while the card request is outstanding, and
pinned by a test that resolves the payment promise by hand.

*An allowlist grant wider than its use.* `POST /api/members/{id}/payment-method` had been
opened publicly for onboarding. It takes an id, and the only household setup ever wants is
the caller's own — and one synthetic household is seeded with a card that declines *on
purpose*. Handing that household a working card would silently delete the payment-failure
branch the recovery story is built on. Replaced with
`POST /api/onboarding/payment-method`, where the household is a server constant and there
is no field to point it elsewhere; the id-taking form went back to denied.

*A resume dead-end.* Setup can be interrupted. Somebody who added a declaration and then
refreshed before finishing came back to step one, and the server correctly refused a second
active declaration for the same product — so re-adding the thing they had already chosen
failed and **Continue stayed disabled**. The only way out was declaring something else they
did not want. Reproduced in the browser, then fixed by seeding the step from the member's
stored declarations rather than from an empty local array.

**Also changed**
Two copy edits, both about precision rather than polish. The location step now says *why* a
synthetic community exists ("which is what lets the demo behave the same way wherever it is
opened") and its button names the place instead of saying "Continue", because that step has
no input and the button is where the choice actually happens. And the convergence figure's
collapsed explainer gained the words "as it stands": its counts are the community's standing
declarations, and one of those lines is now the reader's own, so which side of "buying about
now" it falls on depends on the restock habit they described.

**Validation**
794 Python, 72 web, 75 infrastructure. `make qa` green. Canonical scenario re-proved from
the scripted showcase **and** from a workspace set up by hand in the browser: 10 buyers,
11 rows, 1 retained failure, 1 replacement, 24 funded / 24 purchased / 24 pickup, 2 cases,
no surplus, $861.44 against $1127.76.

**What we learned**
The human-onboarded run splits 7/16 due and 3/8 pulled forward where the scripted one
splits 8/18 and 2/6 — same totals, same money, different bucket. That is not drift: the
consumer told Pool they restock a week ahead and need it in a fortnight, so buying three
days from now genuinely *is* early, and §24 classifies it exactly right. Making the
declaration real input made the timing engine's answer depend on real input, which is the
system working. It did mean a static figure could disagree with a live run by one person,
which is what the "as it stands" edit is for.

**Relevant commits / files**
`apps/web/src/views/onboarding.tsx` · `apps/web/src/api.ts` · `apps/web/src/brand.tsx` ·
`services/agent/pool/api/{app.py,public_demo.py}` · `services/agent/tests/test_public_demo.py`

---

### #0040 — [2026-08-19] — "I declared coffee. Pool showed me whey."
`[ARCHITECTURE]` `[FRONTEND]` `[AGENT]` `[DEMO]`

**Goal / user intent**
A reported bug: a member onboarded, declared coffee as their one standing need, pressed
**Run Pool now**, and Home came back with a whey protein opportunity. Trace it, then audit
the whole class it belongs to — every way the product a member declares, the state the
coordinator evaluates, and the result shown back can come apart.

**Starting state**
`/api/agent/run` already ran the real `PoolCoordinator` against the caller's own workspace.
No scripted helper was on that path, nothing reseeded, and no hidden need was injected.

**Decision**
The coordinator was right and the interface was wrong. Home selected `state.pools[0]` —
the oldest pool in the workspace, whoever it belonged to. Fix the selection at the
*server*, from stored lineage, and make "nothing for you" a first-class answer with a
reason attached rather than an absence.

**Why**
The reproduction, end to end, from a cold workspace:

1. `seed()` writes twelve whey declarations across twelve synthetic households and six
   coffee ones across six. Neither is scripted for the visitor; both are the fixture.
2. The member declares coffee. The stored need is correct — `product_id` is exactly what
   the search returned, and it stays that way for the rest of the run.
3. `Run Pool now` → `POST /api/agent/run` → `PoolCoordinator.run()`. `list_latent_demand`
   ranks unserved demand by `(-member_count, -unserved_units, product_id)`, so whey (12
   members) is first, energy drinks (8) second, coffee (6) third. The system prompt says
   *form at most one pool per run*. The planner evaluates the first opportunity, finds it
   viable, forms it, and stops. It never reaches coffee — correctly, by its own rules.
4. `list_pools` sorts by `(created_at, id)`. Home read `[0]`.

So the member was shown a real pool, formed from real declarations, by a run they
triggered — and none of it was theirs. Nothing lied; nothing was traceable to them either.

Rejected: making the interactive run prioritise the triggering member's products. It would
have papered over the selection bug, given the community coordinator a favourite
household, and required a payload change to the deployed AgentCore contract that could not
be verified without spending on a deploy. The coordinator did not need changing.

**Implementation** — implemented and tested.

`services/agent/pool/services/relevance.py` (new) is the single place that decides what is
whose. A pool is a member's when it is in their Community, a `Membership` row joins them
to it, that membership is in a live state (`LIVE_PARTICIPATION_STATES` — declining or
withdrawing ends it; a *failed authorisation* does not, because that member is exactly who
needs telling), and the membership's `need_id` resolves to a declaration that household
actually holds. Lineage was already in the model; it was simply never read.

`need_outlook()` answers the other half. For each standing declaration with no pool, it
runs the same `evaluate_opportunity` the agent's own tool calls, across every public
pickup site and across substitute-group products Pool can actually source, and returns one
of: `in_pool` · `ready` · `short` · `not_in_round` · `not_worth_it` · `not_matched` ·
`no_supply` · `retired`. So Home says *"Not enough of it yet: 12 bags declared nearby, and
the supplier will not sell fewer than 18"*, not *"nothing yet"*.

`GET /api/members/{id}` now carries `opportunity` (or `null`) and `needs_outlook`. Home
reads those instead of the pool list. No new routes, so the published endpoint counts hold.

Four more defects the audit turned up, all in the same class:

- **Retired declarations were still poolable.** `evaluate_opportunity` and `recover_pool`
  passed the whole need table into `find_candidates`, which never checked `active`. A
  member who retired a need could still be counted toward a supplier minimum and still
  have their card authorised. Fixed in the matcher, where "who is even eligible" belongs,
  as a rejection reason rather than a silent skip.
- **A need already in a pool could be re-pointed at another product**, leaving the record
  saying somebody joined a whey order because they buy coffee while the units, the price
  and the authorisation stayed exactly as they were. `amend_need` now refuses that one
  field; everything else stays amendable.
- **An authorised substitute was undisclosed.** Declare Gold Standard chocolate with
  "same brand, another flavour is fine" and the pool buys Optimum Nutrition vanilla — the
  card led with that name and that photograph and said nothing. It now names what you
  declared.
- **Home listed retired declarations** under "what you buy anyway", and Needs counted them
  in "N independent declarations across the community".

`OpportunityAssessment` gained `matched_units`, `minimum_units` and `reason_code`. The
shortfall was only ever inside a prose sentence, and anything that has to *branch* on why
an opportunity failed should not be matching on wording that has been reworded twice.
`LEFT_PARTICIPATION_STATES` replaces four inline copies of the same set.

The outlook is not free: it runs `evaluate_opportunity` once per sourceable product per
public pickup site, and each of those re-reads the need, household, product, offer and
membership tables. One member view measured **86 repository reads** against 21 for
`/api/state`. Two fixes, both kept: a read memo scoped to that one read-only pass (86 →
**18**), and moving ownership of the member view up into the shell so Home and Needs share
one request instead of making two. The memo is only sound because the pass writes nothing,
which is now pinned by a test rather than assumed.

**AWS / external services touched**
None. Everything ran on the in-memory repository, the deterministic planner and the
deterministic router.

**Cost-relevant activity**
None. No Bedrock, no AgentCore invocation, no deploy. The audit was deliberately run
against the offline coordinator, which is what it exists for.

**Agent behavior**
Unchanged, and that is the finding. Offline planner, five iterations, tools
`list_latent_demand → evaluate_pool_economics → create_candidate_pool →
request_host_acceptance`. Same before and after the fix, for the coffee member and the
whey member alike. What changed is which of its results is presented as whose.

**Validation**
Reproduced first, from a cold workspace through the real endpoints: coffee declared,
whey pool formed, `opportunity` null, coffee need untouched. Then a product matrix, each
from its own fresh workspace, run through onboarding → declare → Run Pool now:

| Declared | Stored product | Coordinator | Shown to the member |
| --- | --- | --- | --- |
| `vanilla whey` → Optimum Nutrition, 2 tubs | `prod_whey_vanilla` | forms the whey pool | **their** pool, 2 tubs, $71.92 vs $93.98 |
| same, 3 tubs | `prod_whey_vanilla` | forms it without them (case boundary) | `not_in_round`, honestly |
| `coffee` → Death Wish Dark Roast | `prod_0810063343040` | forms the whey pool | `not_matched` — exact-only, different product |
| same, category substitution allowed | `prod_0810063343040` | forms the whey pool | `short` — 12 bags of 18 |
| Paper towels | `prod_paper_towels` | forms the whey pool | `short` — 5 of 48 |
| Laundry pods | `prod_detergent_pods` | forms the whey pool | `not_worth_it` — clears the minimum, saves nothing |
| Custom "Cardamom pods, 500g" | custom row | forms the whey pool | `no_supply` |
| Gold Standard chocolate, substitution on | `prod_whey_chocolate` | forms the vanilla pool | their pool, **named as a substitute** |

21 new API-level tests in `test_consumer_relevance.py`, plus 7 new Home tests. Full
`make qa`: ruff clean, **815** Python, **79** web, **75** infrastructure, typecheck clean,
production build, secret scan clean. Canonical showcase re-proved unchanged: 10 buyers,
11 membership rows, 1 retained authorisation failure, 1 exact replacement, 24 funded /
24 purchased / 24 pickup units, 2 cases, no surplus, $861.44 all-in against $1127.76
retail, $266.32 saved, 23.6%.

Visually walked on desktop and at 390 px: cold Home, post-run no-op, the community banner,
the whey success, the substitute disclosure, a browser refresh, and stepping into a
synthetic participant and back out.

**Failures / dead ends**
The first `need_outlook` reported "ready" for demand that a pool had already consumed — it
evaluated without the `pooled_household_ids` exclusion the coordinator's own tools apply.
It also attributed rejections by `household_id`, so a member holding two declarations saw
their paper-towel need explained by their coffee one; keyed on `need_id` now. And the
outlook list was first rendered with `.ledger`, whose values are tabular numerals set
`nowrap` — one full sentence pushed the card off a 390 px screen.

**What we learned**
The bug was not in the agent, the tools, the economics or the store. Every one of those
was right. It was one array index in a React component, and the reason it survived is that
the interface was answering a question — *whose is this?* — that only the server could
answer. Lineage existed in the data model the whole time (`Membership.need_id`); nothing
read it. A "no result" state with a reason attached is also worth more than a successful
one that belongs to somebody else, and it fell straight out of running the same
deterministic evaluator at read time instead of inventing a second explanation.

**Article fodder**
Article 3 — the honesty boundary is not only *act vs. ask*; it is also *whose result is
this*. A community-scoped agent and a personally-scoped interface disagree by default, and
that disagreement is invisible in every test that only checks the agent.

**Evidence worth preserving**
Before: Home leading with "Pool found overlapping demand — 100% Whey Protein" for a member
who declared coffee. After: "Nothing worth coordinating yet · POOL CHECKED", the coffee
sentence, and "Pool is also coordinating 100% Whey Protein for other members here. You are
not in it."

**Relevant commits / files**
`services/agent/pool/services/relevance.py` (new) · `services/agent/pool/services/{coordination,needs}.py` ·
`services/agent/pool/domain/{models,matching}.py` · `services/agent/pool/api/app.py` ·
`services/agent/tests/test_consumer_relevance.py` (new) · `apps/web/src/views/{home,needs,demo-panel}.tsx` ·
`apps/web/src/{App.tsx,api.ts,styles.css}` · `apps/web/src/views/home.test.tsx`

---

### #0041 — [2026-08-19] — Whose question is the button asking?
`[product]` `[agent]` `[domain]` `[demo]`

**Goal / user intent**
#0040 stopped a member being *shown* somebody else's pool. It left the coordinator itself
community-scoped, so the causal chain was still wrong one step earlier: a member could declare
coffee, press **Run Pool now**, and the run would go and form a whey order for ten other students.
Home then said, correctly, that their coffee had not formed and that whey was being coordinated
elsewhere — honest, and still not what the button means.

**Starting state**
One trigger. `PoolCoordinator.run()` took a free-text `instruction`, the public API substituted a
server-owned prompt for it, and every prompt said the same thing: scan the community. Nothing in
the system could express "answer *this* member's declarations".

Two further defects turned up while measuring, and neither was cosmetic.

**Decision — 1. Two triggers, one coordinator**
`member_scan` versus `manual_scan`/`scheduled_scan`. The trigger is the only thing on the wire; the
*objective* is derived server-side inside the coordinator from stored state
(`agent/objective.py`), so the local API, the AgentCore runtime and the test suite all produce the
same semantics from the same tiny payload.

A member objective is that household's active declarations that no live pool is already serving,
soonest first, capped at three — and capped at three for a measured reason, not taste: one listing,
one evaluation each, one pool, one host offer and one closing turn is seven model calls against a
bound of eight. A fourth would sit exactly on the safety net.

There is no household field anywhere in the request. This build has no authentication, so "the
member" resolves to the one household a real person uses — the same server-owned resolution
`/api/onboarding/payment-method` already relies on. A caller cannot point a run at somebody else
because there is nowhere to name them, and the prompt the model receives names products and
quantities and never a person.

The anchor sets the *objective*, never the *answer*. A member run investigates each declaration it
took on and then acts on at most one; "nothing worth coordinating yet" remains a successful
outcome.

**Decision — 2. Discovery and the matcher had drifted apart**
`list_latent_demand` bucketed declarations by substitute *group* and reported the whole bucket as
the demand behind the group's largest product. The matcher then applied each member's own
substitution policy and rejected some of them. A visitor who declared Death Wish coffee
**exact-only** was therefore counted toward the actionable demand for Pike Place — an opportunity
that shrank the moment it was costed.

The listing now counts only declarations `domain.substitution` would let that product serve,
evaluated at the most favourable bulk price any tier offers (so a declaration excluded here is
excluded by every tier). Category interest survives under its own name — `group_interest_units` —
because "people who buy some coffee" and "people whose standing authority this order can use" are
two different numbers. One implementation, in `services/discovery.py`; the compatibility function
is the matcher's own.

The same rule decides what a member run may *act* on: `sourceable_targets_for_need` filters the
substitute-group search through that member's authority, so an exact-only declaration for an
unsourceable brand no longer forms a pool for six other people because two categories coincided.

**Decision — 3. `FORMATION_RADIUS_KM` was a duplicate authority, and the wrong one**
This was measured before it was touched. `Community.radius_km` — declared 2.5 km for Demo
University — was read **nowhere in the codebase**. Meanwhile a module constant of 1.6 km decided
who could form a pool, and the constants' own docstring claimed both radii were "bounded by the
Community radius". Nothing bounded them; `RECOVERY_RADIUS_KM = 4.0` searched well outside a 2.5 km
Community.

The consequences were worse than a stale number. A verified member sitting in the 1.6–2.5 km
annulus was inside their own Community and permanently undiscoverable — reachable only by a
recovery. And the cut *overrode each member's own declared travel authority in the stricter
direction, silently*: somebody who said they would walk 24 minutes was excluded by a rule they
never agreed to and never saw, while the rule they did state was only ever a soft prompt.

So the asymmetry survives and the authority moves. Formation searches the Community's own radius;
recovery widens past it by a stated multiple (1.6 × 2.5 = 4.0 km, exactly today's value, now
derived rather than declared twice). The 1.6 km figure is kept under the name it actually earns —
`WALKABLE_PICKUP_KM` — and used *only* to rank candidate pickup sites, which excludes nobody. The
per-member travel gate is `max_travel_minutes`, evaluated against real routed time by Smart Join,
where it always belonged.

**Why not simply raise the constant**
Because "the audit said 2.5 makes the demo better" is not a domain reason, and a number chosen to
make a demo work is exactly the kind of thing this project exists not to ship. The defensible
statement is about authority, not distance: coarse geography is a search bound and a ranking
preference; the boundary Pool coordinates inside is the Community, and the person who decides how
far they will walk is the member.

**Implementation**
`agent/objective.py` (new), `services/discovery.py` (new), `agent/coordinator.py`,
`agent/offline_model.py`, `agent/tools.py`, `agent/projection.py`, `services/coordination.py`,
`services/relevance.py`, `api/public_demo.py`, `agentcore_app.py`. Status: **tested**.

**AWS / external services touched**
None. No deployment, no Bedrock or AgentCore invocation, no paid call of any kind.

**Cost-relevant activity**
None. Every run in this entry used the offline deterministic planner. A member-triggered run is
*cheaper* than the scan it replaces on the consumer path: it evaluates at most three products
instead of ranking the whole community, and the iteration and tool-call bounds are unchanged.

**Agent behavior**
Offline deterministic planner · same twelve tools · a member run calls
`list_latent_demand` → `evaluate_pool_economics` per objective → `create_candidate_pool` →
`request_host_acceptance`, five iterations · a member with no unserved declaration terminates on
`record_no_action` with that as the recorded reason. The community scan is unchanged and still
short-circuits on the first viable assessment, because the pool-day scan owes the best available
action rather than a verdict per product.

**Validation**
844 backend tests pass (815 before; 29 new across `test_run_objective.py`, `test_discovery.py`,
`test_seed_outcomes.py`). Measured, not assumed:

- The canonical showcase is **bit-for-bit unchanged** by the radius correction. Same pickup site
  (North Hall lobby), the same eleven membership rows, the same replacement household
  (`hh_amadi`), 24 funded / 24 purchased / 2 cases / 0 surplus, $861.44 all-in against $1127.76
  retail, $266.32 saved at 23.6%, host pay $44.68, Pool fee $32.70, processing $28.06, and the same
  8-members/18-units due-now against 2-members/6-units pulled forward.
- The seeded world's outcome taxonomy went from one reachable class to four. Before: whey viable,
  everything else refused on geography. After: whey (23.5%), coffee (17.2%) and energy drinks
  (14.7%) each viable on their own members; detergent refused on **economics** at −11.2% with 12
  units against a 12-unit minimum; paper towels refused on the supplier minimum at 4 against 48;
  chocolate whey refused for having no bulk quote at all.

**Failures / dead ends**
Three tests were passing for the wrong reason and are now fixed rather than deleted.
`test_a_product_whose_bulk_price_does_not_beat_retail_forms_no_pool` asserted only that no pool
formed — at 1.6 km the detergent demand never cleared its minimum, so the economics branch the test
is *named after* had never once executed. Two AgentCore workspace tests asserted "exactly one pool
exists" as a proxy for idempotency; with a richer world a second community scan legitimately finds
the next opportunity, so they now assert what they meant — no duplicate for the same product, site
and distribution day.

An earlier draft let a member run form a pool for any product in their declaration's substitute
group. It passed its tests and was wrong: it re-created the reported bug one level down, forming an
order the member could never join because a category matched.

**What we learned**
A field nothing reads is not dead weight, it is a second opinion nobody is consulting — and the one
the code *was* using turned out to be the one nobody could see. The give-away was the docstring:
it described a constraint ("bounded by the Community radius") that had never been implemented, and
had been quoted forward into the article notes.

The other lesson is about test naming. A test called "bulk price does not beat retail" that asserts
`viable is False` will pass for years on a fixture where the price is never reached. Assert the
reason code, not the absence.

**Article fodder**
Article 1 — the difference between a system that is *honest* and a system that answers the question
you asked. Article 3 — where a coarse safety constraint quietly outranks a preference the user
actually stated, and why that is an autonomy bug rather than a tuning one.

**Evidence worth preserving**
The before/after outcome table for the seeded world. The canonical reconciliation being identical
across the radius change is the load-bearing measurement: it is what makes "this was a correctness
fix, not a demo tuning" checkable rather than asserted.

---

### #0042 — [2026-08-19] — Write down what the run found, before the process disappears
`[agent]` `[observability]` `[product]`

**Goal / user intent**
Make a run explainable to the person who triggered it, from facts the system genuinely
established — not from a recomputation, and not from prose a model was asked to write.

**Starting state**
A run computed a great deal and kept almost none of it. `evaluate_pool_economics` produced a
complete `OpportunityAssessment` — matched units against the supplier minimum, which bulk tier won
and what lost to it, the case fit, the per-declaration rejection reasons, the landed economics —
and the model was shown a projection of it while the authoritative copy went onto
`ToolContext.full_results`, an in-process object. Locally the API could reach it through
`coordinator.last_tool_context`. After an AgentCore run it is in a microVM that no longer exists,
so the deployed path had no way to explain anything. What survived either way was a count and a
180-character tool summary.

Recomputing afterwards was the obvious alternative and is a different claim: current state and
"what this run found" diverge the moment anything else changes, and presenting the first as the
second is retrospective omniscience (§8).

**Decision — a stored evaluation record**
`RunEvaluation`, one row per (run, product) the run actually costed, written through the repository
at the end of the coordinator's own execution. Both entrypoints produce identical rows because both
run the same coordinator.

Written *after* the try/except deliberately: a run stopped by a safety bound still did real work
first, and what it established is exactly what somebody will want to read. Written from the
coordinator rather than from inside the tool so `evaluate_pool_economics` stays provably
side-effect-free — the member outlook calls the same evaluator, and `test_a_member_view_writes_
nothing` pins that a member opening their home screen changes no row.

Bounded on every axis: a fixed field set, at most 12 evaluations per run, 6 supplier tiers, 8
per-declaration verdicts, and the reason string capped at 300 characters.

`AgentRun` also gained what the run was *asked* — objective kind, the anchoring household, and the
declarations it took on, deferred, and skipped as already-served. Without that, "investigated and
declined" and "never investigated" are indistinguishable after the fact, and a member with more
declarations than one run takes on cannot be told which is which.

**Privacy**
An evaluation touches every declaration in the Community. `need_verdicts` carries only the
declarations the run was asked about — the member's own — so one member's report cannot become a
readout of why six neighbours were excluded. No names, no contact details, no payment references,
no model text. A test asserts all of that against the seeded households rather than trusting the
field list.

**A real defect found on the way in**
The earlier pass flagged as a risk that `OpportunityAssessment.rejected` might reflect the last
bulk tier evaluated rather than the winning one. It did. `empty.rejected` was assigned inside the
tier loop, so a *viable* assessment came back explaining itself with a *losing* tier's rejections —
and the tiers genuinely disagree, because a member's per-unit price ceiling is applied against each
tier's own price.

Reproduced: whey has a $31.50/unit tier with a 24-unit minimum and a $39.80/unit tier with a
12-unit one, evaluated in that order. A member whose substitution rule carries a ceiling between
them is compatible with the cheap tier that wins and rejected by the expensive one that is
evaluated last — so the assessment both selected and rejected the same declaration. Nothing
downstream noticed, because nothing downstream had ever read the list.

`matched_units` and `minimum_units` had a quieter version of the same problem: max-across-tiers
paired with min-across-tiers, which is two true numbers describing a supplier offer nobody made.
Both now come from one tier — the winner, or when nothing priced, the one that came closest.

**Implementation**
`domain/models.py` (`RunEvaluation`, objective fields on `AgentRun`), `agent/evidence.py` (new),
`services/run_report.py` (new), `services/coordination.py` (per-tier attribution and
`offers_considered`), `adapters/repository.py` (both stores), `api/app.py`
(`GET /api/runs/{id}/report`), `api/public_demo.py` (allowlist). Status: **tested**.

**AWS / external services touched**
None.

**Cost-relevant activity**
None, and none added: the report is deterministic rendering of stored values. No model call is made
to explain a run, which was the tempting and wrong design — it would have put a language model
between a member and a price.

**Validation**
864 backend tests pass (846 before). The attribution fix was verified adversarially: reinstating
the old last-tier assignment makes `test_rejections_belong_to_the_offer_that_won_not_the_one_
evaluated_last` fail with the member appearing in both the selected and rejected sets, which is the
bug exactly.

**Failures / dead ends**
First attempt wrote the evaluation from inside `evaluate_pool_economics`, which would have meant
relabelling it from `read` to `record` in the tool surface. The label would have been honest — the
kind's own definition is "an evaluation it wants to be able to show its reasoning from" — but it
would have cost the strongest guarantee in the tool surface, that the read tools are provably inert
under a whole-workspace snapshot. Not worth it for a write the coordinator can do once at the end.

A structural slip worth recording: inserting `RunEvaluation` immediately after `AgentRun.from_dict`
silently made `AgentRun.duration_ms` a method of the *new* class. 132 tests failed with
`AttributeError: 'AgentRun' object has no attribute 'duration_ms'`, which is the good outcome — a
property quietly landing on the wrong class is exactly the kind of thing a type checker over
dataclasses does not catch.

**What we learned**
"The risk exists in principle" and "the risk is real" are worth ten minutes apart. The rejected-list
attribution had been flagged as a *possible* problem and dismissed as low-impact because nothing
read the field. Building something that reads it turned a latent inconsistency into a visible one —
which is the argument for building the explanation feature at all: an unexamined intermediate result
is where wrong answers accumulate quietly.

**Article fodder**
Article 2 — the process boundary is the design constraint. Explaining an agent run is easy while
you are still in the process that ran it, and that is precisely the case that does not survive
deployment. Article 3 — the difference between persisting deterministic evaluations and persisting
model reasoning, and why only one of them is safe to show a user.

**Evidence worth preserving**
The two-tier whey reproduction. It is a small, complete example of an agent system producing
confident, plausible, wrong evidence, caught only because something finally consumed it.

---

### #0043 — [2026-08-19] — The scripted proof gets its own community
`[product]` `[demo]` `[architecture]`

**Goal / user intent**
Stop the canonical showcase writing into the visitor's account.

**Starting state**
`/api/demo/scenario` ran in the caller's own workspace. `run_showcase` opens by declaring the
flagship whey need for `CONSUMER_HOUSEHOLD` — which *is* the household a real visitor uses — so a
person who had declared coffee, pressed "run the full lifecycle" to see how a pool works, and gone
back to Needs found Pool believing they also buy whey protein.

The endpoint had already been patched once around this: reseeding wipes the partition, and that
included the account somebody had just set up, so the reseed was skipped whenever the visitor had
onboarded. That fixed the symptom (their account surviving) by causing the disease (the canonical
declaration landing in it), and it made the interface's own copy false — "this starts the community
over" could not be true of a replay that deliberately did not start anything over.

Labelling the row `declared_by: scenario` was the third patch. A provenance tag on a row that
should not exist is not consent.

**Decision**
Separate the state, not the labels. The showcase runs in `f"{workspace}-showcase"`, derived
server-side from the caller's session. Two properties come free from the hyphen: a
browser-generated session id can never contain one, so a visitor's own partition and their showcase
partition can never collide; and reaching somebody else's showcase still requires guessing their
session id, which is the property already protecting `/api/state`.

The replay therefore always reseeds, unconditionally, which is what makes the copy literally true.

On the client, showcase mode became a *world* rather than a screen: one module-level scope flag in
`api.ts` decides which partition every request addresses. Entering showcase points everything at
the showcase partition; leaving points it back. The visitor's state is not "restored" — it was
never touched.

**Why not thread a workspace through every call**
Considered and rejected. The pool drawer is shared between the product and the showcase and carries
real actions — approve a decision, redeem a credential, open distribution. Threading a workspace
argument through each of those is the version of this change that silently misses one, and the one
it misses writes a member's real account from inside a scripted replay. A single scope has exactly
one thing to get right.

**Also moved**
`Run the full lifecycle` is gone from the ordinary consumer pool record. It replays a whole
community from scratch, and offering that from inside a member's own order is an invitation to
"start over" that reads as being about their order. It remains in Showcase and in Demo controls,
where the surrounding copy says what it does.

The demo panel's own entry point was reading `state.pools[0]` to decide where to land — the oldest
pool in whatever workspace happened to be loaded, which after this change is the visitor's own and
has nothing to do with the replay.

**Implementation**
`api/app.py`, `api/public_demo.py` (`SHOWCASE_SUFFIX`, `showcase_workspace`, widened
`PUBLIC_WORKSPACE_RE`), `apps/web/src/api.ts` (scope), `App.tsx`, `views/pool.tsx`, `views/run.tsx`,
`views/demo-panel.tsx`. Status: **tested**.

**AWS / external services touched**
None. The showcase partition inherits the same 24 h TTL as every other demo workspace, so it
sweeps itself; no new table, no new resource.

**Cost-relevant activity**
Marginally *lower* contention: the lease the scenario takes is now on the partition it actually
rewrites, so a visitor's own coordinator run and the scripted replay no longer block each other.

**Validation**
868 backend tests pass, 79 web tests pass. Four new tests pin the boundary: the visitor's consumer
record, needs list, pools and personal opportunity are all identical across a full scripted
lifecycle; the showcase workspace holds the canonical pool; a second replay produces a *different*
pool id and leaves exactly one pool, proving the reseed is real; and a showcase workspace is only
addressable by knowing the session it belongs to.

**Failures / dead ends**
Eleven existing tests used the scenario as a convenient way to populate a workspace and then read
`/api/state`. They now read an empty one, which is the isolation working — but two of them,
`test_workspaces_are_isolated` and `test_two_anonymous_judges_cannot_see_each_others_demo`, would
have gone on *passing* while proving nothing, because they compared two workspaces neither of which
was written any more. Both were rewritten to drive a real coordinator run instead.

**What we learned**
Three patches in a row around one endpoint, each fixing the previous one's side effect, is the
signal that the shape is wrong rather than the code. The tell here was the copy: the interface had
to be softened twice to stay honest about what the button did, and text bending around a behaviour
is usually cheaper to notice than the behaviour itself.

**Article fodder**
Article 1 — a demo that mutates the user's own account to prove itself is not a demo of the
product, and the fix is architectural rather than editorial.

**Evidence worth preserving**
The before/after of the demo panel copy. The old version had to explain that the replay would
declare a whey need on your account and that you could retire it afterwards; the new one does not,
because it does not.

---

### #0044 — [2026-08-19] — Making the sourceable product findable, without lying about the rest
`[product]` `[demo]`

**Goal / user intent**
Close the gap between "the catalogue is real" and "Pool can actually buy this", without
compromising either.

**Starting state**
Typing `coffee` returned eight real coffees ranked purely by how well the word matched, and the one
Pool holds a synthetic verified bulk quote for was not among them. "Death Wish Coffee Co" outscored
it because the noun appears in its *brand*; "Folgers Coffee" outscored it because the phrase appears
in its label. A member picked one, kept `exact_only`, and Pool correctly reported that nothing could
be done.

Every step of that is honest and the whole path is a dead end. Worse, it made the demo's actual
sourcing capability invisible unless you knew to type the magic phrase.

**Decision**
A ranking and a label, not a rewrite.

`catalog.search` takes the set of products this deployment holds a usable bulk quote for and gives
them a bounded boost — deliberately larger than a brand-word coincidence and smaller than a full
phrase match, so `coffee` leads with the sourceable one while `death wish` and `folgers coffee`
return exactly what was asked for. The boost cannot invent a match: a product the query does not
hit scores zero and is excluded before any of this applies, so it changes the *order* of things a
member could legitimately have meant and never what they get if they keep typing.

The set comes from the same `offers_for` the evaluator consults, so nothing can be marked sourceable
that an opportunity assessment could not price. No offer is fabricated for a catalogue product; the
separation between real product identity and synthetic supplier economics is the thing this
constraint exists to protect (§41, §48).

Every result carries `sourceable`, and a card that has it says so — because a ranking a member
cannot see the reason for is just a mysterious ranking.

**The substitution control moved out of the advanced drawer**
This is the change with the most product in it. Substitution decides whose demand may combine with
whose; for a product Pool cannot source it is the *only* setting that could change the answer. It
was behind a collapsed "fine-tune" disclosure, so a member never saw a choice they had already
effectively made. It now sits in the main form, phrased as a question, and when the chosen product
is unsourceable it says so plainly and adds that widening it is their call rather than Pool's.

**What was deliberately not done**
Auto-converting an unsourceable choice into the neighbouring product Pool can buy; silently
widening `exact_only`; special-casing the string `coffee`; fabricating a bulk offer for a catalogue
entry. Each would have made the demo smoother by making the product dishonest — and the first two
are Pool deciding what somebody buys, which is the one decision it must never take.

**Implementation**
`data/catalog.py` (`SOURCEABLE_BOOST`, `search(sourceable_ids=…)`, `view(sourceable=…)`),
`api/app.py` (`_sourceable_product_ids`), `product-search.tsx`, `views/needs.tsx`, `styles.css`.
Status: **tested**.

**AWS / external services touched**
None. Still a bundled snapshot ranked by a pure function — no network on the keystroke path, no
model, no per-character cost.

**Validation**
881 backend tests pass, 81 web tests pass. Thirteen new tests in `test_sourceability.py`: every
sourceable product leads its own generic query (`coffee`, `whey`, `energy drink`, `laundry`,
`paper towels`); a named brand still wins; the boost cannot make an unrelated product appear; the
flag agrees with `offers_for` for every result of five different queries; and no catalogue entry
outside the seeded six has an offer at all.

**Failures / dead ends**
Two existing tests had been quietly relying on `coffee` *not* resolving to the sourceable product —
the way they expressed "pick something Pool cannot source" was "take the first result". They now say
what they mean and ask for the first *unsourceable* one, which is a better test and only possible
because the flag exists.

**What we learned**
The dead end was not a bug in any one component. Search was correct, substitution was correct, and
the evaluator was correct; the product failed at the seam between them, where nobody had written
down that "we can buy this" is a fact worth showing. Seams are where honest components combine into
a misleading experience.

**Article fodder**
Article 1 — the difference between a demo that works when you type the memorised phrase and a
product that works when you type what you buy.

---

### #0045 — [2026-08-19] — Home stops answering the question it is supposed to ask
`[product]` `[ux]` `[agent]`

**Goal / user intent**
Make the consumer surface tell the truth in both directions: pose the question before a run, and
answer it afterwards from what the run actually established.

**Starting state — the answer key**
The pre-run slot drew `ConvergenceFigure`: thirteen restock dates converging on one pool day, eight
already due, eighteen units, two pulled forward, twenty-four. Every number is real and derived from
the seed — and drawing it *before* the run tells a judge the answer and then invites them to watch
Pool produce it. It also hardcodes the canonical scenario into a screen that a member with a coffee
declaration would also see.

The other half was the outlook. `needs_outlook` is a genuinely good thing — it runs the same
deterministic evaluator the coordinator's tools use and says why nothing has formed — but on Home,
before a run, it reads as a verdict ("Worth pooling now", "Nothing worth coordinating yet") for work
that has not happened.

**Decision — three states, each honest about which it is**

*Before.* `standing_demand` on `/api/members/{id}`: per declaration, how many other members have
independently declared something this order could serve, how many units that is, and the smallest
quantity the supplier will sell. **Inputs only, no verdict.** The card then names what is still open
— whether those people can reach one pickup point, whether their restock dates overlap, whether the
units fill whole cases, whether the all-in price beats buying alone — because that is what stops the
counts reading as a promise.

*During.* Unchanged, deliberately: request sent, real elapsed time, no invented per-tool progress.
One addition, and only when it is knowable in advance — with exactly one un-pooled declaration the
wait names it ("Pool is checking your Pike Place Medium Roast declaration…"), because the objective
is derived from stored state *before* anything is invoked. With several it says nothing, since which
of them a bounded run takes on is the server's decision and not the browser's to guess.

*After.* The run report, from `#0042`'s stored evaluations. An order the member is in leads with the
order card and hangs "Why this worked" off it; everything else — declined, formed-without-them,
viable-but-next, not-investigated — is the answer card. Nothing is recomputed in the browser and
nothing appears for a product the run did not evaluate.

The outlook moved to Needs, beside each declaration, under the label **As things stand**. "Pool
evaluated this and declined" and "here is how it looks right now" are different claims, and the
interface now says which one it is making (§15).

**A gap the two-declaration case exposed**
A member with coffee and whey, both viable: Pool forms one order per run, so the second was reported
as `declined` with the evaluator's own internal string — *"viable bulk opportunity"*. Two fixes.
`RESULT_VIABLE_NOT_ACTED` says what is true ("Pool can form this one too, and forms one order at a
time — so it is next"). And the run now *prefers the viable order that includes the member's own
declaration*: `evaluate_pool_economics` returns `includes_member_declaration`, a deterministic fact,
so a run does not form an order its own requester was case-fitted out of when there is one they are
in. Also made the objective's ordering deterministic — it tie-broke on random need ids, so which of
two same-day declarations a run acted on moved between runs.

**Implementation**
`services/discovery.py` (`standing_demand_for`), `api/app.py`, `services/run_report.py`,
`agent/tools.py`, `agent/projection.py`, `agent/offline_model.py`, `agent/objective.py`,
`views/home.tsx`, `views/needs.tsx`, `ui.tsx`, `api.ts`, `App.tsx`, `styles.css`. `ConvergenceFigure`
is kept and still drawn on About, where explaining the mechanism is the whole job. Status:
**tested**.

**AWS / external services touched**
None.

**Cost-relevant activity**
None. The report is deterministic rendering of stored rows — no model is asked to write prose, which
was the tempting design and would have put a language model between a member and a price.

**Validation**
`make qa` green: 881 backend, 75 infra, 84 web, lint, typecheck, production build, secret scan. Home
tests were rewritten around the new states rather than deleted — the invariants they pin (an
unrelated pool is never this member's result; a pool the member *is* in is never called somebody
else's; the community's order is openable as the community's) all survive, now expressed against the
report and the muted "Elsewhere" block.

**Failures / dead ends**
The first layout rendered the personal outcome twice — once as a run result and again as the order
card — which made one answer look like two. Merging them, with the run's facts hanging off the order
under "Why this worked", is both shorter and truer to what the two things are.

**What we learned**
The convergence figure was the most-admired thing on the screen and the most dishonest, and neither
was obvious. It was accurate, derived, and tested against the seed; what made it wrong was *when* it
was shown. Correct content in the wrong moment is still a claim about work that has not happened.

**Article fodder**
Article 1 — the pre-run screen is where a demo either poses a question or spoils it. Article 3 —
"investigated and declined", "worth doing but not this run", and "not looked at" are three different
answers, and collapsing them is how an agent product starts sounding like it knows more than it does.

**Evidence worth preserving**
Before/after of the Home pre-run slot: the convergence diagram against the standing-demand card. It
is the clearest single illustration of the difference between showing the input and showing the
answer.

---

### #0046 — [2026-08-19] — A demo that does not need a memorised phrase
`[demo]` `[docs]`

**Goal / user intent**
Rewrite the rehearsal around what the product now does, and prove the claim it rests on: that Pool
behaves correctly for arbitrary supported input rather than for one word.

**Starting state**
`DEMO_SCRIPT.md` ran 4:53 and opened by instructing the presenter to type `vanilla whey`. That was
honest at the time — search could not surface what Pool could source, so typing a category was a
dead end — but it meant the recording could not survive a judge typing anything else, and it spent
most of its length walking a lifecycle a reader can step through themselves.

**Decision**
Type a **category**. `whey`, `coffee`, `energy`, `laundry`, `towels` — each leads with the option
Pool can genuinely source, labelled, and each reaches a different truthful outcome.

Two declarations in setup rather than one, which is the change that makes the demo about the right
thing. One product proves Pool can find an overlap; two prove it tells the truth about **both**,
and the second answer is *no*. Measured, from the real endpoints, on the form's own defaults:

- whey → formed, member included, 10 buyers, 24 units, 2 cases, six stored facts behind it
- paper towels → declined: "6 compatible packs were declared near you, and the supplier will not
  sell fewer than 48"
- and with a third — laundry → declined on **economics**: "$398.92 against $367.84 buying it alone"

Three declarations, three genuinely different deterministic verdicts, one button, seven model turns
against a bound of eight.

The canonical lifecycle becomes the **backup and regression proof** rather than the recording — now
that it runs in its own copy of the community, saying so is also literally true.

**One inconsistency the rehearsal caught**
The pre-run card said "the supplier will not sell fewer than 12" and the run afterwards said
"reached the supplier's 24-unit minimum". Both true — whey has a 12-unit tier at $39.80 and a
24-unit one at $31.50, and the evaluator takes the second — and side by side they read as a
contradiction. The pre-run card now reports the *cheapest tier's* minimum, which is both the honest
"best price starts at" figure and the one the run actually clears.

Also: the run's all-in figure is now prefixed "about", because an evaluation is always made before
a fulfiller has accepted and their pay is part of the price. A judge comparing $862.45 in the
explanation against $861.44 in the locked ledger should find the difference already accounted for.

**Documentation reconciled**
`docs/ARTICLE_NOTES.md` still described "form tight (1.6 km), repair wide (4 km)" as a clean product
decision. It was quoting a docstring that described a constraint never implemented, so the note now
records what was actually wrong and why the correction is about *authority* rather than distance.
`AGENTS.md` §8 gained the two-trigger rule and the showcase-workspace boundary. Endpoint counts in
`README.md`, `docs/architecture.svg` and `public_demo.py`'s own docstring were three different
stale numbers; all four now agree at 29 of 45, pinned by the test that noticed.

**Implementation**
`docs/DEMO_SCRIPT.md` (rewritten), `docs/ARTICLE_NOTES.md`, `AGENTS.md`, `README.md`,
`docs/architecture.svg`, `services/discovery.py`, `services/run_report.py`,
`tests/test_presentation_truth.py`. Status: **tested**.

**AWS / external services touched**
None. No deployment and no paid invocation in this pass.

**Validation**
`make qa` green: 897 backend, 75 infra, 84 web, lint, typecheck, production build, secret scan.
Every figure quoted in the script was measured through the real endpoints first; two new
presentation tests assert the rehearsal shows a refusal as well as a result, and that it says the
showcase has its own community.

**Failures / dead ends**
`test_the_rehearsal_opens_on_the_person_not_a_dashboard` asserted the script contained
``` `vanilla whey` ``` — pinning the magic phrase as a *requirement*. Inverting it (the phrase must
**not** appear as an instruction) then failed against the paragraph explaining why it was removed,
which is the right kind of failure: the assertion had to become specific about instructions rather
than mentions.

**What we learned**
The strongest beat in the new script is the one that says no. A demo built entirely from successes
cannot demonstrate the property that actually matters here — that the run answers *your*
declarations — because a system that always succeeds looks identical to one that always says yes.

**Article fodder**
Article 1 — "the demo needs a magic word" is a product finding, not a presentation problem, and the
fix was in search rather than in the script.

---

### #0047 — [2026-08-19] — Merge-readiness review of the member-trigger branch
`[REVIEW]` `[FRONTEND]` `[DEMO]` `[MERGE]`

**Goal / user intent**
Verify the `fix/consumer-result-relevance` implementation report against the repository rather than
trusting it, inspect the whole feature diff for correctness, security, privacy, cost, lifecycle and
demo-truth regressions, fix only what could be proved, and merge into `main` if the branch earned
it. No deployment, no paid model call.

**Starting state**
`fix/consumer-result-relevance` at `375e7eb`, pushed and tracking; `main` and `origin/main` both at
`af6237d`; working tree clean. 50 files, +7503/−482 against `main`.

**Decision**
Merged with `--no-ff`, preserving the branch's eleven logical commits, after fixing three defects
the review proved. None of the three was a blocker under the pass's own criteria; all three were
small, provable and adjacent to claims the branch makes, so they were fixed rather than filed.

**Why**
The report's substantive claims held up under adversarial checking, which is the bar for merging. A
brute-force cross-check over 36 injected declarations × 6 products × every public site × every tier
price found **zero** disagreements between `services.discovery.compatible_needs` and
`domain.matching.find_candidates` in either direction — the invariant the branch exists to enforce.
The membership-verification gap that cross-check suggested turned out to be unreachable: `needs.py`
refuses a declaration from an unverified household, so an active need cannot exist without one.

**Implementation**
Three fixes, each with a regression test that fails on the old behaviour. Status: tested.

1. **`apps/web/src/App.tsx`** — the drawer's *Open Showcase mode* set the view directly instead of
   going through `showcaseTo`, leaving `api`'s showcase flag on the visitor's session. The
   showcase's front page then read the visitor's community and printed its counts as the
   showcase's: observed live as "24 members and 34 standing needs" where the showcase holds 31. It
   now goes through `showcaseTo`, the single entry point. Separately, `member` and `report` are
   answers scoped to one partition and were cleared one render *after* the scope moved, so leaving
   the showcase asked the visitor's partition for the showcase's pool id three times and took three
   404s. Both are dropped in the same callback that moves the scope, next to `openPool`.
2. **`services/agent/pool/services/run_report.py`** — `sourceable_targets` deliberately widens the
   search to permitted substitutes, so a run can cost two products for one declaration and reach
   two verdicts; the report took whichever was evaluated first. A member whose substitute formed an
   order they did not fit inside was told "nobody near you has declared anything this order could
   be shared with" — true of the *other* target, and no answer at all. `formed_excluded` existed for
   exactly that outcome and was unreachable. Precedence now: an order Pool placed outranks one it
   declined; `max` keeps the first of equals, so single-target declarations read as before.
3. **`docs/DEMO_SCRIPT.md`, `README.md`, `apps/web/src/api.ts`** — the rehearsal's detergent pair
   ($398.92 / $367.84) is the arithmetic of a four-unit declaration while step 6 says to keep the
   default of two, where the screen reads $306.73 / $275.88 — a breach of the script's own rule
   against quoting a number not on screen. The README's prose still said "twenty-four-endpoint API"
   beside a table this branch corrected to 29 of 45. And `api.ts` had two orphaned doc comments:
   `demoConfig`'s description sat above `runReport`, and `liveAgent` carried two.

**AWS / external services touched**
None. Local only: the offline deterministic planner, the in-memory repository, simulated payments
and the simulated purchase executor. `AGENTCORE_RUNTIME_ARN` was unset throughout, so the live
action was unavailable rather than declined.

**Cost-relevant activity**
Zero. No Bedrock or AgentCore invocation, no deployment, no CDK synth against an account, no live
or test Stripe call, no schedule created. `/api/health` confirmed `model_provider: offline` on the
server used for browser QA.

**Agent behavior**
A member run with three declarations completes in **7 model iterations and 6 tool calls** against
bounds of 8 iterations / 25 tool calls / 2 duplicates — so the cap of three declarations sits one
below the iteration bound rather than on it. A fourth declaration is reported as
`not_investigated` rather than given an invented reason. Verified that no read path constructs a
coordinator: `PoolCoordinator` is built only by `/api/agent/run`, so the report, product search and
the current outlook cost no tokens.

**Validation**
`make qa` green on the merged `main`: **904 backend, 75 infra, 86 web**, Ruff, `tsc -b`, ESLint,
production build, secret scan, and `git diff --check` clean. Canonical reconciliation re-measured
from a fresh showcase run: 11 membership rows, 10 locked buyers, 1 retained `authorization_failed`,
1 replacement restoring exactly 24 funded units, 2 cases, 0 surplus, merchandise $756.00, host
$44.68, processing $28.06, fee $32.70, all-in $861.44 against $1,127.76 retail, saved $266.32 at
23.61%, pickup North Hall lobby, 8 members/18 units due plus 2 members/6 units pulled forward at
discovery. The seeded world still reaches four distinct verdicts across six products (whey 24/2
cases, coffee 18/18 in 3 cases at 17.22%, energy 16/16 in 2 cases at 14.73%, detergent
`not_cheaper` at −11.18% *with* 12 ≥ 12 units so the refusal is genuinely economic, towels
`below_minimum` at 4 vs 48, chocolate whey `no_bulk_offer`). Tier attribution checked against a
constructed disagreement — a price ceiling of $35 between the $31.50/24 and $39.80/12 whey tiers —
in both directions: the winner's own `matched_units`/`minimum_units` are reported and the rejection
list follows the winning offer, with no declaration both accepted and rejected. Persisted evidence
and the report were scanned for every other household's name, id, email and payment reference:
none. Browser QA at 1280×720/1000 and 390×844 through fresh onboarding, category search, two
declarations, the pre-run screen, `Run Pool now`, *Why this worked*, the towels refusal, the Needs
"as things stand" outlook, showcase entry, the full scripted lifecycle and showcase exit; no
horizontal overflow, and the visitor's account, declarations and both pools were byte-for-byte
unaffected by the replay (visitor 34 needs / 2 pools; showcase 32 needs / 1 completed pool).

**Failures / dead ends**
The first attempt at the App-level regression test asserted the drawer opener by accessible name;
testing-library resolves it to the community name where the browser resolves the `title`, so it
queries by title instead. The demo-script assertion also failed initially because a plain whitespace
join leaves a blockquote `>` inside the quoted sentence — the flattener drops those tokens now.

**What we learned**
Showcase isolation has two halves and only one of them is on the server. The partition is
server-derived and correct; *which* partition the browser asks for is one module-level flag, and a
second copy of "enter showcase mode" was enough to desynchronise the screen from the world. The
general lesson is that when a flag decides which world every request addresses, moving the screen
and moving the flag have to be one function, not two call sites that agree today.

**Article fodder**
Article 3 — the run report's precedence bug is a clean example of the difference between a true
sentence and an answer. Every word of "nobody near you has declared anything compatible" was true
of the product it described; it was still the wrong thing to tell someone whose order had just
formed without them.

**Evidence worth preserving**
The live before/after of the showcase counts (34 → 31 standing needs on the same screen), and the
tier-disagreement output showing 32/24 from the winning tier versus 29/12 from the loser.

**Relevant commits / files**
`6ae2d82` showcase scope + `apps/web/src/App.test.tsx` · `7a9d534` script and README figures,
`api.ts` comments, `test_presentation_truth.py` · `8e03505` `run_report._most_telling` +
`test_run_report.py` · merge `ef5547b`.

---

### #0048 — [2026-08-19] — Deploying the member trigger, and the 500 only DynamoDB could produce
`[AWS]` `[COST]` `[AGENT]` `[DEMO]` `[SECURITY]`

**Goal / user intent**
Deploy the reviewed `main` (#0047) to AWS, update the AgentCore runtime so it understands
`member_scan`, and spend the minimum number of paid invocations needed to prove the real causal
path: browser → Lambda → AgentCore → Bedrock → typed tools → deterministic services → DynamoDB →
API readback. Not another audit, not new features.

**Starting state**
`main` and `origin/main` both `54899fb`, working tree clean, `fix/consumer-result-relevance`
retained at `8e03505`. Deployed: `PoolDemoStack` last updated 2026-08-18T18:57Z from `719585a`,
and AgentCore runtime `Pool_PoolCoordinator-TmVqSN9H56` at **version 4** (2026-08-18T05:43Z).
Sixteen commits had touched `services/agent/` since that runtime was built, and `member_scan`
entered `agentcore_app.py` in `d23e2dd` — so the deployed runtime predated the trigger, exactly
as expected. Credentials: `pool-dev`, `arn:aws:iam::860325090409:user/pool-admin`, `us-east-1`.

**Decision**
Deploy the runtime **first**, then the demo stack. The deployed Lambda sent `LIVE_TRIGGER =
"manual"`, and the new allowlist keeps `manual` — so a runtime-first order is backward compatible
and leaves no window in which the public demo is broken. The reverse order would have put a
`member_scan`-sending frontend in front of a runtime that rejects it.

**Implementation**
Both components deployed from the same commit, and both diffs were reviewed before applying.
Each was a single code-asset change: no IAM statement, no environment variable, no resource
replacement, no DynamoDB touch. Runtime **4 → 5 → 6** (5 was the reviewed `main`; 6 carried the
fix below so both components run identical application code). `PoolDemoStack` updated only
`DemoApi`. Status: deployed.

One fix, committed as `09f06ce`. `DynamoDBRepository._get` handed a caller-supplied empty id
straight to `GetItem`, which rejects an empty key attribute (`ValidationException … cannot contain
an empty string value. Key: sk`). `InMemoryRepository` answers `None` for the same lookup, so
`POST /api/needs` with `household_id: ""` was a clean 400 "unknown member" locally and an uncaught
**500 on the deployed function**. The guard now lives in `_get`, where both backends have to
agree, and `FakeTable` in the test suite enforces the real service's rule so the divergence is a
test failure rather than a production incident. Verified live afterwards: the same request now
returns 400.

**AWS / external services touched**
CloudFormation (`AgentCore-Pool-default`, `PoolDemoStack`), Bedrock AgentCore Runtime, Bedrock
(Nova Lite), Lambda, DynamoDB `pool-demo-state`, S3 staging bucket, CloudWatch Logs, X-Ray.

**Cost-relevant activity**
**Three paid AgentCore invocations, where one was planned.** All three were member-triggered runs
on Nova Lite; none created a schedule or any always-on resource.

Two were unintended and are recorded because they were a real mistake, not a rounding error.
`POST /api/demo/agentcore` takes `action` as a **query** parameter defaulting to `member` and
accepts no request body. Two probes intended to test refusal paths sent their arguments as JSON
bodies, which were silently ignored, so both executed as default member runs:
`run_37151a982fb5` (4,916 in / 116 out) and `run_7a680bc1abe1` (4,944 in / 134 out). Both landed
in a throwaway workspace whose consumer had no declarations, so both truthfully returned
`no_action`. The lesson is narrow and worth keeping: *read the endpoint's signature before probing
a paid endpoint* — a body that cannot be read is not a safe probe, it is an unguarded default. The
compensating fact is that they proved the deployed runtime accepts `member_scan` before the
planned run was made.

The planned run, `run_fa577891fcd5`: 7 iterations against a bound of 8, 7 tool calls against 25,
29,701 input / 568 output tokens, 7,415 ms inside the agent, 13,258 ms inside AWS. Everything else
verified in this pass was free — the deterministic showcase, the offline coordinator, every read
endpoint, the refusal probes on `/api/agent/run`, and the whole browser walkthrough.

The staging bucket grew from 36 objects / 545 MB to **43 objects / 648 MB** across three deploys;
the ledger is updated. `agentcore deploy` re-issued its account-level X-Ray `UpdateIndexingRule`
(`ModifiedAt` moved to 2026-08-19T19:26), setting the same 100 % it already held — no effective
change, and the Q18 decision stands, but it confirms the CLI touches account configuration on
every deploy, not only the first.

**Agent behavior**
Model `us.amazon.nova-lite-v1:0` on Bedrock via AgentCore Runtime, `member_scan`, objective kind
`member`, two declarations (`need_4c2ea8c5dc04` whey 2 tubs, `need_9e3ca3e52bc2` towels 2 packs),
both `exact_only`. Tool sequence: `list_latent_demand` → `evaluate_pool_economics` ×2 →
`create_candidate_pool` → `find_host_candidates` → `request_host_acceptance` →
`issue_final_offer`. Terminated `completed`, one HITL decision created (the host offer), which is
correct for a member on Ask Me.

The most useful thing the run did was fail an action. `issue_final_offer` returned `ok=true` with
`issued: false` — *"no host has accepted this pool yet"*. The model chose a consequential action
and deterministic code refused it, inside an otherwise successful run. That is the architecture
rule observable in production rather than asserted: the model decides what to attempt, and
deterministic code decides what is true.

**Validation**
`make qa` green on `09f06ce`: **905 backend** (904 + the new regression), **86 web**, Ruff,
`tsc -b`, ESLint, production build, secret scan, `git diff --check` clean. The new test fails on
the pre-fix code, which was checked by reverting the guard and re-running it.

Causality was proven at the storage layer rather than inferred from the response. Before the run
the live workspace held `RUN` 0, `RUN_EVALUATION` 0, `POOL` 0. After it: exactly one `RUN`
(`run_fa577891fcd5`), **two `RUN_EVALUATION` rows whose sort keys embed that run id**, one `POOL`
(`pool_08e7ecf6ce7d`), ten `MEMBERSHIP` rows including the member's own `hh_navarro`, and one
`DECISION`. `pool.created_by_run == run_id`, `relation_verified: true`, `same_workspace: true`.
The two earlier accidental runs had already demonstrated the shared partition from the other
direction: rows written by the AgentCore process, read by the Lambda.

The persisted evaluations, read straight out of DynamoDB, carry the deterministic facts the run
computed: whey `viable`, 31 matched against a 24 minimum, 16 current + 8 future units, 24
selected across 10 members, 2 cases, 0 surplus, North Hall lobby from 4 sites considered, and
`offers_considered` recording 3150 selected over 3980; towels `below_minimum`, 6 against 48, not
included. A fresh `GET /api/runs/{id}/report` **100 seconds after the runtime returned** came back
in 293 ms with those same facts — including all six *Why this worked* sentences and the towels
refusal — and answered both declarations, one of them "no".

That no second model call produced the report is structural, not observational: the API Lambda's
role grants five DynamoDB actions, `bedrock-agentcore:InvokeAgentRuntime` on one runtime, and
`AWSLambdaBasicExecutionRole`. It holds **no** `bedrock:InvokeModel`. The function that serves the
Run Report cannot call a foundation model. One user action produced one invocation, confirmed in
the runtime log: the four matching lines around the run are two copies each (`otel-rt-logs` plus
the per-session stream) of **one** session.

Canonical invariants intact on the deployed stack, from a showcase replay in its own partition:
11 membership rows, 10 locked buyers, 1 retained `authorization_failed`, 24 funded units, 2 cases,
0 surplus, merchandise $756.00, host $44.68, processing $28.06, fee $32.70, all-in **$861.44**
against $1,127.76, saved $266.32 at 23.61 %, pickup North Hall lobby. The visitor's own partition
was byte-for-byte unchanged by that replay. Separately, the live pool converged on the same
$861.44 / $1,127.76 / $266.32 / 23.61 % / 24 units / 2 cases / 0 surplus once the host accepted.

Sourceability on the deployed search: `coffee` leads with the sourceable Pike Place, `death wish`
returns only Death Wish, `folgers coffee` keeps five Folgers rows ahead of the sourceable option
at sixth, and `shampoo` fabricates nothing.

**Failures / dead ends**
Two, besides the paid-probe mistake. Running `npx aws-cdk diff` directly instead of through `make`
dropped `AGENTCORE_RUNTIME_ARN` from the environment, and the diff showed it would have **removed**
the `InvokeAgentRuntime` grant and blanked the ARN — shipping a demo with the live action silently
off, which is precisely what the Makefile comment warns about. Caught because the diff was read
before it was applied; the lesson is that the deploy path is the Makefile, not the CDK CLI.

Browser QA against the deployed Function URL was **not possible from this environment** — the
domain is blocked by the sandbox's policy and no Chrome instance was attached. The walkthrough was
therefore done against the identical Lambda bundle served locally in the same public-demo mode
(offline planner, live action off), the approach #0035 used under the same constraint, while every
data-level and causal claim above was verified against production over HTTP. That split is stated
plainly rather than papered over: nobody has yet watched the deployed React app render this run.

**What we learned**
A repository whose entire test suite runs on one storage backend cannot see the other backend's
error semantics. The 500 was not a logic bug — the validation was correct and the message was
right — it was two adapters disagreeing about how to say "that row does not exist," and only the
deployed one could say it wrong. The general form: when two implementations of the same protocol
are swapped by configuration, the *fake* has to be as strict as the real service, or the suite is
green about a behaviour it never exercised.

**Article fodder**
Article 2. The strongest paragraph available on AWS is the negative permission: the reason a judge
can trust that the Run Report was not re-generated by a model is not a log line, it is that the
function serving it has no model permission at all. Provenance by IAM rather than by assertion.
Article 3 gets `issue_final_offer` refusing itself mid-run.

**Evidence worth preserving**
The pre/post DynamoDB partition counts either side of one button press (0/0/0 → one run, two
evaluations keyed by that run, one pool, ten memberships), and the Lambda role's policy document
next to the Run Report it served.

**Relevant commits / files**
`09f06ce` `pool/adapters/repository.py` + `tests/test_persistence_and_termination.py`. Deployed
from that commit: AgentCore runtime version 6, `PoolDemoStack` `DemoApi`.

---

### #0049 — [2026-08-19] — Cashing "Pool keeps watching": the same demand, three answers
`[DEMO]` `[ARTICLE-1]` `[FRONTEND]` `[SECURITY]`

**Goal / user intent**
Pool could truthfully refuse an order and tell a member their declaration stays standing. Nothing
ever demonstrated that the refusal was a *current* answer rather than a permanent one — so a judge's
honest next question, "watching for what?", had no reply. Make the changing-world claim
demonstrable: standing demand that outlives a run, an external condition that changes, and a
re-evaluation that reaches a different verdict without anybody being recruited.

**Starting state**
`main` at `360aee7`, clean, one commit past the live AgentCore rehearsal. The seeded world could
refuse for three reasons — below minimum, no case fit, bad economics — every one of them an answer
Pool reaches *after* a supplier has quoted a price. The state it had no example of was the one a
coordination system spends most of its time in: people want the thing, and there is nothing to buy
it from.

**Decision**
Four decisions, in the order they mattered.

1. **Missing supply is not missing demand.** `standing_demand_for` returned its empty base row —
   zero compatible members, zero compatible units — whenever there was no sourceable target. New
   `discovery.unsourced_demand` computes what the matcher would compute, against the declared
   product, with no unit price, because there is no offer.
2. **A seeded product for the class.** Jasmine rice, 5 lb: six independent declarations, 22 bags, a
   shelf price, and no bulk tier.
3. **The world changes through one `Offer` row.** `services/supplier_updates.py` holds two
   server-owned quotes; the client sends an allowlisted key and never a number.
4. **Two quotes, not one.** A single quote that turns a no into a yes is an answer key.

**Why**
The mechanism is deliberately not a simulation mode. An `Offer` row is what every price in this
system already comes from, so the verdict after recording a quote is not written down anywhere —
the ordinary evaluator sees an ordinary offer and reaches whatever the arithmetic supports. A
scenario flag would have needed the evaluator taught about it, and at that point the demo proves
the flag rather than the system.

`OfferSource.MANUAL_VERIFIED` was rejected in favour of `SYNTHETIC`. It is the closer match for the
*act* — an operator did enter these — and the wrong label for the *fact*: Operations renders it as a
green "manual verified" chip meaning a human confirmed a real quote with a real supplier, and
Riverbend Wholesale does not exist. Lending real provenance to an invented price is exactly what
`OfferSource` and `ProductSource` are kept apart to prevent.

**Implementation** — *tested*, local only.
- `discovery.unsourced_demand` + `UnsourcedDemand`; wired into `standing_demand_for` and the
  `no_supply` branch of `relevance.need_outlook`, which now reads demand first and blocker second.
- `prod_rice_jasmine` in `data/seed.py` and `scripts/build_catalog.py` `CURATED`; retail offer only.
  Catalogue entry inserted by replicating the generator's own curated emission — the file
  round-trips byte-for-byte, verified before and after.
- `services/supplier_updates.py`; `GET`/`POST /api/demo/supplier-updates`, both allowlisted for
  judge mode. Public surface is now 31 of 47 endpoints (was 29 of 45); README and the module
  docstring updated with it.
- `views/operations.tsx` "Supplier updates" panel — operator surface, leads with the standing demand
  rather than the button.

**Two defects fixed on the way in.**
- Home → Needs → Home lost the member's own state. `navigate` called `forgetWorkspaceState` on every
  view change, and the refetch effect is keyed on counts that do not move when a member changes
  screens — so the state was cleared and never re-asked. Needs was worse than reported: its "As
  things stand" line never rendered at all.
- A member-triggered no-op logged "Pool ran a background scan and found nothing worth acting on",
  on the one screen that states plainly that nothing is scheduled. `_run_summary` had
  `objective_kind` on the record already and was not reading it.

**A third defect the new tests found.** `run_report._result_for_need` reported
`formed_included` whenever the member was currently in a pool for that declaration —
whichever run formed it. So the first run's report, which had truthfully refused for want of a
supplier, silently became a claim that it had formed the order the moment a second run did. The
stored `RunEvaluation` rows were byte-identical throughout; the rewriting was in the assembly, which
is worse, because nothing in the evidence looks wrong. Attribution now reads stored lineage —
`Pool.created_by_run`, or an evaluation this run wrote naming a pool it acted on. Both already
existed; neither was being consulted.

**AWS / external services touched**
None. No deploy, no AgentCore invocation, no Bedrock call, no live payment. The catalogue insert was
done offline against the committed snapshot rather than by re-running the fetcher.

**Cost-relevant activity**
None. The new endpoint is deterministic and stateful; it spends no model tokens and has no path to
one. It takes the existing workspace mutation lease and the existing per-session action quota.

**Validation**
- `make qa` green: ruff, 926 backend pytest, 75 infra pytest, 97 web vitest, tsc, eslint, production
  build, secret scan, `git diff --check`. Baseline was 905 / 75 / 86.
- Every bug fix was verified to *fail* before the fix by reverting the source file and re-running.
- Browser QA in judge mode (`POOL_PUBLIC_DEMO=true`, offline planner, AgentCore off) at 1280px and
  390px: onboarding → declare through the real catalogue search → refusal → Home/Needs/Home →
  quote A → outlook moves with no run → quote B → outlook ready → second run forms the order.
- Observed end to end in the browser: 38 needs before and after, the six seeded rice declarations
  unchanged, and the first run's report still `declined / no_bulk_offer` after two quotes and a
  second run.
- Canonical showcase re-verified in its own partition: 11 memberships, 10 buyers, 1 authorisation
  failure, 24 units, 2 cases, 0 surplus, $861.44 against $1,127.76, $266.32 kept, 23.61%.
- Deterministic outcomes, all read from the evaluator: no quote → `no_bulk_offer`; split-case →
  `not_cheaper`, $286.66 against $275.76; case-programme → viable, 24 units, 3 cases, 0 surplus,
  $208.72 against $275.76, 24.3%.

**Failures / dead ends**
- First attempt at the split-case quote used a 2-unit case with a 6-unit minimum. `fit_to_cases`
  caps its search a few cases above the minimum, so it took 12 of the 20 available units and lost by
  21% — a refusal explained by an implementation bound rather than by economics. Reshaped both
  quotes so each takes the whole buyer set, which makes the comparison purely economic.
- Seeded quantities were 3 bags each at first. With a 2-bag default declaration the judge could
  never land inside a whole case, so they were excluded from their own demo. Mixed quantities
  summing to 22 fixed it, and the arithmetic still decides.
- Recording a quote left Home stale: the mutation deliberately writes nothing the shell's change
  detection counts. Fixed with an explicit signal rather than by having the server write a row it
  does not need — but the first version of that reused the effect that also clears the run report,
  which wiped the previous run's answer off the screen. That is the one thing here meant to survive
  the world changing. Clearing is now its own effect. Reverting the split fails a test.

**What we learned**
The interesting failure mode in an agent product is not a wrong number; it is a *retrospectively
consistent* one. Two of the three defects here were the interface quietly making the past agree with
the present — a report that reassigned itself to a later run, and a screen that reported missing
supply as missing demand. Neither touched a stored value. Keeping "what that run found" and "what is
true now" as separate, separately-labelled answers is what makes the changing-world claim provable
at all, and it has to be defended in the assembly layer, not only in the store.

**Article fodder**
Article 1 — latent demand is a standing fact and coordination is an ongoing job, not a search
query; "no" as a timestamped answer. Article 3 — an operator action a member deliberately cannot
take, and why the client sends a key rather than a price. Demo — the whole spine of the rewritten
script.

**Evidence worth preserving**
The two-panel Home frame where the run report says *no supplier* and the standing card says *the
supplier's best price starts at 16*, with nothing having run between them. The Operations panel at
390px. The three evaluator verdicts with their economics.

**Relevant commits / files**
Branch `feat/changing-world-demo`: `55b495c` `70d7ba9` `e20dcc5` `88c2d83` `0348a62` `8143948`
`74aa9d4` `861e3c6`. `services/supplier_updates.py`, `services/discovery.py`,
`services/relevance.py`, `services/run_report.py`, `data/seed.py`, `api/app.py`,
`api/public_demo.py`, `views/operations.tsx`, `views/home.tsx`, `App.tsx`,
`tests/test_supplier_updates.py`, `docs/DEMO_SCRIPT.md`.

---

### #0050 — [2026-08-19] — The product says less, and the engine says more
`[FRONTEND]` `[DEMO]` `[DOMAIN]` `[SECURITY]` `[ARTICLE-1]` `[ARTICLE-3]`

**Goal / user intent**
The system was semantically correct and the *product* was not readable. Turn the deepest build so
far into the simplest expression of it, without weakening anything underneath: the interface should
get simpler by representing the engine better, never by hiding what it does.

**Starting state**
`feat/changing-world-demo` at `26ad326`, clean, 927 agent + 75 infra + 97 web green. Everything
below was measured in a real browser at 1280×720 and 390×844, 100% zoom, before any code changed —
because the shape of the problem was not visible from the source.

**The three findings that decided the whole pass**

1. **Home said the same thing three times.** After a run with two items it listed each declaration
   under `POOL CHECKED` with a verdict, again under `Still standing` with demand and a blocker, and a
   third time under `What you buy anyway` with a cadence — which was also, field for field, the whole
   of the Needs page. Two items made six rows and 2.17 viewport-heights, the primary button sat below
   the fold, and the scroll fell between the demand and the blocker that explained it.

2. **The centrepiece beat was one number, moving the wrong way.** The changing-world sequence is the
   strongest argument this build makes. On Home the entire visible difference between "no supplier",
   "supplier found, still not worth it" and "viable" was the tail of a sentence: `With yours, 24.`
   → `…The supplier's best price starts at 12.` → `…starts at 16.` The good quote makes the number go
   **up**, because the case-programme minimum is higher. The actual verdict — *there is enough demand
   and it still would not be cheaper* — rendered only on **Needs**, on a different screen. Captured
   from the baseline worktree for the atlas, the two screens are byte-identical at 1539 px except
   `12` becoming `16`.

3. **Thirty-six units of coffee demand produced nothing.** Run against the real engine: twelve
   members, three units each, all buying some coffee, supplier minimum eighteen. Nine of the twelve
   were discarded at `domain/substitution.py:61-62` as "member accepts the exact product only" before
   timing or geography was consulted, because each had named a different brand. `below_minimum`, nine
   matched units against eighteen. The product whose thesis is *Pool notices overlapping demand* was
   configured so that overlapping demand did not overlap.

**What we did**

*Domain — a member can now say what they buy.* `SubstitutionPolicy.GROUP_DECLARED`, and it is
deliberately **not** a substitution rule: the others answer "I named this product, what else may
serve it", and this one says "I named a family". That distinction is why `CompatibilityVerdict` now
separates `is_exact` — a fact about two product ids, stored on the membership, which has to keep
meaning what it says — from `requires_disclosure`, a fact about what the member expected. Being
handed Pike Place is a substitution only if you asked for something else, and Smart Join no longer
asks anybody to approve their own declaration. The catalogue emits its 20 curated families with
labels and exemplars; the pool still buys one exact product. Nothing was loosened — exact-only is
untouched, the empty-group gate still fails closed (and `test_catalog.py`'s parametrisation over
`list(SubstitutionPolicy)` covered the new member automatically, which is the most valuable existing
guardrail in the repo).

*A consumer grammar.* Five words — needs you, coordinating, ready to collect, watching, done — with
the specific fact as the reason underneath, decided in `services/relevance.py` so no screen can
re-derive it and disagree with another screen. The deterministic `state` field is untouched; these
are a reading of it. `case_boundary` split out of `not_matched`, because those were opposite news
wearing one word: a matcher rejection means nothing near you can serve this, a case boundary means
the order happened and was full. "Nothing nearby fits this one" was the most misleading sentence
Pool had, and it was shown to the person whose neighbours had just bought the thing they wanted.

*Home.* One row per thing you buy, and the row evolves. State, then how many people near you buy it,
then what is stopping it, then what the last run found — dated, and shown only when the answer has
actually changed, compared on reason codes rather than prose. 2.17 → 1.08 vh, and it no longer grows
when a run happens. The community counters, the activity feed, the second copy of the member's own
list and the four-clause caveat all left; every clause of that caveat is now a reason on the row it
applies to.

*Information architecture.* Community could not finish "this page exists so a member can ___" — 3.45
vh of eight sections in which nearly every figure read `$0.00` — so it left the nav and became
**Behind Pool**, one door from the footer, opening with an index of what can be inspected. Five
different labels used to lead to the technical proof from three different drawers. `Pools` → `Orders`
for the collision the vocabulary audit found; `Needs` → `What you buy`, the question onboarding
already asks; `Run Pool now` → `Ask Pool to check now` everywhere.

*Whose order is this.* Home was already careful — "your units were not in this one" — and one click
later the list said `6 buyers · 18/18` with no marker and the record said `everyone still in`. Both
surfaces state it now, either way, from `relevance` and never inferred. And the case boundary is
**drawn**: full cases as boxes, the reader's units inside, the remainder dashed outside. Three
sentences of arithmetic became a picture in which "no speculative surplus" is visible.

*Ingestion.* Two committed sheets under `demo-data/`, really parsed by `csv`, with rows that fail
and name their line. The conflict is the interesting part: this build refuses client-submitted
economics on purpose, and an open upload endpoint hands that authority straight back. So one question
became two — *is the pipeline real* (always, everywhere, before permission is consulted) and *whose
numbers may become offer rows* (on a public deployment, only bytes whose digest is committed). A
judge downloads the file, uploads it, watches it parse; edit one price and it is refused with the
reason named while still being shown what the file contained.

*The map.* It was dots on grey with `preserveAspectRatio="none"`, so the one thing a map is for — how
far apart things are — was the thing it got wrong. It now draws `WALKABLE_PICKUP_KM` as a ring around
each pickup point, read from the server which reads it from `coordination`, with longitude corrected
for latitude. No tile service: Demo University does not exist, and putting invented households on a
real street map would be a more convincing lie rather than a better map.

**Verification**
`make qa` green: **975 agent + 75 infra + 106 web = 1,156**, from 1,099. Ruff, tsc, eslint, production
build, secret scan clean. Bundle 350.37 kB JS / 42.24 kB CSS gzipped to 103.61 / 8.96 — **no new
runtime dependency was added**. Sixteen matched before/after pairs captured from a git worktree at
`26ad326` running its own API on its own port, at identical viewports and device pixel ratio.
Rehearsed three times end to end from a fresh workspace: twelve recorded beats each, byte-identical
after normalising the greeting and the wall clock, setup within ten milliseconds across runs. No AWS
deploy, no AgentCore invocation, no Bedrock call, no live payment.

**Failures / dead ends**
- Flipping the default to `STRUCTURED_CATEGORY_MATCH` produces the right pools and the wrong
  sentences: every member gets told "a substitute for the Pike Place you declared" when they never
  asked for Pike Place, and it silently widens authority on declarations already stored. A default
  that makes the app apologise for doing what somebody wanted is the wrong default.
- One CSV containing both quotes lands them together and skips the refusal, which is the half of the
  sequence that makes it evidence rather than a switch. Two sheets, and the manifest states the order
  rather than leaving it to filename sorting.
- Removing Home's run-report section made a `formed_excluded` declaration vanish from the screen: the
  result carries the pool id of the order that filled *without* those units, and the standing filter
  read that as served. An unrelated card announced an order existed elsewhere while the thing the
  member asked Pool to watch was nowhere. Found in a browser, not in a test.
- The same row then told that member "nobody else near you buys this yet", because
  `compatible_members` excludes households already in a live pool — the right number for how much
  demand is available, and the exact misreading the demand line exists to prevent.
- Two endpoints and two public allowlist entries pushed `test_public_demo`'s reduction ratio past its
  threshold. The temptation was to move the threshold. The metadata endpoint describing the fixtures
  turned out not to be needed by the browser at all — the path is a constant, the digests are in the
  repository — so it came off the allowlist instead, and the guard holds honestly at 32 of 49.
- A rehearsal matching "The host accepts the job" silently skipped the host step and worked the queue
  with no host, which is not a sequence a presenter performs. The drawer names the host Pool actually
  ranked — "Gio M. accepts the fulfilment job" — which is better product behaviour and a worse
  selector.

**Two defects the pass found rather than introduced**
- `POST /api/demo/supplier-updates` had no showcase guard, and the Operations console was reachable
  from inside showcase mode. Recording a rice quote wrote a bulk offer into the recording whose every
  quoted figure — 24 units, 2 cases, $861.44 — is a claim about *that* world. Proved by curl before
  fixing it. Refused server-side now, and the door removed from the client as well.
- `discovery.latent_demand` ranked a family's target on demand alone, so it could propose the coffee
  most people named over the one a supplier will actually sell, and `evaluate_opportunity` would then
  refuse it for `no_retail_baseline`. Survivable while exact-only declarations were rare enough to be
  outvoted; decisive the moment every declaration in a family is compatible. Sourceability now
  outranks demand.
- Smaller: `.panel-lead` was written on the first-use card and no such CSS rule ever existed, so the
  one screen whose whole job is the pitch rendered as an ordinary panel. Three stale endpoint counts
  in the README, `ARCHITECTURE.md` and the architecture diagram, plus a docstring still saying
  "twenty-four allowlisted paths" against a real 32.

**What we learned**
Reading the source tells you what the system computes; only rendering it tells you what it says. Two
of the three findings that shaped this pass were invisible in the code — a screen that lists one
thing three times looks like three correct sections, and a beat carried by a minimum-quantity number
looks like a correct number. And the most valuable single hour was running the engine against a
hypothetical (twelve coffee drinkers) rather than arguing about it: the thesis was falsified by its
own default, and no amount of reasoning about `substitution.py` would have produced the number
thirty-six.

**Article fodder**
Article 1 — the demand-fragmentation experiment, and a product whose default contradicted its
premise. Article 2 — splitting `is_exact` from `requires_disclosure`, and why an overloaded boolean
becomes an apology in the UI. Article 3 — real ingestion with content-addressed economic authority,
and the endpoint that came *off* the allowlist to keep a guard honest.

**Evidence worth preserving**
The matched pair after each supplier sheet: identical before, `Supplier found — not cheaper` then
`Worth doing` after. The case-boundary drawing with two dashed units outside three full cases. The
import panel showing a real digest, real byte count, and `line 2: unit_price_cents is not a whole
number: 'oops'`. The three rehearsal transcripts.

**Relevant commits / files**
Branch `feat/final-experience-rebuild`: `90837ba` `ca4ed6e` `686c596` `49859d8` `a883395` `e95c46b`
`effeb49` `f932f40` `b013811` `e0988e9`. `domain/substitution.py`, `domain/models.py`,
`domain/policy.py`, `services/relevance.py`, `services/discovery.py`, `services/needs.py`,
`services/supplier_import.py`, `data/catalog.py`, `scripts/build_catalog.py`, `api/app.py`,
`api/public_demo.py`, `demo-data/`, `views/home.tsx`, `views/community.tsx`, `views/pools.tsx`,
`views/pool.tsx`, `views/onboarding.tsx`, `views/operations.tsx`, `product-search.tsx`, `chosen.ts`,
`ui.tsx`, `styles.css`, `docs/FINAL_EXPERIENCE_PLAN.md`.

### #0051 — [2026-08-19] — The Showcase stops being a log, and colour goes back to meaning one thing
`[FRONTEND]` `[DEMO]` `[ARTICLE-2]` `[ARTICLE-3]`

**Goal / user intent**
Finish the experience: make the canonical lifecycle read as one causal story, give Behind Pool a
hierarchy built for a judge rather than one inherited from the old Community tab, make the order
record answer a member's questions before an operator's, and use motion only where it explains
something. No product architecture reopened.

**Starting state**
`feat/final-experience-rebuild` at `1188edf`, clean. Measured in a real browser at 1280×720,
1440×900 and 390×844 before anything changed — 18 surfaces, full-page, zero console errors, zero
failed requests. Two Impeccable `critique` sub-agents reviewed the Showcase independently (design
review; detector plus browser evidence) and their findings decided most of what follows.

**What the baseline actually showed**

1. **The Showcase paginated a causal chain.** One step per page, thirteen `Continue` clicks, and a
   fourteen-segment ruler of unlabelled 15×32 px hairlines — under WCAG 2.5.8's 24×24 minimum, at
   **1.56:1** against the paper, and sixteen tab stops ahead of the primary control. The centrepiece
   was invisible: page 07 said "2 units stopped counting", page 08 said `24 / 24`, page 09 said
   `24 / 24` again captioned "whole again". Two pages printed the identical figure while one claimed
   a repair, and nothing on screen ever fell. `CaseFit` — a component this design system invented
   for exactly this argument — was never called, on the surface that asserts "still exactly two
   cases".

2. **The 14-step/13-chapter mismatch was worse than a count.** `member_declared_need` fires on every
   successful run and had no authored chapter, so it fell through a fallback that cut a headline out
   of the server's sentence at its first comma — *"You told Pool she buys 100% whey protein"* — printed
   eight raw identifiers including `declared_by: scenario`, and tagged a person's act `COMPUTED`.
   Second page of fourteen, on the surface whose entire thesis is attribution. Meanwhile the one
   authored chapter with no matching step, `lock_blocked`, is reachable only on failure.

3. **The order record was less use to a member than the summary that linked to it.** Home said
   "Your 2 bags · about $17.53 instead of $22.98 buying alone"; one click later the record opened on
   `Units 24 / 16`, `0 units authorized`, an em dash under "Estimated saving", and
   `View all 11 deterministic checks` — with the member's own quantity absent entirely.

4. **Behind Pool ignored its own index.** It opened with "what you can inspect" and then ran
   attention → inherited Community enablement → map → an actionable host decision → a money ledger of
   **five $0.00 rows** → the activity feed. The feed is the best evidence for the autonomy claim and
   it was last. A test already forbade printing three zero figures for precisely this reason; the
   five-row ledger below them had never been held to it.

**What we did**

*The Showcase became one sheet.* No pagination. A sticky spine draws the quantity as case-fit cells
and follows the reader's position — never a clock, because the run finished ~40 ms before the first
frame. Twelve labelled acts replaced fourteen hairlines. Every step is present, with the figures of
the three that *are* the causal chain open by default. The closing claim came out of a collapsed
`<details>` and became a panel with two real buttons. `member_declared_need` got an authored chapter,
`["human"]`, and a body in consumer language with the identifiers behind a disclosure; the fallback
no longer derives a headline from prose, so no future unmapped step can be cut mid-clause.

*The order record answers five questions first* — what you get, what you pay, where you collect it,
what happens next, whether Pool needs anything from you — in the voice Home already used. The
five-tab strip became five `<details>` sections, all shut, deep-linkable, so `see it run on AWS`
still lands on the evidence. The pool arithmetic is kept and demoted one line.

*Behind Pool got a spine:* the autonomy counts, then the one question it had to ask, then every
action with its actor, then a new **What proves it** section — deterministic result, the agent's
stored tool sequence, `created_by_run` read back from the same workspace, the runtime and model, and
supplier provenance naming Riverbend Wholesale as synthetic — then what it produced, then the
community it ran inside. The ledger of zeroes is suppressed until money moves.

*Colour went back to meaning one thing.* Moss had spread across ~30 selectors as a general
affirmative — done ticks, ok chips, ownership marks, ledger gains, map rings, an emphasised hero
word, and the environment dot on every screen — while graphite drew the global focus ring and
ordinary banner chrome. On the Showcase that was self-refuting: the legend says a green diamond
means *the agent decided*, three inches above thirteen green read-progress segments and five
engine-computed figures. Success and ownership → `ink`; caution and chrome → `ink-muted`; genuine
breakage → `stop`; generic focus → `ink`. Every actor hue that survives is an attribution.

*Motion, twice, both reporting a change that happened.* The spine's cells transition as the reader
moves between acts, and a consumer row's state word and reason lift for one beat when the reason code
actually changes — never on first paint, never on scroll. A test pins the first-paint rule.

**Verification**
`make qa` green: ruff, eslint, tsc, **975 agent + 75 infra + 112 web = 1,162**, production build,
secret scan, `git diff --check`. Impeccable detector: **0 findings** over `apps/web/src`.
**0 contrast failures across 444 distinct foreground/background pairs**, light and dark, over eight
surfaces including the order record fully expanded — worst 4.66:1 against a 4.5 floor; one genuine
pre-existing failure was found and fixed (`.prov-label` at 4.28:1 in dark). No horizontal overflow at
any of the three viewports. On the three rebuilt surfaces: **0 focus stops without a ring** and **0
targets under 24×24** at both desktop and mobile, where the Showcase previously had none at all
reaching 44×44 and fourteen at 15×32. `prefers-reduced-motion` collapses every animation to 1e-05s.
Showcase isolation re-proved in the browser: the visitor's pools, needs and name are byte-identical
before and after running the scripted lifecycle. **Three rehearsals from reset through the real
interface** — including the supplier sheets going through the console's real file input — produced 17
beats each, byte-identical after normalising the wall clock and ids, with 0 console errors. No AWS
deploy, no AgentCore invocation, no Bedrock call, no live payment: the local API runs
`model_provider: offline`.

**Failures / dead ends**
- Line-range surgery on `community.tsx` cut a JSX ternary in half twice. Splitting the return by
  *start anchors* and slicing between consecutive ones worked first time and is the technique to
  reuse: every block's end is the next block's beginning, so nothing has to be balanced by hand.
- `.sheet` was already the demo drawer's class — `position: fixed; width: min(420px, 100vw)` — so the
  new run sheet rendered 419 px wide inside a 1280 px page with six nested overflows. Renamed to
  `.runsheet`. A grep for the class name before choosing it would have cost five seconds.
- The disclosure marker was a flex item, then a grid cell. As a flex item it broke onto its own row
  when a title wrapped; as a grid cell it forced the hint onto a second row at every width and cost
  0.15 vh. Positioned out of flow, both layouts hold.
- Two "moss drift" sites turned out to be **correct** and were nearly destroyed: clay on "You are
  acting as X" is a person, and moss on `called #1, #2` is the agent's own tool choices. Checking the
  three ambiguous ones individually was worth more than the batch that would have flattened them.
- The first rehearsal harness sent `trigger: "member_requested"`, which is not in the server's
  allowlist, so every run silently fell through to the community-wide scan and formed Energy Drink
  pools for a member who had declared rice. It looked exactly like a product defect for twenty
  minutes. The allowlisted name is `member_scan`.

**Two things the pass found rather than introduced**
- `.prov-label` measured 4.28:1 in the dark theme — a real AA failure, pre-existing, invisible without
  sweeping every rendered pair.
- Behind Pool's five-row `$0.00` ledger, sitting directly beneath a test that forbids exactly that
  pattern three figures higher up. The rule was written down and the section below it had never been
  checked against it.
- Stale copy: "Run all **13** server stages" in the reader's empty state and "All **13** stages" in the
  drawer, both against a real fourteen. `run.tsx`'s "All thirteen checks" is **correct** — 11
  unconditional viability checks plus two more under `if final:` — and was left alone.

**What we learned**
A design system's colour rule is only worth what the implementation spends it on. The doctrine said
moss means *the agent decided*; thirty selectors said moss means *good*, and the surface that
displays the legend was the worst offender. Nothing detects that — the detector returned zero
findings on this repository both before and after — because every individual use looked reasonable.
It took writing the rule down as normative, then grepping the palette against it, to see that the
cheapest proof the product had was being spent on progress bars.

**Article fodder**
Article 2 — a paginated reader is a data structure choice masquerading as a UI choice; the fourteen
steps were a list, and the story was a quantity surviving a shock. Article 3 — attribution as a
visual primitive, and how it decays: the mechanism by which a semantic palette becomes a decorative
one is not a decision, it is thirty individually-reasonable ones.

**Evidence worth preserving**
The matched contact sheet, 19 surfaces, before and after at identical viewports. The spine at the
decline beat, two cells dashed in `stop` under the caption "Still 22 of 24". The three rehearsal
transcripts. The 444-pair contrast sweep.

**Relevant commits / files**
`apps/web/src/views/run.tsx`, `views/pool.tsx`, `views/community.tsx`, `views/home.tsx`,
`views/operations.tsx`, `views/demo-panel.tsx`, `styles.css`, `views/run.test.tsx`,
`views/community.test.tsx`, `views/home.test.tsx`, `PRODUCT.md`, `DESIGN.md`,
`.impeccable/design.json`, `docs/DEMO_SCRIPT.md`, `docs/IMPECCABLE_HANDOFF.md`.

### #0052 — [2026-08-19] — A judge can now check the claim themselves
`[FRONTEND]` `[DEMO]` `[SECURITY]` `[ARTICLE-1]`

**Goal / user intent**
The video can explain the product. The live app could not be *used* by somebody who had
never seen it: reproducing the central claim meant knowing to complete four onboarding
screens, find the Operations console, and go download a CSV from GitHub. Make the deployed
demo self-testable in about four minutes, without inventing a parallel fake demo.

**What we did**

*One endpoint, and it is a door rather than a shortcut.* Everything in
`import_supplier_quotes` after `data = await file.read()` moved into
`_ingest_supplier_bytes(ws, data, filename)`. `POST /api/demo/supplier-sample?name=` checks
the name against the manifest's own list, reads `demo-data/<name>`, and calls that same
function — so the parser runs on real bytes, the digest is checked against
`MANIFEST.json` exactly as it is for a stranger's upload, and the offer row is written by
the same code under the same lease and quota. The gate lives *inside* the shared function
on purpose: a convenience control that skipped it would be a second, weaker door onto the
one endpoint whose whole design is that nobody can set a price.

`/api/demo/supplier-file` was left alone. It deliberately does not serve the fixture bytes
and is deliberately not public, and its own comment says why — "serving the bytes from here
would invite the mistake of thinking the server made them up". Bundling the CSVs into the
SPA would have been the same mistake wearing a different hat.

*One view, two doors, no new navigation.* `views/judge.tsx` is a five-step checklist:
become a member, see the demand that pre-existed, watch a willing supplier get refused,
watch better terms change the answer, ask Pool to act. Reached from a card on the first
screen a fresh visitor already lands on, and from the footer beside Behind Pool. It is
allowed to render *before* onboarding — the only destination that is — because step 1
performs that setup through the same three endpoints the forms call.

**Three defects the browser found, none of which the tests could have**

1. **Nothing happened when a quote was imported.** An import writes one offer row and
   deliberately moves none of the counts the member read is keyed on — that *is* the
   no-demand-injection property — so the walkthrough went on showing the previous answer.
   There was already a mechanism for exactly this, `worldChanged`, added when the
   Operations console hit it; the judge view now uses it. Every rehearsal harness in the
   repository had been reloading the page after each import, which is why nothing had
   noticed.
2. **Finished steps rewrote themselves.** They rendered the *live* outlook, so once the
   order formed, the step whose entire point is "a supplier would sell and Pool said no"
   began reading "already coordinating this one". A judge scrolling back to check what
   they had just seen found it had changed. Each step now captures the server's answer at
   the moment it ran and shows that — the same historical-versus-current boundary the run
   reports keep.
3. **"1 people near you buy this."** The demand line read `compatible_members` live, and
   that field counts households *not* already in a live pool — the right number for "how
   much demand is available" and completely the wrong number for "seven people already
   wanted this", because after the run everyone who buys rice is in the order. Captured
   once, at the start. This is the third time this field has produced a wrong sentence
   (#0050 twice); the lesson is that it is a capacity number and never a population one.

**Verification**
`make qa` green: **980 agent + 75 infra + 119 web = 1,174**, ruff, eslint, tsc, production
build, secret scan, `git diff --check`. Five new server tests assert the door is the path:
naming a sheet produces the same body as uploading its bytes, field for field, including
every economic term on the offer row; a tampered fixture is still refused under judge mode;
a name outside the manifest is a 400; and the declaration rows are byte-identical either
side of both imports. Seven web tests pin the honesty properties — no step can be skipped,
no verdict is written by the page, and the word "success" appears nowhere on it.

Three rehearsals from a cold workspace: 12 beats each, byte-identical, 0 console errors, 0
failed requests, and the visitor's needs count unchanged by entering the Showcase. Focus
re-measured with real `Input.dispatchKeyEvent` Tab presses rather than programmatic
`.focus()`, which does not trigger `:focus-visible` in Chrome and therefore could not have
proved the earlier claim: **0 of 94 stops across four surfaces at two viewports lack a
visible ring.** No horizontal overflow at 1280×720 or 390×844. Reduced motion still
collapses every transition. 423 words on the finished page plus 12 s of measured clicking
puts a first-time reader at roughly 2–2.5 minutes.

The endpoint-count guard fired, as designed — the API is 50 paths and judge mode exposes 33
— so the README, `docs/ARCHITECTURE.md` and the test moved together rather than drifting.

No AWS deploy, no AgentCore invocation, no Bedrock call, no live payment.

**What we learned**
The property that makes the demo honest is the same property that broke it. An import moves
no counts *because* nothing about people may change, and a client that watches counts to
decide when to re-read therefore cannot see the one thing the sequence exists to show. The
fix is not a wider heuristic — it is the caller saying "I changed the world", which is what
`worldChanged` already was.

**Relevant commits / files**
`services/agent/pool/api/app.py`, `api/public_demo.py`, `services/supplier_import.py`,
`apps/web/src/views/judge.tsx`, `views/judge.test.tsx`, `views/onboarding.tsx`, `App.tsx`,
`api.ts`, `styles.css`, `tests/test_supplier_import.py`, `tests/test_public_demo.py`,
`README.md`, `docs/ARCHITECTURE.md`, `docs/HACKATHON_SCORECARD.md`.

---

### #0053 — [2026-08-20] — Choosing between two finished visual systems, and shipping one
`[PROCESS]` `[FRONTEND]` `[DEMO]`

**Goal / user intent**
Two complete visual systems existed on two branches, both green. Stop experimenting, pick
the one that ships, prove the other did not leak into it, and make `main` the canonical
implementation for an independent audit. This was release integration, not another design
pass: nothing was redesigned, no architecture was reopened, and nothing was taken from the
experiment.

**What we did**

*The experiment is preserved, not merged.* `exp/synoptic-hour` stays at `ddf0b45`, local and
on `origin`, four commits past the release candidate. It replaced the warm-paper system with
a cold chart-stock one — Archivo for Instrument Serif, a petrol/signal palette, a two-ring
favicon, `#dbe3e1` in place of `#f7f4ef`, and a meteogram-style section treatment. It is a
real alternative and it is kept readable rather than deleted, which is the only honest way to
record a direction that was tried and not taken.

*Leakage was proved absent rather than assumed.* The release candidate's tree is
byte-identical to `e8941e3`, which is the exact parent of the first Synoptic commit
(`ef69635^`), so nothing from the experiment can be present in tracked files by
construction. The claim was then checked independently anyway: zero occurrences of
`archivo`, `synoptic`, `meteogram` or `petrol` in tracked files, Instrument Serif still the
only web font dependency, the six-people favicon and `#f7f4ef`/`#14130f` theme colours
intact — and at runtime the served app computes `rgb(247, 244, 239)` with only
`Instrument Serif` and `ui-sans-serif` in use. One stale artefact did survive outside Git: an
empty `node_modules/@fontsource-variable/` scope directory left by the experiment's install,
removed so the install state matches this branch's lockfile. `npm install` reported
"up to date" with no tracked dependency drift.

*A stale server was in the way, and the reason it had to go is the interesting part.* A
`make api` uvicorn from the previous day still held :8000. It was not the deployed
configuration — no SPA at `/`, and no way to prove what environment it had been started
with. A release smoke test whose runtime provenance cannot be demonstrated is not evidence,
so it was replaced with `scripts/run_public_demo_local.sh`, whose `/api/health` states the
configuration on the record: `model_provider: offline`, `payment_provider: simulated`,
`purchase_simulated: true`, `routing_provider: deterministic`, `schedules_enabled: false`,
in-memory store, live agent off.

**Verification**
`make qa` green: **980 agent + 75 infra + 119 web = 1,174**, ruff, eslint, `tsc -b`,
production build, secret scan (plus its self-test), `git diff --check`. The one pytest
warning is Starlette's `httpx` deprecation from a dependency, not repository code.

Browser smoke at 100% zoom against the offline stack, eleven surfaces at 1280×720 and five
at 390×844: **0 console messages**, **154 server requests, all 200**, no response ≥400, no
traceback, and **no external request of any kind** — the font is self-hosted, so nothing
leaves the origin. No horizontal overflow at either viewport, no interactive target under
24 px, a visible 2 px ink focus ring, and `visualViewport.scale` 1 throughout: no zoom-out
needed to read anything.

The Judge Demo was walked cold from reset. 37 standing needs exist before any supplier
fact arrives. Quote A imports through the real path — `riverbend-split-case.csv`, 1144
bytes, digest `8e0f4e6e…` matching `MANIFEST.json`, 1 valid, 0 rejected — and Pool answers
*"Supplier found — not cheaper"*. The demand fingerprint is identical either side of both
imports (38 needs, 7 rice declarations, 24 bags, 24 households), so the sheets move
supplier facts and nothing else. Quote B travels the same path (713 bytes, digest
`f8bd6a6a…`) and the answer becomes *"Worth doing — Pool has not run yet"*; both sheets stay
on file and the run's own facts record that it compared two supplier prices. The run then
formed `pool_67818840e2ca` from the seven pre-existing rice declarants — 24 bags against a
16-unit minimum, three whole cases — with demand unchanged, which is the whole claim: the
order came out of demand that was already there. After a later run advanced that pool, the
first run's report was still byte-identical, field for field. Showcase runs in its own
`…-showcase` workspace and the member's own state survives the round trip. Reset returns
the workspace to 37 needs, no pools, no runs, `onboarded: false`.

No AWS deploy, no AgentCore invocation, no Bedrock call, no live payment, nothing published.

*Documentation.* `PRODUCT.md` claimed 975 agent tests and 1,156 total from #0050, and 50
`BUILD_HISTORY` entries; both are now current. `docs/IMPECCABLE_HANDOFF.md` was re-read
against the running app and its "no longer true" list is still correct, including the
14-step Showcase. Nothing else in the current-state docs was stale, and no historical entry
was rewritten.

**What we learned**
Two finished systems is a better position than one, but only if the losing one is preserved
whole and the winner's independence from it can be demonstrated rather than asserted. Tree
identity against the experiment's parent commit turned "we did not cherry-pick anything"
from a promise into an argument. The other lesson is smaller and more practical: a leftover
dev server is not a neutral inconvenience during a release check — it is an unprovable
runtime, and evidence gathered against it would have been worthless.

**Relevant commits / files**
`PRODUCT.md`, `BUILD_HISTORY.md`. Release candidate `e8941e3` merged to `main`
fast-forward; experiment preserved at `exp/synoptic-hour` `ddf0b45`.

---

### #0054 — [2026-08-20] — Consent Pool can compute with: typed product requirements over curated facts
`[ARCHITECTURE]` `[HITL]` `[ARTICLE-3]`

**Goal / user intent**
Phase 1 of a post-audit architecture. Build the smallest deterministic foundation that lets
Pool reason about *heterogeneous* recurring demand later — several households who all buy
roughly the same thing and disagree about which one — without ever asking a model whether
two products are basically the same. Explicitly not built here: cohort-strategy generation,
any Strands change, the coordination event, the member UI for it.

**Starting state**
`domain/substitution.py` evaluated one exact target SKU against each declaration under six
policies. Two of them are the shapes a household actually comes in — `EXACT_ONLY` ("this
bag") and `APPROVED_PRODUCTS` ("these bags, and I listed them"). `GROUP_DECLARED` added a
third in #0044: "coffee, I do not care which."

The gap the audit found is the shape in between, and it is the common one: *whole bean,
caffeinated, medium or dark — never ground, never decaf.* That is not an allowlist, because
it describes products the member has never seen. It is not a family, because the catalogue's
`coffee` family has 26 members including a vanilla creamer, an instant, a bottled cold brew
and a chilled Frappuccino. There was no field in which to say it, so the only expressible
approximations were far too narrow or far too wide.

**Decision**
A fourth kind of statement, `ATTRIBUTE_CONSTRAINED`, built on three separated pieces:

- **`ProductFamilySchema`** (`domain/attributes.py`) — versioned. Which attributes exist for
  one curated family, what values each may take, and which of them a product must carry
  before it may be reasoned about at all.
- **`ProductAttributeFact`** — one authoritative statement about one product, carrying its
  provenance and verification state. Curated, committed, synthetic.
- **`AttributeConstraint`** — the member's typed rule: `requires` (hard, "the value must be
  one of these"), `excludes` (hard), `prefers` (soft, ranked, and structurally inert).

The curated family is **`roast_coffee`**, deliberately *not* the catalogue's `coffee`. Beans
and ground coffee only. Attributes: `form` (WHOLE_BEAN | GROUND) and `caffeine` (CAFFEINATED
| DECAF), both required by the family; `roast` (LIGHT | MEDIUM | DARK), not required.

**Why**

*Why a new family rather than the existing one.* There is no honest value of `form` for a
creamer. Writing a schema over the broad coffee family would have meant inventing facts to
fit the model, which is the single thing this layer exists to make impossible. The broad
family stays exactly as it is and stays declarable; the narrow one is a separate curated
set that overlaps it in zero products, asserted by test.

*Why facts are a separate object rather than columns on `Product`.* Provenance and
verification have to travel with the value, and the object has to have no writable runtime
path. `ProductAttributeFact(` is constructed in exactly one place in the codebase — a
committed table in `data/product_facts.py`. Adding a fact means editing a file and
committing it. "The model is never the source of a product fact" is therefore a property
of the code rather than a promise in a docstring.

*Why the family-level required flag and the member's policy are two different mechanisms.*
`form` and `caffeine` are what a product **is**; `roast` is taste. So a member who never
mentions roast can be served a bag whose roast nobody confirmed, and a member who requires
medium cannot — because their own rule is what makes that fact load-bearing. One flag
would have forced a choice between too strict for everyone and too loose for the people who
care, and the asymmetry is the interesting part of the design.

*Why the exact-id short-circuit is skipped for this one policy.* Every other policy
short-circuits when the target and the declared product are the same id, which is right:
you asked for this. A constrained declaration stores a product for lineage and its consent
is a statement about *facts*, so a curated fact corrected afterwards — this bag turned out
to be decaf — has to be able to refuse that very product. Otherwise the exemplar would be
the one thing in the world exempt from the member's own rule. Tested both ways.

**Implementation** — implemented and tested; nothing deployed.

New: `domain/attributes.py` (schema, facts, constraint, the pure evaluator, reason codes),
`data/product_facts.py` (curated synthetic family, six bags, the fact registry).

Changed: `SubstitutionPolicy` gains one member; `NeedDeclaration` gains
`attribute_policy`; `domain/substitution.py` gains `CompatibilityReason` and a `code` +
`attribute` on every verdict; `matching.py` carries the code on a rejection;
`PoolContext` gains an injected `product_facts`; `services/needs.py` validates a
constrained declaration; the API accepts and projects one; `domain/policy.py` treats a
constrained match the way it already treated a family declaration.

*Reason codes.* Every verdict now carries a stable token — `EXACT_PRODUCT_REQUIRED`,
`PRODUCT_NOT_ALLOWED`, `WRONG_PRODUCT_FAMILY`, `REQUIRED_ATTRIBUTE_MISMATCH`,
`EXCLUDED_ATTRIBUTE_VALUE`, `ATTRIBUTE_UNKNOWN`, `ATTRIBUTE_UNVERIFIED`,
`ATTRIBUTE_CONFLICTED`, `SCHEMA_VERSION_MISMATCH`, and the rest — plus the schema
attribute that decided it. A code alone cannot tell "eleven members refused on grind" from
"eleven refused on roast", and that distinction is what makes an exclusion actionable
rather than merely honest. The human sentence is unchanged for every policy that already
had one, so nothing displayed anywhere moved.

The rows never reach the model: `OpportunityOutcome.to_dict()` emits `rejected_count` and
not the rejections, so this costs zero tokens per turn (§3.3).

**A HITL boundary did move, deliberately.** A constrained member on Smart Join is no longer
asked to approve a product that satisfies their own rule. AGENTS.md §5 keeps "accepting a
materially different substitute" for a human because *Pool* would otherwise be deciding what
"materially different" means. Here the member decided, in a typed rule, and the
deterministic layer proved this product satisfies it — the same argument that already
applies to `GROUP_DECLARED`. Asking "will you accept whole-bean caffeinated coffee for your
whole-bean caffeinated coffee?" is the notification this product exists to remove. A product
*outside* the rule is still a hard failure, and that is asserted.

**Backward compatibility: interpretation, not migration.** No stored row is rewritten and
there is no migration code. The new field defaults to `None`, an absent key and an explicit
null both read as "no attribute authority", and `GROUP_DECLARED` keeps its exact previous
meaning including that it still pools ground coffee and decaf for somebody who declared the
family. The one existing test that changed is `test_an_unmapped_product_combines_with_
nothing_but_itself`, which sweeps every enum member: under the new policy a declaration
carrying no rule is refused *even for the product it names*, which is stricter than the
claim the test was making, so the new case is asserted separately rather than folded in.

**AWS / external services touched** — None.

**Cost-relevant activity** — None. No model call, no AWS call, no schedule, no new
resource. The fact source is a compiled-in table; there is no lookup service and nothing to
provision (§3.7).

**Agent behavior** — unchanged. `services/agent/pool/agent/` has a zero-line diff.

**Validation**
`make qa` green: **1,060 agent + 75 infra + 119 web = 1,254**, ruff, eslint, `tsc -b`,
production build, secret scan, `git diff --check`. 80 new tests, 79 of them in
`tests/test_constrained_demand.py`.

Proven there: exact accepts its SKU and refuses another; an allowlist admits only what the
member listed; the canonical constrained member gets medium and dark whole-bean caffeinated
and is refused light, decaf and ground, each naming the attribute that decided it; an
exclusion is a separate rule from a requirement; a soft preference mismatch is never a
refusal and a soft preference can never admit what a hard rule refused; unknown, unverified,
conflicted, wrong-family, wrong-schema-version, invalid-policy, missing-policy and
no-fact-source-at-all each refuse with their own code; a policy round-trips through the
DynamoDB adapter and boto3's own serialiser byte-for-byte identically; a row written before
the field existed is still readable; the canonical rice demand still matches at six
households and twenty-two bags on `EXACT_ONLY`; and eight malformed constrained
declarations are refused by the API with a stated reason.

Two of those tests were written expecting the wrong answer and were right to fail. The
second found a real fail-open: a schema attribute whose type this build cannot compare was
being compared for equality anyway when the *family* required it, because the type check
only ran where the member's policy named the attribute. A family with any uncomparable
attribute now refuses wholesale.

The pre-commit self-review found a second, narrower one. Nothing checked that a fact was
actually filed under the product and attribute it claims — the shipped registry indexes by
the fact's own fields and so cannot produce a mismatch, but a fact source is an injected
collaborator and a hand-built one could. Mis-attributing one bag's grind to another is
precisely the failure this layer exists to prevent, so the fact is now checked against the
key it was found under rather than trusted for being there.

**Failures / dead ends**
The first design had the fact source as a module-level lookup the domain imported. That
reverses the dependency direction the repository already has — `data` imports `domain`,
never the other way — and, worse, it makes the authority a compatibility decision rests on
invisible at the call site. It became an injected `ProductFactSource` on `PoolContext`,
alongside the repository and the payment provider, because it is the same kind of thing.
The default is a source that knows nothing, so a caller that has not wired facts in gets
refusals rather than a structural fallback: "nobody supplied the facts" and "the member's
rule passes" must never produce the same answer.

`AttributeValueType` briefly looked like a one-member enum worth deleting. It earns its
place as the fail-closed guard above, which is also what made the gap findable.

**What we learned**
The useful unit of consent is not a product and not a category — it is a *rule*, and a rule
is only safe if the facts it reads are curated, versioned, and unwritable at runtime. The
version field is doing more work than it looks like: a member's stored policy was written
against one reading of what "whole bean" means, and silently reinterpreting it under
another is exactly how consent broadens with nobody deciding to.

The second lesson is about test design. A parametrized sweep over an enum is the cheapest
early warning a codebase can have — adding one member ran forty existing assertions against
a policy that did not exist when they were written, and the single failure it produced was
the one genuinely interesting semantic question in the change.

**Article fodder**
Article 3, directly: this is a concrete answer to "when may an agent act without asking",
and the answer is "when the human wrote a machine-checkable rule and deterministic code
proved it holds" — not "when the model is confident". The `roast_coffee`-versus-`coffee`
decision is a good short illustration for Article 1 of why product ontology is a safety
problem and not a modelling convenience.

**Evidence worth preserving**
The six curated bags and their facts are the fixture Phase 2's cohort strategies will be
generated over; the one deliberately unverified roast is what will make a refusal there
real rather than narrated.

**Relevant commits / files**
`services/agent/pool/domain/attributes.py`, `data/product_facts.py`,
`domain/substitution.py`, `domain/models.py`, `domain/matching.py`, `domain/policy.py`,
`services/context.py`, `services/needs.py`, `services/discovery.py`,
`services/coordination.py`, `api/app.py`, `tests/test_constrained_demand.py`,
`tests/test_catalog.py`.
