# Demo script — five minutes

One memorable journey. The implementation is sophisticated; the story must not be.

**The line everything hangs off:**

> **Nobody organised the group. Pool noticed.**

Do not spend the video explaining every state, every adapter, every host formula, or
every future legal question. Show one purchase happening.

---

## Before recording

```bash
make qa          # everything green before you film anything
make dev         # API :8000, web :5173
```

Open <http://localhost:5173>, press **Reset**, and leave the browser on the landing page.

Have a second terminal ready with `make demo` typed but not run — it produces the same
transcript in text, which is useful for the technical section.

Check on camera: **Payments: simulated · Purchase: simulated · Model: offline ·
Background schedules: off** is visible in the footer. Say it out loud once. Everything
else in the video is easier to trust after that.

---

## 0:00–0:25 — The problem

**Show:** the landing page.

> Every campus already does this. Someone posts: *"I can buy 50 tubs of protein powder
> way cheaper than the store — DM me if you want one."*
>
> And it works, badly. That person guesses the demand, fronts their own money, buys the
> stock before anyone has committed, then answers thirty messages, chases payment,
> arranges meetups, and eats whatever is left over. They're not paid for any of it. So it
> happens once and stops.

## 0:25–0:50 — The insight

> Pool runs that job in reverse. Nobody creates a group. People just say what they
> routinely buy — protein powder every six weeks, coffee every month — and then forget
> about it.
>
> An agent watches for the moment several of those needs line up into something worth
> buying together.

**Click:** *Enter Demo University.*

## 0:50–1:30 — Latent demand

**Show:** the Needs table, briefly. Then **Run a scan**.

> Nobody here declared a group. Twenty-four students, thirty-three standing needs.
>
> The agent finds eight people who separately need the same protein powder. That's
> eighteen tubs — and the supplier minimum is twenty-four. Most systems would stop.
>
> Two more students don't need theirs for another month, but both explicitly said they'd
> buy up to five weeks early if it saved money. That authorisation is the only reason
> Pool may count them — and it takes the order to exactly twenty-four.

**Point at:** the trace — `list_latent_demand → evaluate_pool_economics →
create_candidate_pool → request_host_acceptance`.

> Twenty-four is not a coincidence. The supplier sells twelve-unit cases. Pool picks the
> set of buyers that fills whole cases exactly, because the alternative is buying stock
> nobody ordered and quietly billing someone for it.

## 1:30–2:05 — Fulfilment and economics

**Show:** the pool detail page — host candidates first.

> Somebody still has to collect thirty kilos of protein powder and hand it out.
>
> Pool considers standing hosts *and* pool members who clicked "offer to host" — and
> offering doesn't claim the job. Four candidates. Two are ineligible for stated factual
> reasons: one wants more money than the job pays, one has no vehicle for a fifty-five
> kilo load. The evaluator ranks the rest and offers the work to the best fit.

**Scroll to:** *Where the money goes.*

> And this is the part I'd want to see if I were a buyer. Seven hundred and fifty-six
> dollars of merchandise. Forty-four dollars sixty-eight to the host, funded by the
> buyers, not by us. Twenty-eight dollars of card processing. Thirty-two seventy to Pool.
>
> All-in: eight hundred sixty-one forty-four, against eleven twenty-seven if these ten
> people had each walked to the campus store. Twenty-three point six percent — *after*
> everything. Nothing hidden.

## 2:05–2:45 — Autonomy and payment

**Show:** the Decision Inbox.

> Eight of these students had already told Pool their rules: minimum saving, maximum
> spend, maximum walk. Those rules pass, so Pool authorises their exact final amount
> without asking. Two are on "ask me", so they get one question with the answer already
> worked out.
>
> And notice the order. The host is chosen *before* anyone is charged, because host pay
> is part of the price. Pool never authorises forty-two dollars and then charges
> forty-seven.

## 2:45–3:20 — Failure, and recovery

**Show:** the activity feed.

> Then one card is declined.
>
> Those two units stop counting as funded, and the order is short. This is where a group
> buy normally dies in a group chat.

**Show:** the recovery run in the trace.

> The agent goes and finds compatible demand in the wider community — someone whose
> quantity replaces the gap *exactly*, because over-recruiting would just trade a funding
> hole for surplus stock. Their own rules pass, their payment authorises, and the order
> is whole again. Nobody who'd already committed was disturbed.

## 3:20–3:50 — Lock and purchase

**Show:** the viability panel.

> Now the lock. Eleven checks, all of them run: supplier minimum, quote freshness, case
> allocation, host assigned, host pay clears their minimum, buyers actually save,
> everyone accepted their price, Pool's own economics, timing, pickup site, funding.
>
> All eleven pass, so the pool locks and the payments capture — in that order. Then one
> bulk order goes in.

**Point at:** SIMULATED-ORDER-…

> Clearly labelled simulated, everywhere it appears. No supplier was contacted and no
> money moved.

## 3:50–4:10 — The physical handoff

**Show:** the Host view.

> The host gets a real job: ten orders, a live checklist, and their earnings broken down.
>
> Each buyer has a one-time code. Only the hash is stored — the plaintext exists once. The
> host can't mark anyone collected without it.

**Do:** re-enter a code that's already been used. It is rejected.

> And it works exactly once.

## 4:10–4:40 — Technical proof

**Show:** the Agent view.

> Underneath: Strands running the agent loop with twelve typed tools and nothing else —
> no shell, no arbitrary queries. Every run bounded at eight iterations and twenty-five
> tool calls, with duplicate-call detection, and every run terminating in a recorded
> outcome.
>
> Bedrock for inference, AgentCore Runtime to host it, DynamoDB for state, EventBridge for
> the background scan — created disabled — Amazon Location for routing, Stripe test mode
> for payments.
>
> The rule underneath all of it: the model decides *what to do*. Deterministic code
> decides *what is true*. Every price on every screen came from a tool, not from a
> sentence a model wrote.

## 4:40–4:55 — Impact

**Show:** the Impact page.

> The buyer saves. The host earns for work they actually did. The supplier gets a clean
> bulk order. Pool takes a transparent share of the saving — no saving, no fee.
>
> Bulk pricing usually favours whoever can afford to buy a lot at once and has somewhere
> to put it. This is a way to reach it without each person carrying all of that alone.

## 4:55–5:00 — Close

> Nobody organised the group. Pool noticed.

---

## Rules for the recording

- **Say what is simulated, once, early.** It buys credibility for everything after it.
- **Never say "deployed"** unless it is, at that moment, deployed and you can show the URL.
- **Never say a number the screen isn't showing.**
- Do not narrate the state machine. Do not narrate the adapters. Do not explain the
  merchant-of-record question. All of it is in the docs for anyone who wants it.
- If the demo breaks on camera: press **Reset** and re-run. It is deterministic; it will
  produce the same numbers.

## Backup

If the UI misbehaves, `make demo` prints the same lifecycle as a transcript from the same
code path. It is a legitimate fallback, not a different demo.
