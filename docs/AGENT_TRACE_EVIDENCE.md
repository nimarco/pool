# Agent trace evidence

Recorded 2026-09-07. Everything below is output from a run that actually executed. No
trace here was written by hand, and none was selected from several attempts — the runs
are reported in the order they were made, including the beats that ended in a refusal.

Regenerate any of it with the commands at the bottom.

---

## 1. AgentCore Runtime v8 — live, verified

The README previously recorded that runtime **version 8 had never been invoked** (the
live Nova Lite verification was performed against version 7 on 2026-08-22). That gap is
now closed.

**Runtime state** (read-only, `bedrock-agentcore-control`):

```
agentRuntimeName    Pool_PoolCoordinator
agentRuntimeVersion 8
status              READY
lastUpdatedAt       2026-08-23 21:08:31 UTC
networkMode         PUBLIC
endpoint DEFAULT    READY, liveVersion = 8
```

**One bounded invocation**, `trigger: smoke_test`, into the private workspace
`smokev8-20260907` — a name the public demo's session scheme cannot generate, so no
visitor's partition was read or written:

```json
{
  "run_id": "run_9793fd48b53d",
  "workspace": "smokev8-20260907",
  "outcome": "pool_created",
  "iterations": 7,
  "termination_reason": "completed",
  "model_provider": "bedrock",
  "model_id": "us.amazon.nova-lite-v1:0",
  "duration_ms": 7594,
  "input_tokens": 29555,
  "output_tokens": 605,
  "hitl_decisions_created": 1
}
```

Tool sequence, as recorded:

```
list_latent_demand → evaluate_pool_economics → create_candidate_pool
  → find_host_candidates → request_host_acceptance → issue_final_offer
```

The last call is worth reading. `issue_final_offer` returned
`issued: false, reason: "no host has accepted this pool yet"` — the agent tried to advance
the lifecycle, deterministic code refused because the precondition was not met, and the
run ended `completed` rather than retrying or working around it.

**Read back from DynamoDB independently of the response**, to establish that the pool a
visitor would see was built by this run rather than replayed from its answer:

```
run  run_9793fd48b53d   provider=bedrock  model=us.amazon.nova-lite-v1:0  outcome=pool_created
pool pool_aab66b5b3ada  product=prod_whey_vanilla  status=host_recruiting
                        created_by_run=run_9793fd48b53d
```

Wall time from the calling process: 13,816 ms, of which 7,594 ms was agent time.
The workspace carries the standard 24-hour TTL.

---

## 2. The refusal-and-redirect trace

This is the run that demonstrates agency, and it was produced by doing the ordinary
thing: onboarding, then saving **one** declaration. Saving is the only action taken.
Everything after it is the coordination run that the save caused.

The member declares *Kestrel Roastworks medium roast* and answers the flexibility
question with "similar" — keeping form and caffeine, accepting `MEDIUM` or `DARK` roast.
That admits more than one possible order, which is the situation the agent exists for.

### 2a. Live Amazon Nova Lite — `run_8a7b91e6793c`

```
trigger      need_declared          objective    member
provider     bedrock                model        us.amazon.nova-lite-v1:0
outcome      pool_created           iterations   7 of 8
termination  completed              tokens       28,227 in / 640 out
duration     7,439 ms
```

| # | Tool the agent chose | What deterministic code returned |
| --- | --- | --- |
| 1 | `list_cohort_strategies` | the options, each with compatible demand, none costed |
| 2 | `evaluate_cohort_strategy` — Kestrel | `viable: false`, `blocker_code: not_cheaper` |
| 3 | `evaluate_cohort_strategy` — Harbourstone | `viable: true` |
| 4 | `create_candidate_pool_from_strategy` | `created: true`, `pool_34beff031819` |
| 5 | `find_host_candidates` | `eligible_count: 0`, `candidates_considered: 3` |
| 6 | `record_no_action` | `"No eligible hosts found"` |

Step 2 → 3 is the beat that matters. The agent picked Kestrel first, the deterministic
evaluator refused it on economics, and the agent **did not** re-evaluate it, argue with
the verdict, widen who was compatible, or form it anyway. It chose a different listed
option and evaluated that one instead. Step 4 could only be reached by passing the
`evaluation_id` of the evaluation that confirmed viability — the mutation is gated on the
evidence, not on the model's assertion.

Note that every tool call reports `ok: true`, including the refusal. That is correct and
worth stating plainly: the refusal is a **deterministic verdict returned by a successful
tool call**, not a tool error. The agent has to read the payload and decide what it means.

The deterministic result underneath, read back from stored rows:

```
Kestrel Roastworks   — medium roast : viable=False  blocker=not_cheaper
Harbourstone Coffee  — dark roast   : viable=True

ORDER FORMED  Harbourstone Coffee, whole bean, 2 lb — dark roast
              18 units = 3 cases x 6, surplus 0
              created_by_run = run_8a7b91e6793c
```

**Replication.** An earlier live invocation the same day, `run_f10ba4c23e90`, produced the
identical six-call sequence and the identical order (28,087 in / 613 out, 6,947 ms). Two
independent live runs, same decisions.

### 2b. The deterministic planner — `run_2a0384889e5c`

The same world, the same declaration, the same Strands event loop, the same 17 tools —
with `DeterministicPlannerModel` in the model position instead of Nova Lite. This is the
route the public judge demo runs.

```
provider     offline                model        offline-deterministic-planner
outcome      pool_created           iterations   5 of 8
termination  completed              tokens       0 in / 0 out
duration     6 ms
```

```
list_cohort_strategies
  → evaluate_cohort_strategy  (Kestrel)      viable=false, not_cheaper
  → evaluate_cohort_strategy  (Harbourstone) viable=true
  → create_candidate_pool_from_strategy      pool_fbc0b089354a
```

Same refusal, same redirect, same order: Harbourstone, 18 units, 3 × 6 cases, surplus 0.

**Why this pairing is the useful result.** The deterministic planner is not standing in
for a decision the model cannot make — it reproduces a decision Nova Lite demonstrably
does make, on the same evidence, through the same tools. So the free, repeatable judge
path is a faithful rehearsal of the paid one rather than a different story told twice.
The two runs differ in the tail: Nova Lite went on to try host recruiting and closed with
`record_no_action`; the planner stopped at the formed pool.

---

## 3. What is *not* reachable through AgentCore

Stated because the trace above could otherwise imply it. The AgentCore entrypoint accepts
`workspace`, `community_id`, `trigger` and `instruction` — it does **not** accept an
`event_id`, and the cohort-strategy surface is selected by a coordination event
(`objective.searches_strategies`). So the refusal-and-redirect run in §2a executed the
real Strands loop against live Nova Lite through the local API path, not through the
hosted runtime.

The hosted runtime reaches the latent-demand surface, which is what §1 exercises.

---

## Reproducing this

```bash
# runtime state and one live invocation (COSTS MONEY, a fraction of a cent)
make whoami
cd services/agent && .venv/bin/python -m pool.scripts.verify_bedrock

# the refusal-and-redirect run on the deterministic planner — free, no credentials
cd services/agent && .venv/bin/python -m pytest tests/test_member_demo.py -q
```

`tests/test_member_demo.py::test_the_order_is_the_one_the_evaluator_adapted_to` asserts
the Kestrel refusal and the Harbourstone formation as a standing property, so the trace
above cannot quietly stop being true.
