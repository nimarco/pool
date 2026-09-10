# Demo video — storyboard and runtime

Companion to [VIDEO_SCRIPT.md](VIDEO_SCRIPT.md) (what is said) and
[VIDEO_MEDIA_MANIFEST.md](VIDEO_MEDIA_MANIFEST.md) (where every pixel came from). This
file is what is *shown*, and for how long.

> **Status.** The runtime and beat times below are the **earlier synthetic-voice reference
> cut's**. The submitted film is a human read and runs **4:49.70** — still inside the 5:00
> limit, with 10.3 s to spare. The beat *order* below is still the film's; the numbers are
> not. See [VIDEO_MEDIA_MANIFEST.md](VIDEO_MEDIA_MANIFEST.md).

**Reference-cut runtime: 4:01.56.** The hackathon limit is 5:00 and the brief's target
window was 3:35–4:05.

---

## 1. The shape

Fifteen beats, three kinds.

| | Beat | In | Out | Length | Kind |
| --- | --- | --- | --- | --- | --- |
| 1 | Hook — one person, twenty-four packs | 0:00.00 | 0:09.41 | 9.41 | graphic |
| 2 | The inversion — `1 × 24` → `24 × 1` | 0:09.41 | 0:18.24 | 8.84 | graphic |
| 3 | The campus — density and categories | 0:18.24 | 0:27.94 | 9.69 | graphic |
| 4 | The coordination job — chat, sheet, requests | 0:27.94 | 0:44.69 | 16.75 | graphic |
| 5 | Pool — the mark | 0:44.69 | 0:47.60 | 2.91 | graphic |
| 6 | Declaring what I buy | 0:47.60 | 1:12.37 | 24.78 | **product · phone** |
| 7 | The order Pool formed | 1:12.37 | 1:37.10 | 24.73 | **product · phone** |
| 8 | Why this order — Kestrel loses | 1:37.10 | 2:01.81 | 24.71 | **product · phone** |
| 9 | Seven against forty-eight | 2:01.81 | 2:17.60 | 15.79 | **product · phone** |
| 10 | Taken out of the order | 2:17.60 | 2:32.77 | 15.16 | **product · phone** |
| 11 | Fifty-one needs, and the open job | 2:32.77 | 2:55.99 | 23.22 | **product · phone** |
| 12 | Agent and code | 2:55.99 | 3:20.70 | 24.71 | phone → diagram |
| 13 | How it runs — Strands, tools, store | 3:20.70 | 3:36.81 | 16.11 | diagram |
| 14 | Back to the phone | 3:36.81 | 3:44.43 | 7.62 | **product · phone** |
| 15 | Close — the callback | 3:44.43 | 4:01.56 | 17.13 | graphic |

Beat boundaries are not chosen; they are computed. `timeline.py` lays each narration cue
after the previous one plus its own written-in silence, then gives each beat a short tail
so it never cuts on a final syllable. The picture is built to those numbers, so it cannot
drift from the voice.

## 2. Screen time

| | Seconds | Share |
| --- | --- | --- |
| Real product, in a phone | 140.5 | **58.2 %** |
| Diagram / desktop-scale proof | 36.3 | 15.0 % |
| Title cards and illustration | 64.7 | 26.8 % |

The brief asked for 80–90 % of the *consumer and product* storytelling to be mobile-first.

- Of the eight beats that show Pool at all (6–14), **79.5 % is the phone** — 140.5s of
  140.5 + 36.3.
- Of the seven beats that are consumer storytelling (6–11 and 14), **100 % is the phone**.
  No desktop appears anywhere in the member's story.
- Desktop-scale layout appears exactly where the brief allows it and nowhere else: the
  architecture argument in beats 12–13, which is a two-column comparison and a three-node
  chain — shapes a phone cannot hold.

## 3. The phone

A 430 × 931 screen inside a 456 × 961 body: bezel, radius, speaker slot, one shadow. No
branded hardware, no fake status bar, no OS chrome Pool does not own.

The app is recorded at 390 × 844 with a forced device scale factor of 2 — a true
780 × 1688 raster — and scaled **down** to the screen, never up. Pool's 15px body text
lands at about 16.5px in the 1920 × 1080 frame; the price on the order card lands at 33px.

Two placements, and one move between them:

- **centred** while the phone is the whole story (beats 6 and 14),
- **left**, with an annotation column at x 900–1780, whenever there is something to say
  beside it,
- and in beat 7 it *slides* from one to the other at 1:13.7, so the same screen is never
  in two places across a cut.

Beat 12 is the handoff the brief asked for: the phone shrinks to 42 % and leaves to the
left under the caption *what the student sees → what makes it work*, and the diagram takes
the space it vacates. It carries a real screenshot of the order — the frame the previous
beat ended on — so the cut away from the product is a cut away from something the viewer
recognises.

## 4. Beat notes

**1 · Hook.** A single column of twenty-four packs builds one at a time past the top of
the frame, then the camera gives up and pulls back to 46 %, revealing the whole tower and
a person about a fourteenth of its height. The count runs `×1 … ×24` as it builds.

**2 · Inversion.** Reconstructs the hook's final frame exactly — same scale, same floor,
same person — then flies the packs into a 8 × 3 grid, each landing under a person. The
strongest visual moment in the film, and the only one that has to be a continuation
rather than a cut.

**3 · Campus.** 460 dots, thinning outward, with a dashed walking radius. Four category
chips arrive on the four words that name them.

**4 · The coordination job.** A phone-shaped group chat, filling bottom-up the way a real
thread does, with the questions that kill these efforts: *what flavor · how much is it ·
can I get another brand · where do we pick it up · who's collecting the money*, then
**actually nvm** in red. A spreadsheet and two payment requests pile up beside it. Marked
`ILLUSTRATION` in the corner, because it is one.

**5 · Pool.** The six ring dots land one at a time; the wordmark follows.

**6 · Declaring what I buy.** One continuous session of the deployed build. The phone
slides up into frame over 0.75s. Nothing is pre-arranged and nothing is skipped: the name,
the search, the product, the quantity, the consent gate, the three preference answers, and
one save. The narration's "Done." lands on the button.

**7 · The order Pool formed.** The result is on screen before the first line of narration.
The phone then moves left and four ticks arrive: *didn't create a group · didn't invite
anyone · didn't choose the supplier · didn't pick Harbourstone*. The card holds for
twenty-two seconds because that is the point of the beat.

**8 · Why this order.** Scrolled to the two costed options, held long enough to compare
them. `$367.19` against `$360.00` on the refused one; `$263.82` against `$333.00`,
`20.7%`, and **CHOSEN** on the one that worked.

**9 · Seven against forty-eight.** A second declaration that correctly forms nothing. The
annotation waits until 2:13 and then says the three things the beat is for: *no fake deal ·
no forced group · it waits*.

**10 · Taken out of the order.** One edit, one consequence, no round trip. The app's own
words: *"An order filled without your units — a group order for this has already formed,
and it filled to a whole case without your units. Your declaration stays standing for the
next one."*

**11 · Fifty-one needs, and the open job.** The community count and four representative
rows, then the order's own **Host needed** state and what the job is. Closes with the
disclosure band: *purchasing and payments are simulated · nothing has been charged*.

**12 · Agent and code.** Two columns. Left, in moss: *what is worth investigating? what
should I try next?* — freedom to coordinate. Right, in graphite: *who qualifies? what does
it cost? does the order actually work?* — no freedom to make up the math.

**13 · How it runs.** `STRANDS → TYPED TOOLS → DYNAMODB`, and two lanes underneath:
*public demo — deterministic planner · 0 model tokens*, and *deployed separately — Amazon
Bedrock AgentCore · Nova Lite*. No IAM, no run ids, no iteration counts, no CloudFront.

**14 · Back to the phone.** The order again, centred, while the honest limit is stated.

**15 · Close.** `1 × 24 → 24 × 1` lifts out of centre to make room for *Nobody organised
the group. / Pool noticed.* One fade to paper.

## 5. Captions

Two lines maximum, balanced, broken where a person would pause — never on an orphan word.
They sit at y 996, below the phone body, which ends at 991: the caption cannot cross the
device in any beat. Set in the film's own face rather than a subtitle renderer's.

The reference cut had three deliveries: `pool-demo.mp4` (narrated, captions as a soft
subtitle track), `pool-demo-captioned.mp4` (the same picture, captions burned in),
`pool-demo-silent.mp4` (picture only), plus `pool-demo.srt` as a sidecar. The submitted
human-narrated film is a single delivery with its captions embedded as a soft subtitle
track. None of these files is committed; the video production tree is local-only.

## 6. What was rejected

- **Stock photography and footage.** Searched and passed on. The CC0 pool for "warehouse
  pallet", "paper towels", "package room" is thin, and what exists does not survive contact
  with a typographic film in Instrument Serif and warm paper. Mixing two or three
  photographs into an otherwise designed film reads as a budget, not as a choice. Every
  non-product frame is drawn in the product's own design tokens instead.
- **Background music.** Permitted by the brief and skipped: this environment cannot listen
  to it, and a bed nobody has heard under a synthetic voice is a risk with no upside. The
  silent cut and the cue timings are delivered so one can be laid under it later.
- **A caption card behind the captions.** Two lines of ink on paper read fine and keep the
  frame looking like the film.
