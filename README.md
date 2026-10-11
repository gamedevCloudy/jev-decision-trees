# Decomposing a large decision into a DAG of small Jev calls

[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-blue.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Paper](https://img.shields.io/badge/paper-Typst-239DAD.svg)](paper/main.typ)

Aayush Chaudhary (Independent, [aaayush.dev@gmail.com](mailto:aaayush.dev@gmail.com)) · Grok 4.7 (SpaceX)

A Jev call scores typed questions on one state.
The questions in one call do not see each other.
A later question can need an earlier answer.
The host then copies that answer into the next state.
The host makes one more call.

This paper puts those calls in a DAG.
A node is one small Jev call.
An edge is code in the host.
The edge copies the parent answer.
The edge can also select the next node.
A decision tree uses this type of test.

The two runs are a probe on a short support transcript.
The scorer is `typesafe/jev-1.13`.
The reference is one DeepSeek answer.
The host calls the next node on each item.
The host does not use a branch test.

Run 001 ties the flat call, the chain, and the dag at 9 of 10.
Run 002 scores four graphs out of 12 items.
The flat call matches 10 items.
The chain matches 11 items.
The dag matches 11 items.
Fact-chain matches 9 items.
A gain of 2 matches was necessary to replace the flat call.
The gain of 1 match is below that line.
Each extra call costs more than the flat call.
The flat call stays the baseline for this transcript.

The DAG is the split for a decision that needs a later answer.
These two runs do not measure that larger decision.

## Cite

```bibtex
@misc{chaudhary2026dagjev,
  author       = {Chaudhary, Aayush and {Grok 4.7}},
  title        = {Decomposing a large decision into a {DAG} of small {Jev} calls},
  year         = {2026},
  month        = oct,
  howpublished = {GitHub},
  url          = {https://github.com/gamedevCloudy/jev-decision-trees},
  note         = {License: CC BY 4.0}
}
```

## Compile

Go to the root of the repository.
Run `typst compile paper/main.typ`.
The PDF is `paper/main.pdf`.

## License

The paper uses the [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) license.
Read `LICENSE`.
The license covers `paper/main.typ` and `paper/refs.bib`.
The license also covers the PDF.
The license does not cover the code, the notes, or the experiment logs.

## Layout

- `paper/` contains the Typst source and the bibliography.
- `src/jevdt/` is the OpenRouter client.
- `experiments/` contains run 001, run 002, and run 003.
- `docs/` contains the run notes.
- `proof/` is a Lean package.
- The Lean package has no theorems.

`notes/` stays on this computer.
Git ignores `notes/`.
