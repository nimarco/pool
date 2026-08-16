# Builder Center article notes

Evidence buckets for three articles. **Do not write the articles from memory later** —
that produces a generic, partly-false narrative. Add notes as things happen.

Status: **all three unpublished.**

---

## ⚠️ The bonus requirement (verified 2026-08-15)

Quoted from the official rules and overview:

> "Publish a post on builder.aws.com covering your **build journey and use of AWS** for
> this hackathon. **Use Agents for Humans in your title.**"

> "You can submit more than one blog post. The Blog Post must be published publicly on
> builder.aws.com. Should use Agents for Humans in the Title."

Up to **+0.6 total, 0.2 per post, maximum three.** Published publicly on builder.aws.com
**before the submission deadline**. There is no submission form — judges discover the posts,
so the title is both the requirement *and* the discovery mechanism.

**Two hard constraints this places on all three articles:**

1. **"Agents for Humans" must literally appear in the title.** No exceptions, no clever
   variations. A great post without it scores zero.
2. **Every post must be a build-journey-and-AWS piece.** A pure product essay does not
   satisfy "covering your build journey and use of AWS", however good it is. The original
   plan for Articles 1 and 3 was product/philosophy framing with AWS as background — that
   has been re-anchored below. Keep the ideas; lead with the build.

Re-verify this wording before publishing. The competition changed its blog-post wording
once already during the event.

### Working titles (all satisfy the constraint)

| # | Title | Anchor |
| --- | --- | --- |
| 1 | **Agents for Humans:** what I learned building an autonomous group-buying coordinator with Strands | Journey + why the AI/deterministic split drove the architecture |
| 2 | **Agents for Humans:** deploying a Strands agent to Bedrock AgentCore, and what broke | Pure AWS build story |
| 3 | **Agents for Humans:** bounding an agent loop so it can't burn your AWS credits | Strands hooks + cost engineering, with HITL as the second half |

Article 3's reframe is the important one: cost-bounding *is* an AWS build story, it is the
most transferable thing in the project, and the autonomy/HITL material fits naturally
inside it ("what the agent may do unattended" and "what it may spend unattended" are the
same question asked twice).

---

## Article 1 — *Agents for Humans:* what I learned building an autonomous group-buying coordinator with Strands

*Build journey. Opens with the problem, but the body is the decisions: why one agent not a
swarm, why the model is never allowed to produce a number, what that cost and bought.*

**Qualifies because:** it is explicitly a build-journey post, and the architecture section
carries Strands, Bedrock, and the tool design.

### The thesis

Group buying is not a software problem that nobody solved. It is a **labour** problem that
software mostly ignored. Every group-buying tool assumes a human organiser and gives them
better spreadsheets. The organiser is the bottleneck, and the organiser is unpaid.

### Material captured

- **The economics, concretely.** Campus retail whey protein $46.99/tub. Wholesale $31.50
  in 12-tub cases with a 24-unit minimum. One student needing two tubs cannot reach it. Ten
  students needing twenty-four clear it exactly — and after host pay, card processing, and
  Pool's own fee they still land 23.6% below retail. The gap between those two facts *is*
  the entire product, and the fact that the saving survives the honest costs is the part
  worth writing about.
- **Why it's agent-shaped, not CRUD-shaped.** The opportunity is latent — nobody says
  "let's buy protein powder together", they separately buy protein powder. Discovering a
  viable group requires
  searching a space no one requested. That is the distinguishing property.
- **The design constraint that follows.** A "create a group and invite your neighbours"
  flow is a *product failure*, not a feature. If a human has to notice the opportunity
  first, we built the wrong thing. This single rule shaped the whole UI: there is no
  create-a-pool button anywhere.
- **The demand shape that makes it work.** 24 synthetic members, 33 standing declarations.
  The ten-student protein pool emerges from declarations that were never coordinated — and
  it only *reaches* the minimum because two students had authorised buying early.
- **The best beat in the whole demo, and it was almost an accident.** Current demand is 18
  units against a 24-unit minimum. The supplier sells 12-unit cases. So the pool needs
  exactly six more units, from people whose need isn't due yet, who explicitly said they'd
  buy early. Three constraints that could each have been decoration turn out to interlock:
  minimum, case boundary, and per-person timing authority. Nothing about that was designed
  top-down; it fell out of taking each rule seriously.
- **Quiet by default.** Every notification spends the attention the product exists to
  conserve. A Pool that pings you six times to assemble one order has reproduced the
  problem. Measured outcome in the demo: 8 commitments made without asking, 3 questions
  asked in total.
- **The third side nobody models.** Most group-buying writing covers buyers and suppliers
  and stops. Somebody still has to physically collect thirty kilos and hand it out. Making
  that a *paid role priced by the work done* — and refusing to let the host front the
  purchase — is what turns a favour into something repeatable. Half the domain model exists
  because of that one decision.
- **Refusing to hide a cost is a design constraint, not a virtue signal.** The naive
  processing-fee calculation under-recovers by a few cents per buyer. Nobody would notice.
  It is also a silent platform subsidy, which means the unit economics you're showing
  people aren't the ones you have. Grossing it up properly took twenty minutes and one
  test.

### Good Neighbor framing

The track is about helping *groups*, not individuals. Pool's unit of value is a
neighbourhood: nobody saves anything alone, and the saving scales with how many people
participate. Community pickup sites (libraries, rec centres, schools) are preferred
unconditionally — partly for privacy, partly because that is genuinely where this happens.

### Still to capture

- Whether the framing survives contact with anyone who has actually run a buying club
- A second product domain where the same latent-overlap pattern applies

---

## Article 2 — *Agents for Humans:* deploying a Strands agent to Bedrock AgentCore, and what broke

*The AWS article. Currently the weakest of the three: it is blocked on real deployment
evidence and cannot be written until something has actually run in the cloud.*

**Qualifies because:** it is nothing but AWS build journey.

### Material captured

**Strands specifics worth writing about**

- The tool decorator derives schemas from type hints and docstrings, so the tool surface
  and its documentation cannot drift apart.
- `HookProvider` is the right place for safety. `BeforeModelCallEvent` counts iterations,
  `BeforeToolCallEvent` can *cancel* a tool with an explanatory message the model then sees
  and can act on. That distinction — cancel gracefully at tool level, raise at run level —
  is a genuinely useful pattern.
- `BeforeToolCallEvent.cancel_tool` accepting a *string* is the nicest API detail we found:
  the model gets told why its call was refused instead of just receiving an error.

**Two integration findings with real teeth**

1. **Strands wraps hook exceptions in `EventLoopException`.** Our `except BoundExceeded`
   never fired, so a tripped safety bound was recorded as a generic crash. Fix: walk the
   `__cause__`/`__context__` chain. Lesson: when your safety net raises, verify that the
   thing catching it actually catches it — otherwise the most important signal in the
   system is mislabelled as noise.
2. **Token usage is not on `stop_response.usage`.** It's in
   `stop_response.message["metadata"]["usage"]`. We found it by probing a live run rather
   than reading types. Reading usage *per model call* rather than from `AgentResult` means
   an aborted run still records its cost — and the aborted run is the one you care about.

**The offline planner — the most transferable idea here**

Implementing the Strands `Model` interface with a deterministic planner means the entire
test suite and the local demo drive the *real* event loop, the *real* tools, and the *real*
domain logic at zero token cost. It is not a mock of the system; it is a substitute for one
component. Runs are labelled `model_provider="offline"` so nothing can be misrepresented.

This is the answer to "how do you test an agent without burning money", and it's better
than mocking the loop because the loop is the part most likely to break.

**Deliberate architectural subtractions** (worth a section — everyone writes about what
they added)

- No multi-agent swarm: deterministic domains are tools, not agents.
- No AgentCore Browser or Web Search: synthetic supplier data demonstrates coordination;
  scraping demonstrates scraping.
- No route calculator resource: `geo-routes` needs none, so there is one less billable
  resource to create and forget. Choosing the newer API for *operational* reasons rather
  than feature reasons is a small but real lesson.
- No vector DB, no RAG: nothing here is a semantic retrieval problem.

**Cost engineering**

- Bounds as configuration with safe defaults, enforced in the event loop.
- Route matrices are `origins × destinations` and billed per cell — the cap is checked
  before the call, and the check is unit tested with a client that throws if invoked.
- The EventBridge rule ships **disabled**, and `infra/test_stack.py` asserts that against
  the synthesized template. Turning a cost claim into a test is the only way it stays true.
- Caching adapter so one agent run cannot re-bill the same route lookup.

### Missing — blocks publication

- [ ] A real Bedrock invocation: latency, token counts, actual cost per run
- [ ] A real AgentCore Runtime deployment: what `agentcore deploy` actually did (the
      starter toolkit's `configure`/`launch` is retired — the current CLI is CDK-based)
- [ ] A real CloudWatch/AgentCore trace screenshot
- [ ] A real Amazon Location route matrix response vs. the deterministic estimate — how
      wrong was the great-circle model?
- [ ] Whether the chosen Bedrock model id is even correct for the account/region

---

## Article 3 — *Agents for Humans:* bounding an agent loop so it can't burn your AWS credits

*Strongest material, re-anchored. Lead with the Strands hook system and cost engineering —
concrete, AWS-specific, and genuinely useful to anyone on free credits. Then widen into the
HITL question, since "what may it do unattended" and "what may it spend unattended" are the
same question.*

**Qualifies because:** the first half is Strands hooks, Bedrock invocation bounds, and
CloudFormation-asserted cost policy — all build journey and AWS.

**Structure with the cost half in front:**

1. The bill you don't see coming: an agent loop with no ceiling
2. Strands hooks as the enforcement point (`BeforeModelCallEvent`, `BeforeToolCallEvent`)
3. Cancel vs. raise — and why `cancel_tool` taking a *string* matters
4. The bug our own guard caught
5. Turning cost policy into CloudFormation assertions
6. From "what may it spend" to "what may it do": the autonomy boundary
7. Smart Join as a pure function, and the re-pricing case nobody plans for

### The thesis

Autonomy is not a slider. It is a **classification problem over actions**, and the answer
has to be machine-verifiable — because "the model judged it was fine" is not something you
can put in front of someone's money.

### Material captured

- **The action split.** Autonomous: evaluate demand, compare offers, calculate routes, form
  a candidate pool, search for a replacement, send status notifications. Consequential:
  commit money, raise a budget, accept a substitute, offer a private residence as pickup,
  accept worse terms. Unknown actions default to consequential — an action nobody
  classified is not evidence that it's safe. (There is a test asserting exactly that.)
- **Smart Join is a pure function.** Six rules, all numeric or boolean, all evaluated (not
  short-circuited) so the UI can show *every* failing rule rather than the first. The model
  reads the verdict; it never produces it.
- **Stricter-wins conflict resolution.** A household's standing policy and a specific need
  can disagree; the tighter constraint wins. Simple rule, surprisingly load-bearing.
- **The best finding of the project: recovery re-pricing.** Adding a replacement changes
  everyone's share. If that pushes an existing member past their own spend cap, that is
  "materially worse terms" — a consequential change to a commitment they already made. Pool
  **asks them** rather than silently updating. This is the case that isn't in anyone's HITL
  checklist, and it only shows up when you build the recovery path for real.
- **Quietest sufficient escalation.** Repairing a dropout by asking one household with
  compatible latent demand beats broadcasting to the whole pool. The measurable claim:
  during recovery, zero existing members were contacted. There's a test asserting nobody
  else was re-invited.
- **Form tight, repair wide.** The formation radius is 1.6 km; the recovery radius is 4 km.
  Deliberate asymmetry: keep the initial travel burden low, widen only to repair — and even
  then every candidate is still bounded by their own travel policy.
- **Explainability without chain-of-thought.** Run records store tool names, counters,
  termination reasons, and token usage. They store *no* model reasoning, and tool arguments
  only as a hash — so the log is safe to publish and still answers "why did this happen?".
- **When the guard caught us.** A planner bug re-issued a terminal tool forever; the
  iteration cap stopped it and recorded a `loop_fault`. Two lessons worth writing: the
  safety net must fail *loudly* (a silent truncation would have looked like a normal empty
  result), and a system that relies on its safety net every run has a bug, not a design.
- **Three verdicts, not two.** The obvious autonomy design is a boolean: may I act, or must
  I ask? That is wrong, because some situations *no prompt can fix*. A product outside
  someone's stated substitution authority, or a pickup day they cannot make, is not a
  question — it is a disqualification. Splitting `NOT_ALLOWED` out from
  `HUMAN_APPROVAL_REQUIRED` removed a whole category of "asking someone something pointless"
  and simplified the pricing loop, because ineligible buyers are removed and the price
  recomputed rather than left pending forever.
- **The agent needs to see the consequences of its own actions.** A planner that reads its
  work queue once, acts, and then decides from the stale view will never notice that the
  pool it just repaired has become lockable. Re-reading after acting fixes it — but
  unbounded re-reading is just polling with extra steps, so the alternation is capped, and
  the duplicate-call guard would catch it anyway. "Observe after acting, at most twice" is
  a small pattern that made the whole loop work.
- **The bug I'd write a whole section about: recovery over-recruited.** The first version
  computed the funding gap as "threshold minus authorised units", which silently counted
  buyers who simply hadn't answered their final offer yet. So it recruited replacements for
  people who hadn't left, filled a hole that wasn't there, and left the pool oversubscribed
  — trading a funding problem for exactly the speculative-stock problem the product exists
  to prevent. The fix is conceptual, not mechanical: **distinguish demand that is *lost*
  from demand that is *pending*.** Only failed authorisations, withdrawals, and declines are
  a hole. And replacements must sum to *exactly* the gap, because "at least enough" breaks
  the case boundary.
- **The corollary about honest reporting.** Once that was fixed, recovery still reported
  `recovered=False` when the pool was whole — because success was measured against *funded*
  units, which cannot be complete while humans are still deciding. Recovery's job is to fill
  the hole, not to finish the pool. Measuring an operation against something it does not
  control produces a system that lies about its own outcomes in a way tests happily pass.

### Structure sketch

1. The naive framing: an autonomy slider from 0 to 100
2. Why that fails: autonomy is per-action, not per-user
3. Classify actions, default unknown ones to consequential
4. Make the policy a pure function, not a judgement
5. The case nobody plans for: when someone *else's* action changes your terms
6. Escalate as quietly as the situation allows
7. Explainability without exposing reasoning
8. What the guard rails caught, including our own bug

---

## Evidence still worth capturing

| Item | For | Status |
| --- | --- | --- |
| Screenshot: decision inbox with "why you're being asked" | 1, 3 | ⬜ |
| Screenshot: activity feed showing the automatic recovery | 1, 3 | ⬜ |
| Screenshot: agent trace with tool sequence and termination reason | 2, 3 | ⬜ |
| Screenshot: community map showing approximate positions | 1 | ⬜ |
| Screenshot: "where the money goes" cost breakdown | 1, 3 | ⬜ |
| Screenshot: host candidates with score components and refusal reasons | 1, 3 | ⬜ |
| Screenshot: viability panel, all eleven checks | 3 | ⬜ |
| Real Bedrock run: latency, tokens, cost | 2 | ✅ #0019, #0020, #0021 |
| Real AgentCore deployment output and trace | 2 | ⬜ blocked |
| Real vs. deterministic routing comparison | 2 | ⬜ blocked |
| `make demo` terminal transcript | all | ✅ reproducible any time |
| Test output: 514 passing (490 app + 24 infra) | 2 | ✅ |
| Synthesized CloudFormation showing the disabled schedule | 2 | ✅ |
