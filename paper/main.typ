#set document(title: "Composing decision models into trees and forests")
#set page(paper: "a4", margin: (x: 2.4cm, y: 2.5cm), numbering: "1")
#set text(size: 11pt)
#set par(justify: true, leading: 0.65em)
#set heading(numbering: "1.1")
#show heading: set block(above: 1.4em, below: 0.7em)
#show table: set text(size: 9.5pt, hyphenate: false)

#align(center)[
  #text(size: 17pt, weight: "bold")[
    Composing decision models into trees and forests
  ]
  #v(0.9em)
  Working draft #sym.dot 11 October 2026
]

#v(1.2em)
#outline(indent: 1em, depth: 2)

= Abstract

A decision model takes a state and a set of typed questions and returns a probability for each allowed answer. The questions in one call are scored independently. This draft asks what can be built when an earlier answer is copied into the state of a later call, and when several such chains are aggregated. The shape is the one already familiar from decision trees and random forests: a node is one call, an edge is a handoff written in ordinary code, and a forest is an ensemble of those trees. A language model proposes the questions and the criteria. The decision model only scores them. This draft records the question. It reports no measurements.

= One call

The call that every current decision model shares has three parts. The _state_ is the evidence. The _questions_ name the judgments, each with a type and a closed set of answers. The response is a typed value plus a probability, with a separate confidence on choice and score questions.

Three question types cover the calls we will use.

#figure(
  table(
    columns: (0.9fr, 1.7fr, 2.6fr),
    align: (left, left, left),
    inset: 7pt,
    table.header([*Type*], [*Question*], [*Answer*]),
    [Noul], [Is this statement true?], [Probability of yes, from 0 to 1],
    [Choice], [Which one label applies?], [A label, a distribution, a confidence],
    [Score], [Where does this sit on a rubric?], [A position, a distribution, a confidence],
  ),
  caption: [Question types shared by Jev, Clef, Liquid d1, and Microsoft-Decision-1. Names differ by vendor. OpenAI calls a noul a predicate. Vercel AI Gateway calls it a boolean.],
) <tbl-types>

The interface in @tbl-types is the one published for Jev, Clef, d1, and Microsoft-Decision-1, and the one Vercel uses as the common field guide @typesafe2026jev @cloudflare2026clef @liquid2026d1 @microsoft2026decision1 @vercel2026decisions.

Adding another question to the same call does not show that question the other answers. A judgment that depends on an earlier answer is a later call.

= Where the next call starts

The host program decides what the next state contains. A typical handoff copies the parent answers in beside the original evidence, then asks a narrower set of questions. The decision model stays inside one node. The graph lives in the program that calls it.

That split is the whole method. The model is a scorer with a fixed schema. The program is the place where order, dependence, and thresholds are written down, so a change of policy is a change of code.

= A tree

A tree is a root state, a node of independent questions, and a rule that picks the next node from those answers. The rule can be a threshold on a noul, an exact choice label, or a band on a score. The leaves are actions or a final record, and they are also ordinary code.

The depth is a cost. Each level waits on the level above it. The baseline is one flat call that asks every question of the original state. A tree has to be more accurate than that call by enough to pay for the extra round trips.

= A forest

A forest is several trees read against the same root state, then combined. The combination rule is open. Candidates are a mean of the leaf probabilities, a majority of the leaf labels, and a further decision node whose state is the set of leaf answers. The first experiments will have to pick one and say why.

The language-model side of a forest is that each tree can be proposed separately. Different prompts, and later different proposer models, are different trees. The decision model underneath can stay fixed while that changes, which is the comparison we actually want.

= Who writes a node

Three language-model roles sit outside the decision call.

#figure(
  table(
    columns: (1.1fr, 2.4fr, 2.2fr),
    align: (left, left, left),
    inset: 7pt,
    table.header([*Role*], [*Model*], [*Job*]),
    [Planning], [`x-ai/grok-4.7`, high reasoning], [Experiment design and writeup],
    [Coding], [`moonshotai/kimi-k3`], [The program that runs the tree],
    [Node text], [A small open model, not chosen yet], [Instructions and criteria for each question],
  ),
  caption: [Models around the decision call. Scoring starts on #box[`typesafe/jev-1.13`] through OpenRouter.],
)

The node-text model is the one we expect to matter. A weak question or a muddy criterion changes the score even when the decision model is held fixed. The first experiments vary that text and keep the scorer constant.

= What the experiments have to measure

Each experiment records the tree it actually ran, the prompts, the model identifiers, and the raw answers. The comparisons that justify the machinery are:

- Calibration of a single node on a labeled set, before any tree is built.
- A tree against one flat call that sees the same evidence.
- A forest against its best single tree.
- The same tree with a different node-text model.
- Latency and input tokens, counted per level, because depth adds a round trip.

A threshold that is accurate and sends every case to review has not improved the workflow. Review and abstention stay in the answer set wherever a forced label would hide missing evidence.

= Formalization

Statements that survive those measurements go into the Lean package in `proof/`. The package builds and contains no theorems yet. A claim is written down there after an experiment has fixed the statement, so the formalization follows the result rather than preceding it.

#bibliography("refs.bib", style: "ieee")
