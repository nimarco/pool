# Cost notes

Pool runs on a student's promotional AWS credits. Exhausting them ends the project, so
cost safety is enforced in code and asserted by tests rather than written down as an
intention.

**Real AWS spend to date:** Bedrock `ConverseStream` on Nova Lite across entries #0019–#0021
(local verification) and #0023 (six live invocations from the deployed runtime, ~114k input
/ ~2.9k output tokens), plus — since **2026-08-16** — the first provisioned infrastructure
this project has ever had.

**Resources now exist and some of them accrue.** A CDK bootstrap (`CDKToolkit`) and the
deployed AgentCore runtime (`AgentCore-Pool-default`) are live. There is **no always-on
compute**: the runtime bills per invocation only. What does accrue quietly is storage and
log ingestion — the CDK staging bucket, three CloudWatch log groups, and account-wide X-Ray
Transaction Search. Every one of them is enumerated with its own teardown command in the
resource ledger at the top of [`BUILD_HISTORY.md`](../BUILD_HISTORY.md).

Every other run — the full test suite, `make demo`, all UI development — used the
in-memory store, deterministic routing, simulated payments, and the offline planner, and
cost nothing.

---

## Enforced bounds

All configurable via environment variables so they can be tightened without a code change.

| Bound | Env var | Default | Enforced where |
| --- | --- | :-: | --- |
| Model iterations per run | `MAX_AGENT_ITERATIONS` | 8 | `BeforeModelCallEvent` — **raises**, terminating the run |
| Tool calls per run | `MAX_TOOL_CALLS_PER_RUN` | 25 | `BeforeToolCallEvent` — cancels further calls |
| Identical repeated calls | `MAX_DUPLICATE_TOOL_CALLS` | 2 | Argument digest; cancelled with an explanation |
| Tool retries | `MAX_TOOL_RETRIES` | 3 | Bounded with backoff |
| Wall clock per run | `WORKFLOW_TIMEOUT_SECONDS` | 120 | Checked on every model and tool call |
| Route matrix cells | `MAX_ROUTE_MATRIX_CELLS` | 100 | Checked **before** any Location API call |
| Background schedules | `SCHEDULES_ENABLED` | `false` | Rule ships DISABLED in CloudFormation |

A run that hits a bound terminates **loudly** — recorded as `outcome=loop_fault` with the
specific bound in `termination_reason` — never as a silent truncation that resembles a
normal result. `tests/test_agent_bounds.py` proves each of these by driving a deliberately
misbehaving model through the real event loop.

## Per-run cost shape

One coordination run at defaults:

| Resource | Worst case per run | Notes |
| --- | --- | --- |
| Bedrock invocations | ≤ 8 | Iteration cap. **Measured: 6 calls for a discovery run** |
| Lambda | 1 invocation, ≤ 60 s | 1024 MB |
| DynamoDB | tens of on-demand reads/writes | Small demo dataset |
| Location `geo-routes` | ≤ 1 matrix call, ≤ 100 cells | Cached per run so repeated tool calls cannot re-bill |
| CloudWatch | a few KB | 14-day retention |

The demo scenario is three runs. In offline mode all three cost **zero**.

### Measured, not estimated (#0019, #0020)

A discovery run against `us.amazon.nova-lite-v1:0`: **6 ConverseStream calls, ~35.7k input
tokens, ~420 output tokens, ~6 s**. Consistent across three runs.

The input figure deserved attention: it was **85× the output**. Strands resends the whole
conversation each turn, so every large tool result is re-billed on every subsequent call
— and `evaluate_pool_economics` alone returned 9,015 bytes, growing with community size.

**Fixed in #0020 by projecting tool results** (`pool/agent/projection.py`). The model now
receives the decision-critical facts; the complete deterministic result is retained for
the API, the operator UI, auditing, and tests. Re-measured on the same model, seed,
scenario and bounds:

| Discovery run (6 iterations) | Before | After | Change |
| --- | --- | --- | --- |
| Input tokens | ~35.8k | ~19.2k | **−46%** |
| Output tokens | ~430 | ~490 | +14% |
| Input:output ratio | 85:1 | 39:1 | |
| Wall clock | ~6.0 s | ~5.5 s | −8% |
| Tool sequence and outcome | canonical, `pool_created` | unchanged | — |

Strands' own context management was evaluated and **not** adopted: the default sliding
window (40 messages) never engages in a run this short, its reactive truncation cuts tool
JSON blindly at 200 characters, and summarizing compression would spend an extra model
call to put an LLM paraphrase of deterministic numbers into context — which AGENTS.md §5
forbids. See #0020.

### What the first real deployment actually cost, and what it left running (#0023)

A deployed discovery run against `us.amazon.nova-lite-v1:0` matched the local measurement:
**6 Bedrock calls, ~19.1k input / ~473 output tokens, ~5 s of agent time** inside ~12 s
wall clock including microVM cold start. Traces now expose the per-call breakdown —
2111 → 2624 → 3089 → 3415 → 3770 → 4131 input tokens as context accumulates — so the
re-send growth is visible per turn, not just in the total.

Deploying introduced three persistent surfaces that no per-run figure captures:

| Surface | Cost shape | Note |
| --- | --- | --- |
| CDK staging bucket | S3 storage, **41.7 MiB per deployed artifact version** | Accumulates on every redeploy. Not garbage-collected |
| AgentCore runtime | **Per-invocation only** | No idle compute. Idle session capped at 60 s, lifetime at 300 s |
| **X-Ray Transaction Search** | **Per-GB span ingestion, account-wide** | Enabled by `agentcore deploy` itself — not by any Pool config — and **not** removed by `make destroy-agent` |

The third is the one worth remembering: a tool switched on an account-level billing path
as a side effect and announced it in one line of output. It also created
`/aws/application-signals/data` **with no retention policy at all**. Both that group and
the runtime's own log group are created outside the CloudFormation stack, so neither is
destroyed with it, and both had to be given 14-day retention by hand.

#### Three different percentages, which are easy to conflate

The phrase "100 % sampling" was used loosely in the first write-up of #0023. There are
three separate numbers here and only two of them are at 100 %:

| # | Layer | What it controls | Current value | Who set it |
| :-: | --- | --- | :-: | --- |
| 1 | **Transaction Search span ingestion** | Every span written to CloudWatch Logs (`aws/spans`, and the runtime's own `spans` stream). **Not a configurable percentage** — it is 100 % by construction whenever Transaction Search is enabled | **100 %, inherent** | Implied by `UpdateTraceSegmentDestination` |
| 2 | **X-Ray trace-summary indexing** | What fraction of *traceIds* become searchable trace summaries — the X-Ray Traces console, `get-trace-summaries`, ServiceLens. AWS's default is **1 %** | **100 %** | **Explicitly set by AgentCore CLI 0.27.0** |
| 3 | **X-Ray centralized head sampling** | Classic X-Ray SDK sampling. Rule `Default`, `FixedRate 0.05`, reservoir 1, `ModifiedAt` epoch 0 — the AWS built-in, **never modified** | **5 %, and unused** | Nobody |

**Number 3 is inert on this path.** The AgentCore OTel pipeline does not appear to consult
X-Ray centralized sampling: every runtime log line carried `trace_sampled=True`, and a
single run exported all 25 of its span records — consistent with an always-on OTel sampler,
not a 5 % one.

**Only number 1 is the money.** Ingestion is the dominant Transaction Search charge, and
the indexing percentage in number 2 does not reduce it. So lowering indexing to 1 % would
save essentially nothing while making the handful of hackathon traces invisible in
X-Ray/ServiceLens. Measured span volume is **138.9 KiB per run** (25 records, ~5.7 KiB
each) — 1,000 runs is ~0.13 GB. The real lever is Transaction Search on/off, not the
percentage. See Q18.

Turn Transaction Search off with:

    aws xray update-trace-segment-destination --destination XRay

## Infrastructure choices, and why

| Choice | Reason |
| --- | --- |
| DynamoDB **on-demand** | Provisioned capacity bills whether or not anyone uses the demo |
| DynamoDB **TTL** on demo workspaces | Judge workspaces expire automatically after 24 h |
| **No** point-in-time recovery | Synthetic data; PITR is storage cost for nothing worth recovering |
| CloudWatch retention **14 days** | Explicit log group — the implicit Lambda one never expires *and survives `cdk destroy`* |
| EventBridge rule **disabled**, 6-hourly when on | Recurring demand changes over days and a Pool Day comes round weekly; faster buys nothing and costs invocations |
| CloudFront **PriceClass_100** | Cheapest edge footprint |
| **No** route calculator resource | `geo-routes` needs none — one less billable thing to forget |
| **No** EC2 / RDS / NAT / ALB / OpenSearch | All bill continuously. Asserted absent by test |
| `RemovalPolicy.DESTROY` everywhere | `cdk destroy` genuinely removes everything |

These are not claims — `infra/test_stack.py` asserts each one against the synthesized
CloudFormation template, so a future change that quietly enables the schedule or removes
log retention fails the build.

## Money that is not AWS credit

Payments deserve their own note, because the failure mode is worse than a surprise bill.

| Control | Where it is enforced |
| --- | --- |
| Default provider is `simulated` | `config.py`; the CDK stack pins it, asserted by an infra test |
| Stripe provider **refuses any non-`sk_test_` key** | `adapters/payments.py`, unconditional — no flag relaxes it |
| No Stripe credential in the CDK template | Asserted by `test_no_stripe_credential_is_baked_into_the_template` |
| Purchase executor pinned to `simulated` | Only executor implemented; the builder raises on any other value |
| Webhooks verified before parsing, replays rejected | `verify_webhook_signature`, tested |

The simulated provider never opens a socket. Every test, the demo, and the deployed
default move exactly zero real money, and a misconfigured environment fails loudly at
construction rather than quietly charging a card.

## What could still cost money unattended

Ranked by how easy it is to forget:

1. **An enabled EventBridge rule.** Ships disabled. `make schedule-off` disables it again;
   `make schedule-on` requires typing `ENABLE` to confirm.
2. **A deployed AgentCore Runtime.** Deployed by its own tooling, so it is *not* removed by
   `cdk destroy`. `make cost-check` lists runtimes explicitly for this reason. **Live since
   2026-08-16.** Per-invocation billing, so it costs nothing while idle.
3. **X-Ray Transaction Search.** Enabled account-wide by `agentcore deploy` itself (#0023),
   not by anything in this repository, and not removed by tearing the stack down. Per-GB
   span ingestion at 100 % — inherent to it being on, not a setting. The same CLI call
   sequence also raised the account-level `Default` **indexing** rule from 1 % to 100 %,
   which is a different number and costs nothing extra. Retained through the hackathon by
   Q18; revisit when the runtime is no longer needed.
4. **Orphaned CloudWatch log groups.** No longer hypothetical: the AgentCore runtime's log
   group and `/aws/application-signals/data` are both created *outside* CloudFormation and
   both arrived with **no retention policy**. Set to 14 days by hand in #0023. Nothing
   destroys them for you.
5. **The CDK staging bucket.** ~41.7 MiB per deployed artifact version, accumulating across
   redeploys. Must be emptied before `CDKToolkit` can be deleted.
6. **A CloudFront distribution.** Minimal at zero traffic but non-zero. Removed by
   `make destroy`.
7. **DynamoDB storage.** Negligible at this data volume; demo workspaces self-expire.

## Cleanup

```bash
make cost-check     # list project resources; flag anything recurring
make schedule-off   # stop scheduled runs without tearing anything down
make destroy        # remove the PoolStack CDK stack
make destroy-agent  # remove the AgentCore stack (the CLI has no destroy command)
```

Then the things no stack owns, in this order:

```bash
aws logs delete-log-group --log-group-name /aws/bedrock-agentcore/runtimes/<runtime-id>-DEFAULT
aws logs delete-log-group --log-group-name /aws/application-signals/data
aws logs delete-log-group --log-group-name aws/spans
aws xray update-trace-segment-destination --destination XRay
```

And, only when finished with CDK in this account entirely:

```bash
aws s3 rm s3://cdk-hnb659fds-assets-860325090409-us-east-1 --recursive
aws cloudformation delete-stack --stack-name CDKToolkit
```

Every resource is tagged `Project=Pool`, `Hackathon=AgentsForHumans`, `Environment=dev`,
applied inside the stack construct so the tags exist however the stack is instantiated.
`make cost-check` uses the tag to find strays.

**No cleanup script deletes by wildcard.** `DynamoDBRepository.reset()` is scoped to a
single workspace partition and has a test proving it cannot reach another workspace;
`cdk destroy` is scoped to the named stack.

## Live AWS resource ledger

See the ledger at the top of [`BUILD_HISTORY.md`](../BUILD_HISTORY.md). As of **2026-08-16**
it lists **23 live rows** across three groups: the `CDKToolkit` bootstrap and its 11
resources (12), the `AgentCore-Pool-default` stack and its 3 resources (4), and **seven
things created outside both stacks** that no teardown command removes for you.

## Development practices that keep this cheap

- Default configuration is in-memory + deterministic routing + offline planner + the
  simulated payment provider: the full 469-test suite and `make demo` cost nothing, need
  no account, and move no money.
- Real model calls are opt-in via `MODEL_PROVIDER=bedrock`, never a default.
- UI work needs no inference; the frontend was developed entirely against the offline path.
- The route adapter is wrapped in a cache so a single run cannot re-bill a lookup.
- `cdk synth` runs offline, so infrastructure is validated without an account.
