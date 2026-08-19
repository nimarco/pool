/* Test environment shims.
 *
 * jsdom declares the APIs a real browser has and throws "Not implemented" for the ones
 * it does not actually do, which turns ordinary product code — scrolling to the top of a
 * new step — into pages of stack traces that hide real failures. Stubbing here keeps
 * that noise out of the suite without putting an `if (test)` in a component.
 */

import { vi } from "vitest";

window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
