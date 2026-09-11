# Demo polish audit — 2026-09-11

Scope: the frozen film and settled mobile screens, economics, agent behavior, data,
API contracts and infrastructure configuration are unchanged. Only the Demo drawer
adds a normal visible control. No file under `video/` was written.

## Measured defects and fixes

| Defect | Before | Implemented and tested |
| --- | --- | --- |
| Supplier proof disappears after setup | No member drawer route; only an onboarding link | First section of Demo drawer, plus a direct README link |
| Needs navigation reveals content in stages | Full-text animation-frame sample: heading at 72 ms, list at 518 ms — 446 ms incomplete | Last successful server read initializes the arriving screen; normal read still runs. Local sample with 500 ms injected latency: complete screen at 58 ms |
| Home navigation reveals content in stages | Heading/body at 50 ms; detail link and cadence at 485 ms — 435 ms incomplete | Same bounded presentation snapshots; complete local screen at 52 ms |
| Failed needs reads claim the account is empty | Both Home and Needs convert rejected reads to `[]` | Explicit read error and manual retry, without claiming an empty account |
| Coffee order completes rice proof | Any member opportunity counted as the walkthrough's completed order | Completion also requires the server's rice outlook to be `in_pool` |
| Reloading an explanation produces an empty screen | `?screen=why` restores the screen without its declaration ID | Restores Home, like the existing pool-detail fallback to Orders |

Orders already transitioned completely in 50 ms live, with no console errors. The
original navigation probe inspected only 72 body characters and missed both partial
screens; the full-text probe exposed them. No timer was lengthened to hide the defects.

Snapshots hold at most one needs response and one pool response in memory. They are
partition scoped, cleared on writes and scope changes, and never replace normal reads.
A generation check prevents a read started before a write from repopulating them later.
They retain server values; they perform no domain calculations. Both supplier import
methods use the same write invalidation boundary, preserving multipart upload behavior.

## Visual proof

All four committed Builder Center PNGs have **PSNR = inf** against the local production
build, at 390 px and device scale 2, full-page, with no image editing. This was also
established against the unchanged deployed baseline before comparison with the fix.

The original screenshots were captured on September 11 UTC / September 10 evening in
America/Chicago. Re-running with today's live clock initially produced 43.97 dB on the
declaration and 31.82 dB on towels: the date-dependent allowance said 14 rather than 15
days, and Home said morning rather than evening. Pinning only browser Date to
`2026-09-11T02:00:00Z`, with timezone `America/Chicago`, made all four baseline images
exact. The same clock was then used for the changed build. Timers and animations run
normally; no screenshot pixels or page text are patched.

Reproduce captures, full-text navigation samples, canonical facts, and the supplier
walkthrough with an existing Playwright installation:

```sh
node scripts/audit_demo_polish.mjs /tmp/pool-audit
# For a local production server:
POOL_CAPTURE_URL=http://127.0.0.1:8000/verify node scripts/audit_demo_polish.mjs /tmp/pool-local-audit
```

The script uses the existing Playwright installation in the recording project without
writing there. Alternatively set `POOL_PLAYWRIGHT_PACKAGE` to the absolute package.json
of another project with Playwright installed. Outputs go only to the supplied directory.
Compare each PNG with its namesake in `docs/builder-center-final/images/` using FFmpeg's
`psnr` filter. The script also stores full screen facts and actual coordination responses.

## Regression evidence

Each behavioral regression was executed red before its fix (or with the fix temporarily
removed), then green after restoration:

- App: member drawer route after onboarding, with operator reset absent and verify scope retained.
- App: complete needs list during a deliberately unresolved arrival read.
- Home: member allocation retained during an unresolved pool read.
- API: a pre-write in-flight read cannot repopulate invalidated snapshots.
- Home and Needs: failed read, truthful error, one explicit successful retry.
- Judge: an existing unrelated order cannot complete the rice proof.
- App: explanation reload cannot leave a blank main screen.

The first test run also exposed test isolation that did not reset verify scope; that
cleanup now resets both module-level scopes. One initial retry assertion was ambiguous
because a product appears in both the member list and community list; it now permits
both rendered occurrences. Neither test issue was suppressed.

## Deliberately left alone

The duplicate `.reveal` definitions and the reported faint onboarding handoff frame
remain as recorded in the film. The earlier intermittent lifecycle pool-read 404 did
not recur, so its root cause remains unproven. There is no speculative backend fix.
Cold loads still require server reads; retaining a prior answer helps navigation, not a
browser with no prior answer. Explanation detail URLs fall back to Home because their
record identity is not encoded in the existing route.

Final local checks: **206 web tests, 1,318 agent tests, 86 infrastructure tests**, lint,
typecheck, build and secret scan passed. Infrastructure tests initially hit a sandbox
permission error in the JSII cache, then passed with that local access allowed; the run
took 465.69 seconds traversing local assets. No infrastructure code was changed.

Deployment and final live verification are recorded below after observation.
