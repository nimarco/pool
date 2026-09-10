# Demo video — media manifest and truth statement

Every element in the submission film, where it came from, and what it is allowed to claim.

The film this repository submits is the **human-narrated cut, runtime 4:49.70** —
1920x1080, 30 fps, mono AAC, -21.0 LUFS integrated.

Companion to [VIDEO_SCRIPT.md](VIDEO_SCRIPT.md) and
[VIDEO_STORYBOARD.md](VIDEO_STORYBOARD.md).

---

## 1. The short version

- **No stock footage. No stock photography. No third-party imagery of any kind.**
- Every non-product frame is original, drawn for this film in Pool's own design tokens.
- Every frame that shows Pool *doing* something is a screen recording of the real
  application answering real requests.
- No AgentCore or Bedrock invocation was made to produce any part of this video.
- Nothing was purchased, charged, or ordered; no supplier was contacted; no host was paid.

## 2. Product footage — the real application

| Segment | What it records | Beats |
| --- | --- | --- |
| `declare.webm` | A cold session: `/verify` → name → search *Kestrel* → three bags → allow alternatives → whole bean, caffeinated, dark → save → the order that forms | 6, 7, 14 |
| `why.webm` | The same session, then **Why this order?** and its two costed options | 8 |
| `towels.webm` | The same session plus a paper-towels declaration, and the watching state it produces | 9 |
| `exact.webm` | The same session plus towels, then the coffee declaration edited to *only this exact coffee*, and the consequence | 10 |
| `community.webm` | The same session plus towels, then the community's standing needs and the order's open host role | 11 |

**Provenance.** Captured with Playwright against the public-demo build of commit
`41c5d27bf1374d47bb6cdd934cacf0781e97469f`, run through
`scripts/run_public_demo_local.sh` — the same process shape, judge mode, offline planner,
simulated payments and simulated purchasing that the deployed stack runs, with an
in-memory store instead of DynamoDB. Browser at 390 × 844 with
`--force-device-scale-factor=2`, recorded at 780 × 1688.

**What is real in them.** The declaration is genuinely saved through the API. The
coordination run genuinely happens. The order on screen is the one the server formed,
priced by the deterministic evaluator: `$43.96` against a `$55.50` retail baseline, 18
bags, six buyers, past a 12-bag supplier minimum. The refusal of Kestrel at `$367.19`
against `$360.00`, the selection of Harbourstone at `$263.82` against `$333.00`, the
`7 of 48` paper-towel shortfall, the 51 standing declarations, and the removal from the
order after the exact-only edit are all server-computed and read back from stored rows.

**What is not.** Every workspace is seeded from the synthetic Demo University community:
the other households, Kestrel Roastworks, Harbourstone Coffee, Beanline Wholesale and
their quotes are fixtures, not real people or real suppliers. Payments and purchasing are
simulated. The order is provisional and stays that way.

**The one compositing mark inside the phone.** A soft green ring is drawn at the point of
each tap, for the same reason a phone screen-recording overlay draws one — the app has no
cursor of its own and a demo that shows effects without causes is unreadable. It is added
by the recorder (`record_app.mjs`, `tap()`), not produced by the app, and it never
substitutes for an interaction: every tap it marks really happened.

**Editing.** Segments are trimmed to length and their order is chosen; nothing inside a
shot is sped up, slowed down, reversed, spliced, or composited over. Scrolls are the
browser's own smooth-scroll, driven by the recorder.

## 3. Original graphics — everything that is not the product

All authored for this film in `scenes/`, rendered frame-by-frame by Playwright at
1920 × 1080, in the design tokens from `apps/web/src/styles.css`.

| Asset | What it is | Beats |
| --- | --- | --- |
| `hook` | A tower of twenty-four packs and one person; a camera pull-back | 1 |
| `inversion` | The tower flying apart into twenty-four people, `1 × 24` → `24 × 1` | 2 |
| `campus` | A density field, a walking radius, four category chips | 3 |
| `chaos` | An illustrated group chat, a spreadsheet, two payment requests, boxes | 4 |
| `reveal` | The Pool mark and wordmark | 5 |
| `split` | The agent/code two-column comparison, and the phone handoff | 12 |
| `stack` | Strands → typed tools → DynamoDB, and the two deployment lanes | 13 |
| `close` | The `1 × 24 → 24 × 1` callback and the closing lines | 15 |
| `ann_*` | The annotation columns beside the phone | 7–11 |
| `captions` | The burned-in caption layer | all |
| `plate.png` | The phone body — bezel, radius, speaker slot, shadow | 6–12, 14 |
| `bg.png` | The paper the phone stands on | 6–12, 14 |
| `grain.png` | A 320px monochrome grain tile, generated deterministically | all |

**The group chat is an illustration and is labelled as one.** It depicts no real product,
imitates no real messaging app's interface, and shows no real conversation. The names are
initials and a first name. It is marked `ILLUSTRATION` on screen.

**The phone is not a product.** No manufacturer's industrial design, no logo, no operating
system, no status bar. A rectangle with a radius and a bezel.

## 4. Third-party assets

| Asset | Source | Licence | Attribution required | Where it appears |
| --- | --- | --- | --- | --- |
| **Instrument Serif** (400 normal, 400 italic) | [Instrument Serif project](https://github.com/Instrument/instrument-serif), via `@fontsource/instrument-serif` | SIL Open Font License 1.1 | No (OFL requires the licence to travel with the font files, which it does in `apps/web/node_modules` and any redistribution) | Every display heading, in the film and in the app |
| **System sans** (`-apple-system` / Helvetica Neue) | macOS | System font, used for rendering only | No | Body text and captions |
| **Open Food Facts product names and photographs** | [openfoodfacts.org](https://world.openfoodfacts.org/), dated snapshot 2026-08-19 | Data ODbL-1.0; images CC-BY-SA-4.0 | Yes — and it is, on screen, inside the app's own product search, visible in the film during beat 6 | The catalogue a member searches |

No stock media, no AI-generated imagery, no scraped images. The only other third-party
material is the two licensed audio files in §5, itemised in
[VIDEO_AUDIO_LICENSING.md](VIDEO_AUDIO_LICENSING.md).

## 5. Audio

**The narration is a human read, performed by the author.** It was recorded locally,
take-reviewed, and never sent to any transcription or synthesis service. The picture was
then timed to that read rather than the other way round. The mix is mono at **-21.0 LUFS**
integrated (the spoken-word standard for mono; the perceptual equivalent of -16 LUFS
stereo), LRA 3.8 LU, true peak -5.1 dBTP.

Earlier cuts used a macOS `say` reference voice as a stand-in. That is no longer what
ships, and the timings in [VIDEO_SCRIPT.md](VIDEO_SCRIPT.md) and
[VIDEO_STORYBOARD.md](VIDEO_STORYBOARD.md) are that earlier cut's — see the status note at
the top of each. The authoritative cue times are the caption track embedded in the
delivered film.

**There are two pieces of licensed music**, both Pixabay Content License, neither requiring
attribution: a short glitch sting under the opening title card, and a soft piano outro that
enters under the last line and resolves over the held final frame. Full provenance —
source URLs, creators, licence text, and the standalone-redistribution clause that keeps
them out of git — is in
[VIDEO_AUDIO_LICENSING.md](VIDEO_AUDIO_LICENSING.md).

## 6. Truth boundaries, as stated on screen

The film says all of the following out loud or shows it in the app:

- **"In this prototype, purchasing and payments are simulated. Nothing has actually been
  charged."** — spoken at 2:49.5, and shown as a band at 2:49–2:56.
- **"The public demo runs a deterministic planner, so any judge can reproduce it at zero
  model tokens."** — spoken at 3:24.2. `PUBLIC_DEMO_AGENTCORE_ENABLED=false` on the
  deployed stack; the visible coffee and paper-towel runs are the bounded Strands loop with
  the offline planner and spend nothing.
- **"The same bounded agent is separately deployed on Amazon Bedrock AgentCore, with Nova
  Lite."** — spoken at 3:30.2, and stated as *deployed separately* on screen. The film
  never claims Nova produced the run it just showed.
- **"We still need live supplier inventory and pricing before any of this is a real
  purchase."** — spoken at 3:37.2.
- The order's own status chips — **Forming**, **Host needed**, **Nothing charged** — are
  on screen for the whole of beats 7 and 14.

And these claims are never made:

- that any stock actor or illustrated figure is a Pool user — there are no photographs of
  people in the film at all;
- that any sourced footage is footage of a Pool pilot — there is no sourced footage;
- that Pool has any relationship with Costco. The narration names it once, at 3:45.3, as
  the comparison every listener already understands. No logo, no mark, no implication of
  partnership.

## 7. Reproducing the film

Working directory (not committed — it holds ~300MB of intermediates):

```
script.json        the narration: text, and the silence before each line
timeline.py        → beat table, SRT, caption cards. The voice is the clock.
record_app.mjs     drives the real app and records each product segment
scenes/            the graphics, as deterministic functions of t
render_scene.mjs   one screenshot per frame, so a render is exact rather than smooth
make_plate.mjs     the phone body and the paper it stands on
build.py           cuts every beat to the timeline and muxes the deliveries
```

Rebuilding needs `scripts/run_public_demo_local.sh` on `:8000`, a static server on `:8181`
for `scenes/`, Playwright with Chromium, and ffmpeg. It costs nothing and touches no AWS
service.
