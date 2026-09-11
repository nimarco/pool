# Builder Center publishing checklist

Prepared 2026-09-06. **Nothing has been published.** No Builder Center draft exists yet.

Paste the `# …` H1 line of each file into the **Title** field, and everything below it into
the **body**. Do not paste the H1 into the body — Builder Center renders the title itself.

---

## Title wording — settled

The rules page carries an update notice above the body text:

> "Updated 8/12/26 to remove requirement of #AgentsforHumans in Blog Post Bonus Submission
> items."

The stale line further down the same page ("Use hashtag Agents for Humans in the title")
is superseded by that notice. The overview page's wording — "Use Agents for Humans in your
title" — is the operative requirement, and all three titles satisfy it as written.

**No hashtag. Titles are final as below.** Re-read the notice before publishing; the page
has been edited at least once during this event.

---

## Rule eligibility — verified 2026-09-06 against the live pages

| Item | Status |
| --- | --- |
| Builder Center posts still qualify | ✅ Yes — "publishing a builder.aws Blog Post" |
| Bonus per post | ✅ 0.2 points each |
| Maximum bonus | ✅ 0.6 total (three posts) |
| "Agents for Humans" expected in title | ✅ Yes, as a phrase. All three titles comply |
| Hashtag required | ✅ **No** — removed from the rules on 2026-08-12 by a notice at the top of the rules page |
| Minimum word count | ✅ None stated anywhere |
| Required tags | ✅ None stated |
| Required disclosures | ✅ None. Builder Center appends its own author-opinion line automatically |
| Formatting / image requirements | ✅ Guidance only: H1 → H2 → H3, alt text on images, 4.5:1 contrast, short paragraphs, **max 5 tags per article** |
| Must be public before the deadline | ✅ Yes — "publicly posted to builder.aws", before **2026-09-14 17:00 PT** |
| Content focus | ✅ "covering your journey building and implementing AWS for this hackathon" |

Publishing mechanics: sign in with an AWS Builder ID → `+` → *Create article* → drafts
auto-save → *Preview* → *Publish* → an automated moderation scan runs (broken links,
profanity, title/description length).

---

## Article 1

- **File:** `article-1.md`
- **Title:** Agents for Humans: What if bulk buying didn't require one person to buy in bulk? *(79 characters)*
- **Word count:** **742** (prose only; excludes image markdown and link URLs)
- **Tags (5):** `agents-for-humans` · `strands-agents` · `ai-agents` · `product-design` · `prototyping`
- **Suggested description:** *Bulk pricing works by making one person buy twenty-four of something. What I got wrong building a group-buying agent for the Agents for Humans hackathon, and the coffee bug that changed the product.*
- **Links (1):** "Pool" → `https://github.com/nimarco/pool`

| Image | Alt text |
| --- | --- |
| `images/article-1-inversion-24x1.jpg` (1520×910) — after the intro | Twenty-four small figures arranged in a grid, each with one package, under the label 24 × 1. |
| `images/article-1-declare-flexibility.png` (726×1564) — end of *Twelve people bought coffee* | Pool's declaration screen: Kestrel Roastworks whole bean coffee, 3 bags every 30 days, and a choice between "Only this exact coffee" and "Any brand that matches my preferences". |

**Bonus eligibility:** build-journey post; names Strands and explains when the agent
became load-bearing.

---

## Article 2

- **File:** `article-2.md`
- **Title:** Agents for Humans: More demand doesn't always mean a better group order *(71 characters)*
- **Word count:** **811**
- **Tags (5):** `agents-for-humans` · `strands-agents` · `amazon-bedrock` · `agentcore` · `ai-agents`
- **Suggested description:** *The candidate order with the most demand behind it cost more together than buying separately. How I split the coordination between a Strands agent and deterministic code, and what actually runs where.*
- **Links (3):** "Strands" → `https://strandsagents.com/` · "The public demo" → `https://d38kno05ygcarw.cloudfront.net/verify` · "Amazon Bedrock AgentCore Runtime" → `https://aws.amazon.com/bedrock/agentcore/`

| Image | Alt text |
| --- | --- |
| `images/article-2-why-this-order.png` (724×1570) — end of *The option that looked better* | Pool's "Why this order?" screen. Kestrel Roastworks is marked "Costs more" at $367.19 together against $360.00 buying separately, from 23 bags standing across 8 people. Harbourstone Coffee is marked CHOSEN, saving $69.18 at $263.82 against $333.00, with 18 bags in 3 full cases of 6 and nothing left over. A row below reads "Nothing has been charged, ordered or assigned". |
| `images/article-2-agent-and-code.jpg` (1380×610) — in *What the model does and doesn't decide* | A two-column diagram. Agent: what is worth investigating, what should I try next — freedom to coordinate. Code: who qualifies, what does it cost, does the order actually work — no freedom to make up the math. |

**Bonus eligibility:** the AWS-heaviest post — Strands loop, the deterministic-planner
public path, and the separate AgentCore + Nova Lite deployment, each described as what it
actually is.

---

## Article 3

- **File:** `article-3.md`
- **Title:** Agents for Humans: How I built a group-buying demo without pretending the fake parts were real *(94 characters — check this against any title-length limit in the editor)*
- **Word count:** **749**
- **Tags (5):** `agents-for-humans` · `strands-agents` · `amazon-bedrock` · `agentcore` · `prototyping`
- **Suggested description:** *A prototype can use synthetic people and simulated payments and still prove the hard coordination behaviour honestly. What that cost me while building for the Agents for Humans hackathon.*
- **Links (2):** "Pool" → `https://github.com/nimarco/pool` · "The public demo" → `https://d38kno05ygcarw.cloudfront.net/verify`

| Image | Alt text |
| --- | --- |
| `images/article-3-paper-towels-7-of-48.png` (736×1492) — in *Letting things stay unresolved* | Pool's home screen showing paper towels in a WATCHING state, "Not enough demand yet": 7 packs declared, 48 required, 3 people near you. A footer line reads "Synthetic community · simulated payments · real software". |
| `images/article-3-share-my-location.png` (740×1075) — end of *Asking for a location without taking one* | Pool's setup step titled "Find people near you", with a map-pin illustration, a "Share my location" button, and the line "Synthetic location for this demo — Pool did not ask your browser where you are." |

**Bonus eligibility:** build-practice post whose central decision is an AWS one — the
zero-token deterministic public path on a function with no model permission, and the
AgentCore/Nova Lite path deployed separately and switched off for visitors.

---

## Image provenance

| File | Source | Real app? |
| --- | --- | --- |
| `article-1-inversion-24x1.jpg` | Frame from the submission film, cropped | No — original graphic, no app UI shown |
| `article-1-declare-flexibility.png` | **Captured live 2026-09-06** from the deployed demo, 390px viewport at 2× | Yes |
| `article-2-why-this-order.png` | **Captured live 2026-09-06** from the deployed demo, 390px viewport at 2× | Yes |
| `article-2-agent-and-code.jpg` | Frame from the submission film, cropped | No — explanatory diagram, visually distinct from app UI |
| `article-3-paper-towels-7-of-48.png` | **Captured live 2026-09-06** from the deployed demo, 390px viewport at 2× | Yes |
| `article-3-share-my-location.png` | **Captured live 2026-09-06** from the deployed demo, 390px viewport at 2× | Yes |

Every crop is a straight rectangular crop. Nothing was retouched, recoloured, upscaled or
composited, and no value on any screen was edited.

> **Stale as of 2026-09-10 — recapture before publishing.** All four app screenshots were
> true of the build deployed when they were taken, but the deployment has since been
> restyled: the app now reads as a flat ledger, without the nested card borders, bordered
> `How flexible are you?` fieldset, or pill-shaped `Costs more` / `Saves $69.18` badges that
> these PNGs show. Re-driven live against
> <https://d38kno05ygcarw.cloudfront.net/verify> on 2026-09-10, **every number, label and
> sentence in all four images still matches the live app exactly** — only the chrome around
> them changed — so the article prose and the alt text below remain correct. What is wrong
> is the styling, and the fix is a straight recapture at 390 px / 2×, not an edit.

All four app screenshots present the community as *Demo* rather than *Demo University*. The
two remaining film frames show no application UI at all.

---

## Factual verification — re-checked 2026-09-06

### Verified live against the deployed demo (`/verify`, driven end to end today)

- Kestrel: `$367.19` together, `$360.00` buying separately, "23 bags standing from 8 people" ✅
- Harbourstone: `CHOSEN`, `Saves $69.18`, `$263.82` / `$333.00`, `20.7%`, "18 bags · 3 full cases of 6 · nothing left over" ✅
- Member view: `$43.96` against `$55.50`, "with 5 others" (six people) ✅
- **`Host needed`** and **`Nothing charged`** on the forming order, plus "A neighbour collects the order, runs the pickup, and is paid for it" ✅
- "Nothing has been charged, ordered or assigned" ✅
- Location step reads exactly: *Find people near you* / *Share my location* / *Synthetic location for this demo — Pool did not ask your browser where you are.* ✅
- The deployed JavaScript bundle contains **zero** occurrences of `geolocation` ✅
- `/api/health` → `model_provider: offline`, `payment_provider: simulated`, `purchase_simulated: true`, `schedules_enabled: false` ✅
- `/api/demo/config` → `live_agent_available: false` ✅

### Verified against the repository

- 12 households / 3 bags each / 36 bags / minimum 18 / nine discarded as exact-only — commits `90837ba`, `ca4ed6e` ✅
- Coffee category has 26 entries incl. a vanilla creamer and a bottled Frappuccino — `BUILD_HISTORY.md` #0054 ✅
- "I declared coffee. Pool showed me whey." — `BUILD_HISTORY.md` #0040, a reported bug ✅
- "Run Pool now" button existed and was removed — #0040, #0057 ✅
- Strands chosen on day one; the agent's problem was "thin" until the strategy search — #0005 vs #0056 ✅
- Kestrel wholesale `$15.70` / retail `$18.00`, cases of 5, minimum 15 — `data/roast_coffee_fixture.py` ✅
- Five heuristics all pick Kestrel — asserted by a test, `tests/test_declaration_events.py:370–413` ✅
- Paper towels: 4 seeded units + the visitor's 3 = 7, against 4 cases × 12 = **48** — `data/seed.py` ✅
- Reversibility — `services/coordination.py::reconcile_after_declaration_change` ✅
- "so there was plenty" copy bug — commit `5b216dc` ✅
- Video-script line corrected during recording — commit `6414aa1` ✅
- Location step rewrite — commit `0598d78` ✅

### Nothing stale found

No claim in any article was contradicted by the current repo or the live deployment.

**Resolved 2026-09-10.** This section previously recorded that `README.md` named the wrong
deployment commit. The README now names `f06345e`, and that was checked rather than assumed:
building `f06345e`'s `apps/web` reproduces the exact `index-*.css` and `index-*.js` that
CloudFront serves, byte for byte.

---

## Links — all returned HTTP 200 on 2026-09-06

| URL | Status |
| --- | --- |
| `https://github.com/nimarco/pool` | 200, public |
| `https://d38kno05ygcarw.cloudfront.net/verify` | 200 |
| `https://strandsagents.com/` | 200 |
| `https://aws.amazon.com/bedrock/agentcore/` | 200 |

No localhost, signed, private or expiring URLs are used anywhere.

---

## What remains for you to do manually

Builder Center drafts could **not** be created: it requires signing in with an AWS Builder
ID, and no signed-in Chrome session was available. Entering your password is not something
I will do.

1. Sign in at <https://builder.aws.com> with your AWS Builder ID.
2. For each article: `+` → *Create article* → paste the H1 into **Title**, the rest into
   the body, upload the two images at their marked positions, paste the alt text, add the
   description and the five tags.
3. In *Preview*, check: heading order runs H1 → H2 with no skips; both images render and
   carry alt text; the four links resolve; no markdown artefacts; the phone screenshots are
   legible on a narrow viewport.
4. **Do not publish until you have reviewed all three previews.**
