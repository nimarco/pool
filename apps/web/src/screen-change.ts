import { flushSync } from "react-dom";

/* Running a screen change as one visual move.
 *
 * Split from screen-swap.tsx only because a module that exports a component should export
 * nothing else — see the react-refresh rule. The reasoning lives here.
 *
 * The keyed animation in screen-swap.tsx brings the arriving screen up, but it cannot fade
 * the one being left: by the time it runs, that screen has already been unmounted, so a
 * switch shows one frame of bare paper between the two. At 25 fps — which is what the film
 * records — that frame is a blink.
 *
 * The browser will do the part React cannot. `startViewTransition` takes a snapshot of
 * the page as it is, lets the DOM change, and animates the snapshot out
 * while the result comes in — at the compositor, with no second React tree, no duplicated
 * document, and nothing of the old screen left to take a click. Those were the costs that
 * made holding the outgoing screen in React a bad trade.
 *
 * What it animates is a swipe: the screen being left travels off one edge while the screen
 * arriving comes in from the other. A dissolve was tried first and read as one screen
 * glitching into another, because a dissolve through a page of mostly-white paper spends
 * its middle looking like neither screen. A slide never does — there is always a whole
 * screen under the eye, and the direction says which way through the app you went.
 *
 * `flushSync` is required rather than incidental: the snapshot is taken when the callback
 * returns, so an ordinary `setState` would hand it a page that has not changed yet.
 *
 * Where it is unavailable, the update simply happens and the keyed animation handles the
 * arrival on its own — which is why `html.can-cross-fade` stands that animation down only
 * when there is something better to stand down for.
 */
type Transitional = Document & {
  startViewTransition?: (cb: () => void) => { finished: Promise<void> };
};

/** Kept in step with the `screen-arrive` animation in styles.css. */
export const SWAP_MS = 260;

export function supportsCrossFade(): boolean {
  return (
    typeof document !== "undefined" &&
    typeof (document as Transitional).startViewTransition === "function"
  );
}

function asksForLessMovement(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/** Which way the app is moving. A screen that swipes in from the right when Back was
 *  pressed says the opposite of what happened. */
export type Direction = "fwd" | "back";

/** Run a screen change as one visual move, in a stated direction.
 *
 *  Safe to call when the browser cannot do it: the update simply happens, and the keyed
 *  fallback animation in styles.css brings the arriving screen in on its own.
 */
export function changeScreen(update: () => void, dir: Direction = "fwd"): void {
  const doc = document as Transitional;
  /* Read by the `[data-nav]` rules in styles.css. Set before the transition starts, and
     left in place: it describes the move that just happened, and the next move sets it
     again. */
  if (typeof document !== "undefined") document.documentElement.dataset.nav = dir;
  if (asksForLessMovement() || typeof doc.startViewTransition !== "function") {
    update();
    return;
  }
  doc.startViewTransition(() => {
    flushSync(update);
  });
}
