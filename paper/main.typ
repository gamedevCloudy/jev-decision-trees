#set document(title: "Decomposing a large decision into a DAG of small Jev calls")
#set page(paper: "a4", margin: (x: 2.4cm, y: 2.5cm), numbering: "1")
#set text(size: 11pt)
#set par(justify: true, leading: 0.65em)
#set heading(numbering: "1.1")
#show heading: set block(above: 1.4em, below: 0.7em)
#show table: set text(size: 9.5pt, hyphenate: false)

#align(center)[
  #text(size: 17pt, weight: "bold")[
    Decomposing a large decision into a DAG of small Jev calls
  ]
  #v(0.9em)
  11 October 2026
  #v(0.8em)
  Aayush Chaudhary (Independent, #link("mailto:aaayush.dev@gmail.com")[aaayush.dev\@gmail.com])
  #h(0.45em) · #h(0.45em)
  Grok 4.7 (SpaceX)
  #v(0.6em)
  #link("https://creativecommons.org/licenses/by/4.0/")[CC BY 4.0]
]

= Abstract

A large decision does not fit in one Jev call. Questions in one call do not see each other. This paper splits the decision into a DAG of small calls. A node is one Jev decision. An edge is host code, in the manner of a decision tree. The edge copies a parent answer into the next state, and it can choose the next node. The two runs are a probe on a short support transcript. They are not a large problem. The scorer is `typesafe/jev-1.13`. The reference is one model, `~deepseek/deepseek-v4-flash-latest`. The host calls the next node on every item. It does not take the branch. Run 001 ties the flat call, the chain, and the dag at 9 of 10. Run 002 scores the flat call, the chain, the dag, and fact-chain at 10, 11, 11, 9 of 12. Every extra call costs more. A gain of 2 matches was required before a graph could replace the flat call on this task. The gain of 1 happened. It stays below that line. The probe keeps the flat call here. The DAG remains the split for a problem that needs a later answer.

= Introduction

One Jev call answers a small question. A large problem is many such questions, and some of them depend on earlier answers. One call cannot carry that dependence. The program builds a DAG. Each node is one small Jev decision. Each edge is host code. In the manner of a decision tree, that code can test the parent answer and send the case down one branch. The model stays a scorer. The graph lives in the program.

Tang and Zheng leave the error and the cost of this split unmeasured @tang2026typed. These runs are a first probe of that cost. The task is already small. It is the next action on a short support transcript. The scorer is Jev. The reference is one DeepSeek answer. The flat call asks every question at once. The chain, the dag, and fact-chain are DAGs that copy parent answers forward. The host calls the next node on every item. A branch test is the decision-tree edge. These runs do not use one.

The paper makes three claims.

+ A dependent Jev question is a later node. The host holds the edge. The edge copies the parent answer, and a decision-tree test would choose the child.
+ On this short transcript the copy does not pay. Run 001 ties at 9 of 10. Run 002 gives the chain and the dag one extra match, and both cost more.
+ The flat call stays the baseline. A DAG replaces it only when the gain covers the extra calls. This probe does not meet that bar, and it does not score a large problem.

= Background

The _state_ is the evidence one call sees. Here the state is the transcript, plus any answer object the host has copied.

A _question_ is a typed judgment with a closed set of answers. Questions in one call are scored independently. A question in that call does not see the other answers.

#figure(
  table(
    columns: (0.9fr, 1.7fr, 2.6fr),
    align: (left, left, left),
    inset: 7pt,
    table.header([*Type*], [*Question*], [*Answer*]),
    [Noul], [Is this statement true?], [Probability of yes, from 0 to 1],
    [Choice], [Which one label applies?], [A label, a distribution, a confidence],
  ),
  caption: [Noul and choice, the question types these runs use. Names differ by vendor.],
) <tbl-types>

The interface in @tbl-types is the one published for Jev, Clef, d1, and Microsoft-Decision-1, and the one Vercel uses as the common field guide @typesafe2026jev @cloudflare2026clef @liquid2026d1 @microsoft2026decision1 @vercel2026decisions.

A _handoff_ is a later call. The parent answer object goes into the next state beside the transcript. The model scores one node. The host calls the next node.

A _match_ is a leaf equal to the reference choice. The leaf is the Next choice. The denominator is the set of items with both a leaf and a reference choice.

A _gain_ is the graph's match count minus the flat match count, on that shared denominator.

= The DAG

A large problem is a set of small questions. Some of those questions need an earlier answer. One Jev call scores only the questions that share a state. The question that needs an earlier answer is the next node.

The graph is a DAG. A node is one call. An edge is code in the host. The code writes the parent answer into the next state. In the manner of a decision tree, the same code can test that answer and choose one child. A high Fact score can select ask. Any other score can select one Next call. These runs do not use that test. They call the next node on every item. The edge only copies the answer.

Depth is the number of calls on one path. The flat call has depth 1. The chain and the dag have depth 3. Fact-chain has depth 2. The flat call is the baseline. A DAG has to beat it by enough to pay for the extra calls.

This is the method. The two runs ask whether the copy changes the leaf on a short transcript. They do not ask whether a large problem breaks into these nodes.

= Related work

Tang and Zheng, arXiv:2609.32160, review early typed-decision papers @tang2026typed. The typed readout has no accuracy gain over label probabilities. The error and the cost of decomposition are unmeasured. These runs use the same scorer in the flat call and in the handoffs. They do not test the readout against label probabilities.

Deußer, Sparrenberg, and Sifa, arXiv:2609.37647, measure one frozen Jev call per example @deusser2026jev. The flat call here is that one call. The handoffs add a later call.

Yao et al., arXiv:2305.10601, search a tree of thoughts @yao2023tot. Besta et al., arXiv:2308.09687, join thoughts in a graph @besta2024got. Zhou et al., arXiv:2205.10625, solve simpler subproblems in order @zhou2023least.

Those methods have the language model write the intermediate text. This scorer returns a closed score. The host copies that score, and a decision-tree test in the host would choose the next node. These runs copy the score. They do not search, do not join thoughts, and do not take the branch.

= Method

The task is the next action on a short support transcript. Each transcript has three to five turns. The actions are `reply`, `ask`, `escalate`, and `wait`. Run 001 items are c01–c12. Run 002 items are d01–d12. The run 002 transcripts are new. They are not a reuse of run 001.

The reference is one chat completion per transcript on `~deepseek/deepseek-v4-flash-latest`. The prompt contains the transcript and the Next question. It asks for one JSON object. Run 001 caps the reference output at 256 tokens. Two contents come back empty, so c06 and c11 have no reference choice. Run 002 caps that output at 512 tokens. This is the only protocol change. Every run 002 item has a reference choice.

The scorer is `typesafe/jev-1.13`. The question text is frozen. Tone is a noul: "The latest user turn is heated." Fact is a noul: "The agent needs one missing fact before it can act." Next is a choice: "Choose the next agent action." Reply means the agent can answer from the transcript. Ask means the agent must request one missing fact. Escalate means a person must take the case. Wait means no action is due on this turn.

The flat call is one request. It contains Tone, Fact, and Next. The state is the transcript. Next does not see the Tone answer or the Fact answer.

On a handoff, the parent answer object goes into the next state beside the transcript. The chain is three requests. Fact sees the Tone answer object. Next sees both answer objects. The dag is three requests. Tone and Fact do not see each other. Next sees both answer objects. Fact-chain is two requests, and it is in run 002 only. There is no Tone request. Next sees the Fact answer object.

The host calls the next node on every item. There is no threshold.

The claim rule was fixed before run 002. A gain of 2 matches was required before a graph could replace the flat call. A gain of 0 or 1 leaves the flat call as the system to use. A loss of 2 or more would say that the handoff lowers the match count. Fact-chain could replace the chain only in two cases. Its gain had to be at least 2, or its match count had to equal the chain at a lower cost. If all three graphs had gained 2 or more, the cheapest would have been kept.

= Results

@tbl-run001 is the pilot. The match denominator is 10. Calls were still made on all twelve items.

#figure(
  table(
    columns: (1.35fr, 0.9fr, 0.7fr, 0.9fr, 0.85fr, 1.35fr, 1.25fr),
    align: (left, right, right, right, right, right, right),
    inset: 5pt,
    table.header([*Graph*], [*Matches*], [*Calls*], [*Input*], [*Output*], [*Cost*], [*Minus flat*]),
    [Reference], [—], [12], [2594], [1297], [0.0006675413], [—],
    [Flat], [9 of 10], [12], [6499], [956], [0.000272958], [0],
    [Chain], [9 of 10], [36], [17418], [1052], [0.000731556], [0.000458598],
    [Dag], [9 of 10], [36], [17024], [1052], [0.000715008], [0.000442050],
  ),
  caption: [Run 001. Costs are US dollars from `usage.cost`. Input and output are token counts. The denominator is 10. The reference row is the target, so its match cell is empty. The ledger sum is 0.0023870633. Both handoffs cost more, and the flat call, the chain, and the dag tie at 9 of 10.],
) <tbl-run001>

On the ten items with a reference choice, every graph matches nine. The shared miss is c05. The reference choice is ask, and each leaf is reply. Every call has a `usage.cost` value. No cap stopped an agent.

@tbl-run002 scores all twelve items. The shared denominator is 12.

#figure(
  table(
    columns: (1.35fr, 0.9fr, 0.7fr, 0.9fr, 0.85fr, 1.35fr, 1.25fr),
    align: (left, right, right, right, right, right, right),
    inset: 5pt,
    table.header([*Graph*], [*Matches*], [*Calls*], [*Input*], [*Output*], [*Cost*], [*Minus flat*]),
    [Reference], [—], [12], [2712], [897], [0.00056985388], [—],
    [Flat], [10 of 12], [12], [6632], [954], [0.000278544], [0],
    [Chain], [11 of 12], [36], [17818], [1050], [0.000748356], [0.000469812],
    [Dag], [11 of 12], [36], [17422], [1050], [0.000731724], [0.000453180],
    [Fact-chain], [9 of 12], [24], [11908], [810], [0.000500136], [0.000221592],
  ),
  caption: [Run 002. The shared denominator is 12. Chain gain is 1. Dag gain is 1. Fact-chain gain is −1. The ledger sum is 0.00282861388. Every handoff costs more. The gain of 1 happened, and it stays below the line of 2.],
) <tbl-run002>

The flat call matches 10 of 12. The chain matches 11. The dag matches 11. Fact-chain matches 9. No graph gains 2 matches. Every call has a `usage.cost` value. No item failed. No cap stopped an agent. @tbl-choices is the leaf on each item.

#figure(
  table(
    columns: (0.7fr, 1.15fr, 1fr, 1fr, 1fr, 1.25fr),
    align: (left, left, left, left, left, left),
    inset: 5pt,
    table.header([*Item*], [*Reference*], [*Flat*], [*Chain*], [*Dag*], [*Fact-chain*]),
    [d01], [escalate], [escalate], [escalate], [escalate], [escalate],
    [d02], [escalate], [escalate], [escalate], [escalate], [escalate],
    [d03], [escalate], [escalate], [escalate], [escalate], [escalate],
    [d04], [wait], [wait], [wait], [wait], [reply],
    [d05], [escalate], [ask], [ask], [ask], [ask],
    [d06], [wait], [wait], [wait], [wait], [wait],
    [d07], [reply], [reply], [reply], [reply], [reply],
    [d08], [reply], [reply], [reply], [reply], [reply],
    [d09], [reply], [reply], [reply], [reply], [reply],
    [d10], [wait], [wait], [wait], [wait], [wait],
    [d11], [wait], [reply], [wait], [wait], [reply],
    [d12], [wait], [wait], [wait], [wait], [wait],
  ),
  caption: [Run 002 choices. Every graph misses d05, and fact-chain also misses d04. Chain and dag repair the same one item, d11, and that gain of 1 stays below the line of 2.],
) <tbl-choices>

= Analysis

The run 001 miss is the same on every graph. On c05 the reference choice is ask. The flat leaf, the chain leaf, and the dag leaf are reply. The copied answers do not change that leaf.

The run 002 miss shared by every graph is d05. The reference choice is escalate. Each leaf is ask. The copy does not change that leaf either.

Chain and dag repair the same one item. On d11 the reference choice is wait. The flat leaf is reply. The chain leaf and the dag leaf are wait. The match count rises by 1. The rule asks for a rise of 2.

Fact-chain does not return wait on d11. Its leaf there is reply. It also misses d04. On d04 the reference choice is wait, the flat leaf is wait, and the fact-chain leaf is reply. The fact-chain loss of 1 stays under the loss-of-2 line.

= Limitations

These limits sit beside the probe. The items are handwritten transcripts. They are already one small decision. They do not show that a DAG decomposes a large problem. The reference is a single reference model. Missing human labels mean that agreement with DeepSeek is not accuracy on a public label.

The pilot denominator is 10 because two reference contents were empty. The confirmatory set has 12 items. The host did not take a decision-tree branch. No model wrote a node. The flat-call result belongs to this transcript. It is not a reason to keep every large decision in one call.

= Conclusion

A large decision becomes a DAG of small Jev calls. A node is one call. An edge is host code, in the manner of a decision tree. The edge copies a parent answer, and it can choose the next node. On this short transcript the host only copies the answer. Run 001 ties at 9 of 10. Run 002 scores the flat call, the chain, the dag, and fact-chain at 10, 11, 11, 9 of 12. The gain of 1 happened. It stays below the line of 2. Every extra call costs more. The flat call stays the baseline for this task. The DAG stays the split for a problem that needs a later answer.

#bibliography("refs.bib", style: "ieee")
