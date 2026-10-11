# Setup record

Executed from `notes/02-setup.md` on 2026-10-11. `notes/` stays outside git. This file is the copy that lives with the code.

## Direction

The project compounds decision models by composition. One call already returns a boolean, a category, or a score. The experiment is to stack those calls.

- A node is one Decisions call. Its questions share a state and do not see each other.
- An edge is code that writes the parent answers into the next state and chooses the next questions.
- A tree is a chain of those edges.
- A forest is several trees on the same root state, combined by a rule the experiment has to name.

A language model writes the node text. The decision model scores it. The aim is a working composition across domains, with the paper, the experiments, and a Lean proof of whatever claim survives measurement. The source notes for the five vendor writeups are in `docs/decision-models.md`.

## Layout

| Path | Role |
| --- | --- |
| `.env` | `OPENROUTER_API_KEY` only. Gitignored. |
| `.venv/` | uv-managed, Python 3.12. Gitignored. |
| `src/jevdt/` | OpenRouter client. Chat route and Decisions route. |
| `experiments/` | One directory per experimental setup, added when that setup exists. |
| `paper/` | Typst draft, `paper/main.typ`. |
| `proof/` | Lean 4 package `jevproof`. No theorems yet. |
| `docs/` | Findings, directions, decisions, outcomes. |
| `notes/` | Working notes and prompts. Gitignored. |

Charts during exploration use matplotlib, which is installed in the venv. Figures that belong in the paper are drawn in Typst.

## Models

All of them go through the OpenRouter key.

| Role | Id | Route |
| --- | --- | --- |
| Planning and experiment design | `x-ai/grok-4.7` with `reasoning_effort=high` | `POST /api/v1/chat/completions` |
| Coding | `moonshotai/kimi-k3` | same |
| Node instructions and criteria | unset | same, once a small open model is chosen |
| Decision node, starting scorer | `typesafe/jev-1.13` | `POST /api/alpha/decisions` |

The node-text model is deliberately unset. The setup note says to start with a small open model and only later to try more than one. Picking it is the first experiment, not part of setup. `qwen/qwen3.5-9b` is on the catalog and is the backbone Microsoft-Decision-1 and Clef-flash were post-trained from, so it is a candidate, not a default.

`typesafe/jev-router` is a chat router in the ordinary model catalog. It is a different object from `typesafe/jev-1.13` and is not the scorer.

Blog posts also name `microsoft/microsoft-decision-1` and `liquid/d1` as OpenRouter decision models. Neither id appeared in the public chat-model catalog fetched the same day. Whether the Decisions route serves them is unchecked.

Clef weights are Apache 2.0 on Hugging Face. Nothing here runs a local checkpoint. That stays a later option.

## Client

`jevdt.decide(state, questions, model=...)` posts to the Decisions route. `jevdt.complete(prompt, model=..., reasoning_effort=...)` posts to chat completions. Both read `OPENROUTER_API_KEY` from the environment, or from `.env` if it is unset. Variables already set in the environment win.

```python
from jevdt import DECISION_MODEL, decide

answer = decide(
    "Hi, I've been trying to connect Stripe for 3 days and I'm losing sales.",
    {
        "is_urgent": {
            "type": "noul",
            "instructions": "The message conveys urgency.",
        }
    },
    model=DECISION_MODEL,
)
```

Run it with `uv run python`. uv loads the project and the venv.

## Toolchain

- uv 0.7.19, Python 3.12.11, packages `openai`, `httpx`, `matplotlib`.
- Typst 0.15.1, already installed. Compile with `typst compile paper/main.typ`.
- elan 4.2.4 from Homebrew, default toolchain Lean 4.34.1. The package pins `leanprover/lean4:v4.34.1`. Build with `lake build` inside `proof/`.

## How an experiment is run

Each experiment is a directory under `experiments/` with the code, the prompts, and a short record of what changed and what came out. Independent strategies can be handed to parallel subagents because they do not share state beyond the read-only client and the docs. A result that should outlive the run is copied into `docs/` as a finding, a decision, or an outcome. A claim that should be proved is then stated in `proof/`.

## Checked

- `uv run python` imports `openai` 3.28.0, `matplotlib` 3.11.2, and `jevdt`.
- One Decisions call, state "The sky is blue today.", noul question "Does the text describe the sky as blue?". `typesafe/jev-1.13` resolved to `typesafe/jev-1.13-20260917` on provider TypeSafe. The answer was noul 0.99. Usage was 281 input tokens and a cost of $0.0000118.
- `typst compile paper/main.typ` produced a 3-page PDF.
- `lake build` in `proof/` succeeded on Lean 4.34.1.
- The chat route was not called. Grok 4.7 and Kimi K3 are wired by id only.

## Left open

- Which small open model writes node text.
- Which aggregation a forest uses.
- Whether Microsoft-Decision-1 and Liquid d1 answer on this key.
- A labeled set for the first calibration check. No dataset is chosen yet.
- No theorem. `proof/JevProof/Basic.lean` is an empty namespace so the package builds.
