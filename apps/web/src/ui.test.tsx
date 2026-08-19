/* The Product's wait state is the only screen a judge watches while a real AgentCore
 * invocation is in flight, which makes it the easiest place in the whole app to lie by
 * accident. A progress bar with three steps would be a claim about three observations;
 * a browser making one HTTPS request has exactly one.
 *
 * So this pins the claim rather than the layout: name the destination, run a real clock,
 * resolve only the send, and say on screen that nothing else is being watched.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { CoordinatorWait } from "./ui";

afterEach(cleanup);

describe("the live coordinator wait", () => {
  it("names where the request went without claiming to watch it get there", () => {
    const { container } = render(<CoordinatorWait live region="us-east-1" />);

    expect(screen.getByText(/Amazon Bedrock AgentCore/)).toBeTruthy();
    expect(screen.getByText(/in us-east-1/)).toBeTruthy();
    expect(screen.getByText(/this session’s own DynamoDB workspace/)).toBeTruthy();

    // One resolved row: the send. Everything after it is named, not observed.
    expect(container.querySelectorAll(".wait-step.done")).toHaveLength(1);
    expect(screen.getByText(/Request sent from your browser/)).toBeTruthy();
    expect(
      screen.getByText(/Only the first line is something this page watched happen/),
    ).toBeTruthy();
    expect(
      screen.getByText(/Nothing in between is animated as if it were/),
    ).toBeTruthy();
  });

  it("does not name AgentCore when the deployment has no runtime", () => {
    render(<CoordinatorWait live={false} region={null} />);

    expect(screen.queryByText(/AgentCore/)).toBeNull();
    expect(screen.getByText(/running in this workspace/)).toBeTruthy();
    expect(screen.getByText(/Strands loop → Pool’s typed tools → the store/)).toBeTruthy();
  });

  it("runs a real clock rather than a scripted one", async () => {
    render(<CoordinatorWait live region="us-east-1" />);

    // The elapsed figure is the one progress signal the browser genuinely owns.
    const elapsed = await screen.findByText(/\d+\.\ds elapsed/);
    expect(elapsed).toBeTruthy();
  });
});
