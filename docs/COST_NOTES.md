# Cost notes

Pool runs on a student's promotional AWS credits. Exhausting them ends the project, so
cost safety is enforced in code and asserted by tests rather than written down as an
intention.

**Nothing in this repository has yet spent a cent of AWS credit.** No AWS credentials were
available during development; every run so far used the in-memory store, deterministic
routing, and the offline planner.

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
| Bedrock invocations | ≤ 8 | Iteration cap. Prompts are compact structured state, not transcripts |
| Lambda | 1 invocation, ≤ 60 s | 1024 MB |
| DynamoDB | tens of on-demand reads/writes | Small demo dataset |
| Location `geo-routes` | ≤ 1 matrix call, ≤ 100 cells | Cached per run so repeated tool calls cannot re-bill |
| CloudWatch | a few KB | 14-day retention |

The demo scenario is two runs. In offline mode both cost **zero**.

## Infrastructure choices, and why

| Choice | Reason |
| --- | --- |
| DynamoDB **on-demand** | Provisioned capacity bills whether or not anyone uses the demo |
| DynamoDB **TTL** on demo workspaces | Judge workspaces expire automatically after 24 h |
| **No** point-in-time recovery | Synthetic data; PITR is storage cost for nothing worth recovering |
| CloudWatch retention **14 days** | Explicit log group — the implicit Lambda one never expires *and survives `cdk destroy`* |
| EventBridge rule **disabled**, 6-hourly when on | Neighbourhood demand changes over days; faster buys nothing and costs invocations |
| CloudFront **PriceClass_100** | Cheapest edge footprint |
| **No** route calculator resource | `geo-routes` needs none — one less billable thing to forget |
| **No** EC2 / RDS / NAT / ALB / OpenSearch | All bill continuously. Asserted absent by test |
| `RemovalPolicy.DESTROY` everywhere | `cdk destroy` genuinely removes everything |

These are not claims — `infra/test_stack.py` asserts each one against the synthesized
CloudFormation template, so a future change that quietly enables the schedule or removes
log retention fails the build.

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

- Default configuration is in-memory + deterministic routing + offline planner: the full
  219-test suite and `make demo` cost nothing and need no account.
- Real model calls are opt-in via `MODEL_PROVIDER=bedrock`, never a default.
- UI work needs no inference; the frontend was developed entirely against the offline path.
- The route adapter is wrapped in a cache so a single run cannot re-bill a lookup.
- `cdk synth` runs offline, so infrastructure is validated without an account.
