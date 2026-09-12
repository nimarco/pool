# Agents for Humans: My agent gets eight tries, then it stops

[Pool](https://github.com/nimarco/pool) is a group-buying coordinator I built for the Agents for Humans hackathon: you say what you already buy, it looks for enough compatible demand nearby to order it together, and an agent does the searching.

The interesting engineering was not teaching it to search. It was deciding in advance everything it would never be allowed to do.

## The budget

Every run gets eight model iterations, twenty-five tool calls, two repeats of any single call, and forty-five seconds. When a bound is reached the run ends and records which bound ended it.

None of these are tuned for output quality. They exist so a run has a worst case I can write down. An agent that can loop is an agent whose cost and latency are whatever the model feels like today, and "whatever the model feels like" is not something you can put in front of a person.

The duplicate bound is the one I would recommend to anybody. Two identical calls is curiosity. Three is a loop wearing a hat.

## That timeout is softer than it sounds

Forty-five seconds is cooperative, not pre-emptive. The bounded runner checks the clock before each model call and before each tool call, so it ends a run that is *taking* too long. It cannot interrupt a single call that has already hung.

So the deployment nests harder rungs behind it: the bridge's read timeout, then the AWS Lambda timeout. The in-process bound is the polite one. The outer two are the ones that genuinely cannot be talked past.

I only wrote that distinction down because the number itself had been wrong in a way nobody would ever have reported. The default was 120 — a value no deployment actually used, longer than the function timeout that would have killed the run first, and the figure anyone running it locally would read off the health endpoint while the video and the diagrams both said 45. One value, in every place a run can execute.

## A bound I deleted instead of building

There was going to be a retry bound: how many times may the agent re-attempt a tool that failed?

I removed it. Automatically re-running a consequential tool is the wrong default for a system that moves money — the safe answer to a call that failed, and might have half-succeeded, is to stop and say so, not to try again and hope. The setting only made sense if retrying was the default behaviour, and retrying should not be the default behaviour, so the honest fix was to delete the knob rather than choose a number for it.

## Seventeen doors

The agent's entire surface is seventeen tools. It cannot reach the database, the pricing code, or anybody's money except through them. Whatever it decides, it decides by choosing which door to open and in what order.

That is the part I would defend hardest. The interesting question is not how clever the loop is. It is how small you can make the set of things it is able to do while still letting it do the job.

## The gate it cannot talk past

Before any order locks, a deterministic evaluator runs thirteen checks: supplier minimum, quote freshness, case fitting, host assignment, host pay, buyer savings, every buyer's own authorisation rules, platform economics, timing, pickup, funding.

It runs at two stages, because two different questions are being asked. Before funding: is this worth issuing a final offer for? At the lock: may we take these people's money? The first skips the funding check and reasons about provisional demand. The second runs all thirteen, and the answer has to rest on stored facts rather than on anything the model said.

None of those thirteen belong to the agent. It can propose a group. It cannot vote on whether the group is allowed.

## The number that was two answers

Here is one I got wrong and caught late.

The savings check reported "net landed savings $X after all costs". But host pay is part of what buyers pay, and until a neighbour actually accepts the job there is no reward to price it with — so the pricing code puts zero in its place.

As a gate that was always correct: nothing can lock while the host checks two lines above are still failing. As a *sentence* it was wrong. It overstated the saving by exactly the host's pay, and printed a larger number directly beside the smaller one the member sees on their own order. Two numbers, one question, no explanation offered.

The fix was not to the arithmetic. It was to say what the number actually is: savings *before host pay, which is not known until a host accepts*. Name the basis instead of the total, and the two can never read as two answers to the same question.

Every check in that engine prints a sentence a person will read. I had been reviewing them as booleans.
