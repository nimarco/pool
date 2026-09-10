# Submission film — third-party audio licensing

**Not covered by this repository's MIT licence.** The film uses two third-party audio
files under their own terms. They are recorded here so the boundary is explicit, and
neither is committed to this repository — see [Why these are not in
git](#why-these-are-not-in-git).

Everything else audible in the film is original: the narration is a human read by the
author, and there is no other music, sound effect, or stock audio.

## The assets

| | title sting | outro |
|---|---|---|
| **title** | Logo Glitch Short | Soft Cinematic Piano Outro |
| **source** | <https://pixabay.com/sound-effects/musical-logo-glitch-short-182326/> | <https://pixabay.com/sound-effects/musical-soft-cinematic-piano-outro-151764/> |
| **creator** | Pixabay contributor ID `35433346` — no username shown on the item page | **Universfield** — <https://pixabay.com/users/universfield-28281460/> |
| **licence** | **Pixabay Content License** | **Pixabay Content License** |
| **uploaded** | 22 December 2023 | 31 May 2023 |
| **duration** | 6.03 s | 5.56 s |
| **attribution** | **not required** | **not required** |
| **used for** | the title card — one hit, then faded out from under the first line | the close — entering under the last line, "Pool found it.", and resolving over the held final frame |

Both upload dates are after January 2019, so both are under the **Pixabay Content License
and not CC0**. Pixabay content from before that date was CC0; these are not, and neither
should be described as public domain.

## What the licence permits, and the one clause that bears on this project

Permitted, quoting the licence summary: use the content for free, "Modify or adapt Content
into new works", and use it "without having to attribute the author (although giving credit
is always appreciated by our community!)".

The clause that matters here:

> "You cannot sell or distribute Content (either in digital or physical form) on a
> Standalone basis. Standalone means where no creative effort has been applied to the
> Content and it remains in substantially the same form as it exists on our website."

Two consequences, both already satisfied:

1. **Using them in the film is fine.** Each is attenuated, filtered, faded, timed against a
   measured narration clock and mixed under a five-minute film — creative effort applied,
   not standalone.
2. **Committing the raw mp3s to a public repository would not be.** Pushing them unchanged
   to GitHub distributes them in substantially the same form as Pixabay hosts them. So they
   stay out of git.

Also relevant and satisfied: no trademark or logo use, neither is used as part of a trade or
service mark, and nothing about the use is misleading.

## Attribution

**None is required for either file.** If you want to credit anyway — the licence says it is
appreciated — the outro has a named creator and the sting does not, so the honest line is:

> Audio: "Soft Cinematic Piano Outro" by Universfield, and "Logo Glitch Short", via Pixabay.

## Why these are not in git

The whole video production tree is local-only (see the `video/` section of
[`.gitignore`](../.gitignore)), and these two files would be excluded even if it were not.
The film stays reproducible from this file: both source URLs are above, the mixer picks up
whatever it finds in its two audio directories, and re-downloading them rebuilds the same
mix.

Nothing in this repository claims either file is MIT-licensed.

## Other third-party material in the film

Imagery and typography are covered separately, in
[VIDEO_MEDIA_MANIFEST.md](VIDEO_MEDIA_MANIFEST.md) §4 — in short: Open Food Facts product
names and photographs (data ODbL-1.0, images CC-BY-SA-4.0, attributed on screen inside the
app's own product search), and the fonts the app already ships.
