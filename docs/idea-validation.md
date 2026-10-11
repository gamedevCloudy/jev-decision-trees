# Validation of the working idea

Checked on 2026-10-11 against `notes/03-idea.md`, `docs/decision-models.md`, and these sources.

- Tang and Zheng, *Typed Decision Models: An Early Evidence Audit and Evaluation Checklist*, arXiv:2609.32160, 26 Sep 2026. Review of the first 28 TDM papers.
- Deußer, Sparrenberg, and Sifa, *Evaluating and Benchmarking the System One Model Jev*, arXiv:2609.37647, 29 Sep 2026. One frozen call per example on 37 datasets, `jev-1.13.0`.
- Yao et al., *Tree of Thoughts*, arXiv:2305.10601, NeurIPS 2023.
- Besta et al., *Graph of Thoughts*, arXiv:2308.09687, AAAI 2024.
- Zhou et al., *Least-to-Most Prompting*, arXiv:2205.10625, ICLR 2023.
- Dohan et al., *Language Model Cascades*, arXiv:2207.10342, 2022, as cited by the audit.
- The vendor interface already recorded in `docs/decision-models.md`.

No paper PDFs are stored in the repo. The audit and the Jev benchmark were read from arXiv HTML on this date.

## Verdict

The setup is a real measurement hole, and it is already surrounded by older methods. The sentence the audit leaves open is the sentence in `notes/03-idea.md`: breaking a hard decision into atomic questions may help, and the error and the cost of doing so have not been measured. The same sources put four constraints on how that sentence can be tested.

## What the sources support

**One API call is a node.** A typed decision call answers its questions independently, in parallel, on one shared state. A question that needs an earlier answer is another call, and the program copies that answer into the next state. TypeSafe's own guidance, the Vercel field guide, and the audit's definition of the interface all say this. The audit's open-problem section then says the consequence has not been measured: "Decomposing a hard decision into atomic questions may help, but the resulting error propagation and cost trade-off have not been measured systematically."

**The interface has no internal iteration.** The audit states that a TDM provides no explicit iterative computation and no generated intermediate reasoning, and that this shows up on multi-step tasks. A graph of calls in the host program is how iteration gets added outside the model. That matches the decision that the planner and the small language model build the graph, and the decision model only scores a node.

**Depth and generated structure are an existing experimental design.** Tree of Thoughts treats problem solving as four choices: how to decompose a step, how to generate candidates, how to evaluate a state, and which search to run. Least-to-most is the chain form of the same idea: break a problem into simpler subproblems and solve them in order, with each answer available to the next. Depth as a knob, and a graph produced during the experiment, sit on this side of the literature. A classical decision tree sits on the other side: the structure is induced once from labeled data and then reused. `notes/03-idea.md` leaves that unit of generation open. Both units exist in the literature, so the hole is real.

**A forest whose trees differ by a random draw is Breiman's definition.** Breiman's random forest is a set of trees where each tree depends on a random vector drawn iid from one distribution, and the trees vote. An independent draw from the node-writing language model can be that vector. Assigning different language models to different sub-trees is a further step: the draws no longer share one distribution. That experiment is allowed by the note, and it is a different object from a Breiman forest.

**A DAG is the shape that adds joins.** Graph of Thoughts is the step past a tree: thoughts are vertices, dependencies are edges, and several thoughts can be aggregated into one. The note is right to list a DAG and right that it has no design. The design it is missing is the join.

**The reader and the gap match.** The Jev benchmark measures one frozen template and one request per example, 346,009 requests, under $10. The 28-paper audit organizes systems as a single step, a controller, a judge, or a measurement instrument. None of those papers is a generated tree of decision calls whose depth is the experimental factor. A reader who knows one Jev call and has not scaled it is the reader these two papers leave behind.

## Constraints the sources put on the setup

**Alpha-beta pruning searches a tree. It does not combine a forest.** Tree of Thoughts evaluates states and then runs a search (lookahead, backtracking, breadth-first or depth-first). Alpha-beta is in that family: it skips branches that cannot change the result of a minimax search. The note already separates this from the missing vote. The sources agree with that separation. Alpha-beta can decide which nodes are worth a call. The rule that turns finished trees into one answer is still the forest rule, and Breiman's version of it is a vote.

**A hard branch at 0.5 is a known failure of this model.** The Jev benchmark finds that choice probabilities are well calibrated and that binary probabilities rank well, while a fixed 0.5 threshold places them badly. On UNFAIR-ToS, micro-F1 moves from 0.50 to 0.75 when the threshold is tuned on training data. Prompt-injection detection has perfect precision and 50% recall at 0.5, with AUROC 0.982. An edge in the manner of a decision tree is coherent when the branch test is a threshold fitted off the evaluation split. The audit's checklist requires that separation. A default of 0.5 is the setting those papers show going wrong.

**The first dataset has to be a problem one call finds hard.** On the Jev benchmark, one frozen call already reaches 96.5% on IMDB, 96.4% on SST-2, 98.8% on ARC, and 99.6% on language identification. A tree cannot demonstrate decomposition there. The same paper's weak single calls are Emotion at 58.5% accuracy, SST-5 at 57.9%, GoEmotions at macro-F1 0.243, AGB-DE at F1 0.204, and UNFAIR-ToS at micro-F1 0.499 before the threshold is tuned. Banking77, with 77 overlapping intents, is at 79.7%. Those are the problems where a second node has something to do.

A common tabular set in the 10–100MB band is a legal size, and it is a different experiment. The audit's checklist says that where labels suffice to train a model, the baseline is a task-specific classifier. On a standard tabular problem that baseline is a classical tree or forest, and it is strong. The decomposition claim would then be tested against a method that already decomposes by learned splits. The benchmark's hard text problems compare a tree of calls against the published one-call number for the same scorer.

**End-to-end error is the result, and per-node accuracy is a weak stand-in.** In the audit, a controller is a sequence of decisions that changes state. Errors compound, and per-step accuracy is a weak proxy for the final outcome. One game-playing study in that corpus never recovered from a per-step chooser that had no planner. The result named in the note, that the large problem comes out right, is the right result. Reporting only that each small question looks accurate would miss the failure the audit already saw.

**The scorer is the wrong place to claim an accuracy gain.** The audit's first finding is that the typed readout has not shown an independent accuracy advantage over reading label probabilities from an ordinary language model. Jev's clearest measured gains are latency and cost. A tree that beats a flat call is evidence about the decomposition. It is not evidence that the decision model is a better classifier. The comparison the claim needs is the same scorer, once as one flat call and once as the tree.

**Duplicate questions are a generator failure.** Least-to-most states the dependence that forces a later step: the next subproblem is solved with the answers of the earlier ones. Two copies of the same question have no such dependence, and the API would have scored them together. The risk named in the note belongs in the generator check. It does not yet name the dependence inside the first task.

## What this leaves open

The output of a run, the exact fields the small model writes, and the forest's combination rule are still open, and the sources do not pick them. Tree of Thoughts' four choices are a menu for the fields, if one is wanted later: the decomposition, the candidate generator, the state evaluation, and the search.

The proof sentence in the note is an empirical claim about complex domains. Lean can start on the piece the audit says is unmeasured and is purely about the host program: how error moves along a chain of hard tests of a given depth. That is a logic experiment. A proof that the method works on complex domains waits on the measurement.

## Sources

Tang and Zheng, arXiv:2609.32160. Deußer, Sparrenberg, and Sifa, arXiv:2609.37647. Yao et al., arXiv:2305.10601. Besta et al., arXiv:2308.09687. Zhou et al., arXiv:2205.10625. Breiman, Random Forests, Machine Learning 45:5–32, 2001, for the forest definition used above. The interface facts agree with `docs/decision-models.md`.
