# Agents for Humans: I made my group-buying demo less impressive on purpose

[Pool](https://github.com/nimarco/pool) coordinates group purchases between neighbours: you say what you already buy, and it looks for enough compatible demand nearby to order it together. I built it for the Agents for Humans hackathon.

A hackathon demo rewards you for looking capable. Most of the decisions I'd defend did the opposite. Here they are, including two where the project caught itself being wrong.

One thing to name up front: the community, the households and the supplier quotes in the walkthrough are scripted. The compatibility rules, the case fitting, the pricing, the agent loop and every record you can read back are not.

## A declaration that finds nothing

Alongside coffee I declare paper towels. Pool finds seven packs of demand nearby; the supplier minimum is forty-eight. So nothing forms, my declaration stays standing, and the screen tells me what is missing.

Seeding a world where every declaration resolves would have been easy, and it proves nothing. A system that always finds a deal is one you can't trust when it does.

## A sentence that was wrong while the logic was right

There's a copy bug from that screen I still think about. A refusal used to end with "so there was plenty" — written for a different refusal, and printed on all of them. So the paper-towels screen described seven packs against a minimum of forty-eight as *plenty*.

The arithmetic was correct the entire time. The sentence was not, and the sentence is what a person reads. I now treat copy as something that can be wrong independently of the code underneath it.

## An order that admits what it's missing

The order that does form says **host needed**, because no neighbour has agreed to collect it yet, with one line explaining that hosts are paid for the work. No card is touched and no supplier is contacted. Nothing invents an acceptance to make the screen look finished.

## Undoing it

Plenty of agent demos show the system doing something. Very few show you taking it back.

If I edit my coffee declaration to *only this exact coffee*, Pool removes my units from the order. It re-forms without me, to a whole case, and my declaration returns to standing. Nobody is out of pocket.

I got this wrong in my own video script. I'd written that Pool would "rather lose the order" than substitute against a stated preference. It doesn't — it removes me and lets the order survive. The script changed, not the code.

## Taking the model out of the loop

[The public walkthrough](https://d38kno05ygcarw.cloudfront.net/verify) runs the real [Strands](https://strandsagents.com/) loop and the real tools, with a deterministic planner standing in for the model. Every run records which provider produced it, so a planner run can never be read as a model run.

Two reasons, neither of them about hiding anything. It makes the walkthrough reproducible — run it ten times, get the same trace, no account, no cost. And nobody can spend my credits, because the function serving that page has no permission to call a model at all.

Live model execution is a separate deployment: the same bounded agent on [Amazon Bedrock AgentCore Runtime](https://aws.amazon.com/bedrock/agentcore/) against Amazon Nova Lite, over the same DynamoDB table, switched off for public visitors.

## A true sentence that expired

The walkthrough page claimed there was no *run* button. That was true when I wrote it. Then Home got an **Ask Pool to check now** button one click away, and the denial outlived its truth — a reader could have disproved my own page without leaving it.

Saying what the button actually does was the better sentence, because it survives someone pressing it. Every claim I make about a system has an expiry date attached to a commit I haven't written yet.
