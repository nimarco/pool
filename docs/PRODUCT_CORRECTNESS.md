# The parts that are easy to get wrong

Nine places in Pool where the obvious implementation is subtly wrong, and what it does
instead. Every one of these is enforced in deterministic code rather than asked for in a
prompt — see [AI decides what to do. Deterministic code determines what is
true.](../README.md#ai-decides-what-to-do-deterministic-code-determines-what-is-true).

### Provisional participation is not financial commitment

A candidate pool counts **provisional** demand so the opportunity can be discovered and
shown. Only **authorised** demand counts toward the funded threshold. Adding a recurring
need never touches anyone's card.

```
ELIGIBLE → PROVISIONAL → FINAL_OFFERED → AUTHORIZED → LOCKED
```

### The host is chosen before anyone is charged

Host compensation is part of the buyer's price, so the order is fixed: host accepts →
quote refreshed → exact landed cost → final offer → buyer policies evaluated →
authorisation → lock. Pool never authorises $42 and later charges $47. If the price
moves before lock, the stale hold is released and the buyer is asked again.

### The price includes everything

```
  bulk merchandise
+ host / runner compensation
+ payment processing
+ Pool platform fee
= all-in Pool cost

retail comparison − all-in Pool cost = net savings
```

Smart Join is evaluated against **net** landed savings. Two subtleties are load-bearing:
the platform fee is a share of *gross* savings, so it is defined without referring to the
total it belongs to; and card processing is **grossed up** per buyer, so the charge
covers the processor's cut of that very charge. Computing it the naive way would
under-recover by a few cents per buyer — a silent platform subsidy, which is exactly what
the model forbids.

If fair host compensation erases the saving, the pool should not form. That is a correct outcome,
not a bug.

### Pool does not buy stock nobody ordered

Cases do not divide evenly into demand. Rather than quietly buying the leftovers and
billing someone for them, Pool **chooses the buyer set that fills whole cases exactly**
([`fit_to_cases`](../services/agent/pool/domain/economics.py)), preferring people whose need
is already due over demand pulled forward. If no combination lands on a case boundary,
the pool does not lock and says why.

### Future demand moves only with permission

Each need carries two different timing numbers: a **routine restock lead** (when someone
normally buys) and an **earliest acceptable purchase date** (how far ahead they are
willing to buy if it saves money). The agent may decide to *investigate* whether more
demand exists; the deterministic timing engine decides *who is actually eligible*. A
member who authorised no early purchase is never pulled forward, however convenient it
would be for the case count.

In the demo this is not decoration, and the split is a figure the transcript carries
rather than a claim the interface makes: **eight people were buying about now anyway —
18 units, against a supplier minimum of 24. Two more had authorised an early purchase,
and their 6 units close the gap exactly.** Ten people, twenty-four units, two whole
cases. Take away the pull-forward pair and this pool does not form.

### Ten people bought. The record shows eleven

The counts move once, and the run says so where it happens. Ten people are matched at
discovery. One card is then declined, and recovery finds one replacement — so ten people
still buy, and the pool's record carries **eleven memberships**, the extra one being the
failed authorisation. It stays visible on the pool page instead of being deleted, and
every surface reports both numbers: `buyer_count` alongside `member_count`.

### Offering to host is not claiming the job

Candidates come from two places: standing hosts who opted in earlier, and ordinary pool
members who click "Offer to host" on this specific pool. Several people can offer at
once. A deterministic evaluator checks facts — availability, vehicle, capacity, weight,
supplier travel, pickup-site suitability, their own minimum pay — and ranks the eligible
ones on the whole transaction, not the cheapest line. The top candidate gets an offer.
If they decline or the window expires, the next one does. There is no
first-come-first-served path.

Compensation scales with the work: base + per order + distance + exceptional weight +
an optional handoff component. A buyer no-show cannot erase pay for a run already done —
only the handoff slice is contingent.

### Pickup is proved, not asserted

Every buyer allocation gets its own one-time credential: a long token for the QR and a
short human-readable code for when scanning is awkward. **Only hashes are stored.** The
plaintext exists exactly once, in the response that issued it; re-issuing invalidates the
previous pair. The credential carries no payment details, phone number, or email. A host
cannot mark an order collected without one — the only other route is an operator override
that requires a stated reason and is audited.

### Communication is exception-driven

Routine communication is automated; human messaging is the exception. There is no pool
group chat. Buyers get structured exceptions first ("running late", "can't pick up
today"), most of which Pool resolves with nobody's attention; a product problem becomes an
operator case rather than an argument at the pickup table; only what is left opens a
private, transaction-scoped buyer ↔ host thread that archives with the pool. No phone
number or email is ever exposed.
