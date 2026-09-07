/* Moving between screens, without the frame that shows the wrong one.
 *
 * The app renders one screen at a time out of a conditional, and it used to replace one
 * with the next in a single frame. Two things were wrong with that. There was nothing to
 * read the move *by* — the page simply became a different page. And because every
 * data-backed screen opens on a loading state that a same-origin read answers in about
 * one frame, the frame you actually saw was often neither screen: "Loading…", or an order
 * card that had not yet learned whose order it was.
 *
 * The second problem is fixed where it is caused — see `use-settled.ts`, and `isMine` in
 * views/home.tsx. What is left for this to do is the first: give the arriving screen a
 * short rise out of the page so a switch reads as a switch.
 *
 * It also covers the tail of the first problem for free. A screen that renders nothing for
 * its first frame renders that nothing at opacity zero, against the same paper that is
 * behind it either way — so the gap is not a gap on screen, and by the time the screen is
 * legible it is complete.
 *
 * An earlier version of this held the outgoing screen mounted underneath and cross-faded.
 * It looked slightly better and cost too much: two live React trees for the length of the
 * animation, duplicate headings and landmarks in the document, and the screen being left
 * still running its effects after the member had gone. Not worth 260 ms of overlap.
 */
import { ReactNode } from "react";

export function ScreenSwap({ id, children }: { id: string; children: ReactNode }) {
  /* The key is the whole mechanism: a new id is a new element, and a new element replays
     the CSS animation. Same id, no remount, no animation — which is what makes typing in
     a form or re-reading state cost nothing. */
  return (
    <div className="screen-in" key={id}>
      {children}
    </div>
  );
}
