/* A wait is only worth telling somebody about once it has actually made them wait.
 *
 * Every read in this app answers from the same origin. A "Loading…" drawn for one frame
 * is not information, it is a flicker, and a viewer reads a flicker as the screen going
 * somewhere it did not mean to go. So the pending state is real from the start and
 * *visible* only after it has outlasted a frame or two.
 *
 * The threshold is deliberately below the point where a still screen starts to feel
 * broken, and above the point where a fast answer would show anything at all.
 *
 * 220 ms was that number when this ran from memory and answered in about twenty
 * milliseconds. It is not that number on the deployed demo, where the same reads go out
 * to CloudFront and a Lambda and come back in 420-510 ms measured. At 220 the spinner
 * appeared at ~285 ms and was gone by ~505 — 220 ms of "Loading…" between a blank screen
 * and the answer, which is three states in half a second and exactly the flicker this
 * module exists to prevent. Raised above the real read so a normal answer shows none of
 * it, and a genuinely slow one still says so.
 */
import { useEffect, useState } from "react";

export const PENDING_MS = 600;

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
