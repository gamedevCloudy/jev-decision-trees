# Findings brief

Condensed on 2026-10-11 from `docs/`. Sentences stay short. Numbers come from the run notes.

## The object

A decision call scores typed questions on one state. Questions in one call do not see each other. A later call sees an earlier answer only when the host copies that answer into the next state. That copy is an edge. A tree is a chain of edges. A forest is several trees on one root state. The forest rule is still open.

The decision model only scores a node. It does not write the tree. A language model may write node text. The scorer stays fixed, so a text change has one cause.

## What was measured

Runs 001 and 002 ask for the next action on a short support transcript. The actions are `reply`, `ask`, `escalate`, and `wait`. Tone and Fact are noul questions. Next is the choice. The reference is one DeepSeek answer. The scorer is `typesafe/jev-1.13`. The question text is frozen. No model writes a node in these two runs.

The flat call puts Tone, Fact, and Next in one request. Next does not see the other answers. The chain gives Fact the Tone answer, then gives Next both answers. The dag scores Tone and Fact apart, then gives Next both answers. Fact-chain, in run 002 only, skips Tone. Next sees the Fact answer. No run uses a threshold. The host always calls the next node.

The claim rule was fixed before run 002. A gain is the graph match count minus the flat match count. A gain of 0 or 1 leaves the flat call in place. A gain of 2 or more keeps that graph, with the extra cost in the same sentence. A loss of 2 or more says the handoff lowers the match count.

## Results that fix the claim

Run 001 is the pilot. Flat, chain, and dag each match 9 of 10. The shared miss is c05. The reference says ask. Each leaf says reply. Items c06 and c11 have no reference choice. The reference cap was 256 tokens. The flat cost is $0.000272958. The chain costs $0.000458598 more. The dag costs $0.000442050 more. The ledger sum is $0.0023870633.

Run 002 uses 12 new transcripts. The reference cap is 512 tokens. This is the only protocol change. Every item has a reference choice. Flat matches 10 of 12. Chain matches 11. Dag matches 11. Fact-chain matches 9. Chain gain is 1. Dag gain is 1. Fact-chain gain is −1. The shared miss is d05. The reference says escalate. Each leaf says ask. Chain and dag repair d11, where the reference says wait and the flat leaf says reply. The flat cost is $0.000278544. No graph gains 2 matches. The flat call stays the system to use. The handoffs stay in the table. The ledger sum is $0.00282861388.

## Run 003 is a different measurement

Run 003 does not compare graphs. It compares writers and scorers. Three areas run in parallel: inbox, money, and guard. The decision is an employee action. The hidden roles are explore and exploit. Writers invent the transcript and the option words. Scorers and references do not see the role map. There is one decision call per item. There is no handoff.

The rerun writers are `qwen/qwen3.8-27b` and `google/gemma-4-31b-it`. Liquid `lfm-2.5-2.6b` returned HTTP 404 on the first pass and was not retried. The scorers are Jev, Clef, Drex, and Microsoft-Decision-1. The references are DeepSeek and MiMo. The ledger sum is $0.0169856875. On the rerun items, Jev and Clef match DeepSeek on 10 of 12. Drex matches on 11 of 12. Microsoft-Decision-1 matches on 8 of 10, with two transport failures. The paper file was not updated from this run.

## What the sources already constrain

Tang and Zheng, arXiv:2609.32160, leave the error and the cost of decomposition unmeasured. Deußer, Sparrenberg, and Sifa, arXiv:2609.37647, measure one frozen Jev call per example. A tree that beats a flat call is evidence about the handoff. It is not evidence that the decision model is a better classifier. The comparison uses the same scorer in both shapes.

Do not use a fixed 0.5 branch. On UNFAIR-ToS, micro-F1 moved from 0.50 to 0.75 when the threshold was tuned. Do not start on ceiling tasks. IMDB, SST-2, and ARC are already near the ceiling for one call. Report the end-to-end outcome and the extra cost. Per-node accuracy is a weak stand-in.

## What is still open

No forest was run. The vote rule is open. No Fact threshold was run. The unrun arm is a high Fact score selects ask, otherwise one Next call. The threshold must be fixed before those calls. No labeled calibration set was used. The reference is another model, not a human label. The Lean package builds and has no theorems. The bibliography in the draft cites vendor posts. The audit and the benchmark are not in that file.

## The sentence the runs fix

On this task, the flat call matches the reference about as often as a handoff, and it costs less. A gain of one match does not change the system. That sentence is the draft claim. The title still says trees and forests. The body does not measure a forest.
