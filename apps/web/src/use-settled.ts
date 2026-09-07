/* A wait is only worth telling somebody about once it has actually made them wait.
 *
 * Every read in this app answers from the same origin, and in the public demo it answers
 * from memory — twenty milliseconds, one frame. A "Loading…" drawn for one frame is not
 * information, it is a flicker, and a viewer reads a flicker as the screen going somewhere
 * it did not mean to go. So the pending state is real from the start and *visible* only
 * after it has outlasted a frame or two.
 *
 * The threshold is deliberately below the point where a still screen starts to feel
 * broken, and above the point where a fast answer would show anything at all.
 */
import { useEffect, useState } from "react";

export const PENDING_MS = 220;

/** True once `pending` has been continuously true for `delay` ms. */
export function useSlowEnoughToSay(pending: boolean, delay = PENDING_MS): boolean {
  const [say, setSay] = useState(false);
  useEffect(() => {
    if (!pending) {
      setSay(false);
      return;
    }
    const timer = window.setTimeout(() => setSay(true), delay);
    return () => window.clearTimeout(timer);
  }, [pending, delay]);
  return say;
}
