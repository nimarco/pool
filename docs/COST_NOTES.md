# Cost notes

Pool runs on a student's promotional AWS credits. Exhausting them ends the project, so
cost safety is enforced in code and asserted by tests rather than written down as an
intention.

**Real AWS spend to date: 18 Bedrock `ConverseStream` calls on Nova Lite** (three
verification runs, entry #0019 — roughly 107k input and 1.3k output tokens in total).
Nothing else. No resource has been created, so nothing is accruing cost right now and
there is nothing to shut off.

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
   `cdk destroy`. `make cost-check` lists runtimes explicitly for this reason.
3. **A CloudFront distribution.** Minimal at zero traffic but non-zero. Removed by
   `make destroy`.
4. **DynamoDB storage.** Negligible at this data volume; demo workspaces self-expire.
5. **Orphaned CloudWatch log groups.** Avoided by declaring the log group explicitly.

## Cleanup

```bash
make cost-check     # list project resources; flag anything recurring
make schedule-off   # stop scheduled runs without tearing anything down
make destroy        # remove the CDK stack
```

Plus, separately, because AgentCore is not part of the CDK stack:

```bash
aws bedrock-agentcore-control list-agent-runtimes
aws bedrock-agentcore-control delete-agent-runtime --agent-runtime-id <id>
```

Every resource is tagged `Project=Pool`, `Hackathon=AgentsForHumans`, `Environment=dev`,
applied inside the stack construct so the tags exist however the stack is instantiated.
`make cost-check` uses the tag to find strays.

**No cleanup script deletes by wildcard.** `DynamoDBRepository.reset()` is scoped to a
single workspace partition and has a test proving it cannot reach another workspace;
`cdk destroy` is scoped to the named stack.

## Live AWS resource ledger

See the ledger at the top of [`BUILD_HISTORY.md`](../BUILD_HISTORY.md). It is currently
**empty** — no AWS resource has been created.

## Development practices that keep this cheap

- Default configuration is in-memory + deterministic routing + offline planner + the
  simulated payment provider: the full 469-test suite and `make demo` cost nothing, need
  no account, and move no money.
- Real model calls are opt-in via `MODEL_PROVIDER=bedrock`, never a default.
- UI work needs no inference; the frontend was developed entirely against the offline path.
- The route adapter is wrapped in a cache so a single run cannot re-bill a lookup.
- `cdk synth` runs offline, so infrastructure is validated without an account.
