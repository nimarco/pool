/* A superseded view transition must not leak an uncaught rejection.
 *
 * `startViewTransition` rejects `finished` with `AbortError: Transition was skipped`
 * when a newer transition replaces it. That is ordinary — somebody navigated twice —
 * but the returned transition was discarded, so nothing handled the rejection and it
 * surfaced as a red error in the console. Seen on the deployed demo while clicking
 * between screens.
 *
 * Asserted as the contract rather than by waiting for an `unhandledrejection` event:
 * jsdom does not deliver that event reliably under the test runner, so a test written
 * that way passes against the broken code and proves nothing. This checks the thing
 * that actually has to be true — that `finished` is handled.
 */
import { afterEach, expect, it, vi } from "vitest";

import { changeScreen } from "./screen-change";

afterEach(() => {
  delete (document as unknown as Record<string, unknown>).startViewTransition;
});

function stubTransition() {
  const finished = Promise.reject(
    new DOMException("Transition was skipped", "AbortError"),
  );
  const onCatch = vi.fn();
  // Record the handler and then genuinely swallow it, so the stub itself cannot be
  // the thing that leaks.
  const spied = { catch: (fn: (e: unknown) => void) => { onCatch(fn); return finished.catch(() => {}); } };
  (document as unknown as { startViewTransition: unknown }).startViewTransition = (
    cb: () => void,
  ) => {
    cb();
    return { finished: spied };
  };
  return onCatch;
}

it("handles the skipped-transition rejection rather than discarding it", () => {
  const onCatch = stubTransition();
  let ran = false;

  changeScreen(() => {
    ran = true;
  });

  expect(ran).toBe(true);
  expect(onCatch).toHaveBeenCalled();
});
