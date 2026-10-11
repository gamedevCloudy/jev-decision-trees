# Decision models

Read on 2026-10-11 from the five writeups linked in the setup task. Numbers in this note are the vendors' own figures. They do not agree with each other, and none of them has been remeasured here.

- TypeSafe, [Introducing System One Models & Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- Cloudflare, [Introducing Clef](https://blog.cloudflare.com/clef-decision-models/)
- Liquid AI, [Introducing d1](https://www.liquid.ai/blog/d1-decision-model)
- Vercel, [What are decision models?](https://vercel.com/i/what-are-decision-models)
- Microsoft, [Microsoft-Decision-1](https://commandline.microsoft.com/microsoft-decision-1-model-foundry/)

The API shape below was checked against the [TypeSafe quickstart](https://docs.typesafe.ai/introduction/quickstart) and the [OpenRouter Decisions reference](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-questions-and-answers-request).

## The call

A decision model scores a closed set of answers. It does not write the answer as text.

The request has three fields.

- `state`. The evidence. A string, or a JSON object or array of related context.
- `questions`. One or more named judgments. Each has a `type`, `instructions`, and, where the type needs it, `criteria`.
- `model`. Which scorer to run.

Questions in one request are scored independently, in parallel, against that same state. A later question does not see an earlier answer. If it needs one, the program makes a second request and puts the first answer into the next state. Vercel states this directly, and TypeSafe's own guidance is the same: decompose a judgment into atomic questions and combine them in code.

Three question types show up under different names.

| Judgment | TypeSafe / Clef / d1 / OpenRouter | OpenAI | Vercel AI Gateway | What comes back |
| --- | --- | --- | --- | --- |
| Yes or no | `noul` | predicate | boolean | Probability of yes, from 0 to 1 |
| One label | `choice` | choice | choice | The label, a distribution, and a confidence |
| Ordered rubric | `score` | score | score | A position on the rubric, a distribution, and a confidence |

A noul near 0 means the model favors no. It does not mean the model is unsure. Confidence on a choice or a score summarizes the shape of that distribution. Jev's docs treat confidence as a separate field from the probability of the chosen option. A high probability can still be wrong, so a threshold has to be measured on labeled cases before it is allowed to act.

Choice criteria are a map of label to description. Score criteria are an ordered list. Noul criteria, when present, are the two descriptions `true` and `false`. Several questions share one state, so the evidence is billed once per request on the APIs that work this way. Liquid's direct API is the exception they document: each question is billed as its own prompt.

Jev's published cardinality limit is 255 labels. Above that, TypeSafe describes a two-stage procedure: score independently, then choose.

## Five systems

### Jev (TypeSafe)

System One is TypeSafe's name for the class, taken from Kahneman's fast System 1. Jev is named for William Stanley Jevons. The training method they name is reinforcement learning for calibrated decisions (RLCD). Sampling is parallel: every answer is produced in one pass, and the model does not generate a string. Type safety is a property of the schema, so a response that violates the question types is excluded by construction.

Jev, in the TypeSafe post, takes text. Cloudflare describes its context as 32k. Published price is $0.042 per million input tokens, with output tokens free. TypeSafe's own latency range for a call is 70–500 ms. Their workflow-eval writeup is the source of the larger speed and cost multiples on the marketing page, and they flag those multiples as the high end.

Hosted as `jev-latest` at `POST https://api.typesafe.ai/v1/systemone`. On OpenRouter the documented model id is `typesafe/jev-1.13`, on `POST https://openrouter.ai/api/alpha/decisions`. The Python SDK is `typesafe-sdk`, and it can point at OpenRouter with `base_url="https://openrouter.ai/api"`.

Use cases they show: a real-time Doom bot driven by structured game state (they say the demo is text state, and that about ten queries a second came out near $7 per hour), and WikiRacing over high-cardinality link choices. The workflow evals they publish are invoice processing, customer service, security incidents, and agent-trace observability, scored against the average of two large language models given the same workflow.

### Clef (Cloudflare)

Clef and Clef-flash are Apache-2.0 weights on Hugging Face (`Cloudflare/clef`, `Cloudflare/clef-flash`), hosted on Workers AI, and described as Jev-API compatible. Clef adds a vision encoder. Cloudflare states a 64k context.

The backbone is a frozen Qwen: Qwen3.8-27B for Clef and Qwen3.5-9B for Clef-flash, plus a rank-256 adapter and a routing head. Inference is a prefill, then a non-autoregressive score of the schema choices. They describe a two-stage attention route: each option attends to the prompt, then fields cross-attend with each other and back to the payload. Post-training is label-smoothed cross-entropy, a Brier loss for calibration, synthetic permutations of field order and schema, and a second stage they also call RLCD.

On their table, median latency is 209 ms for Clef and 39 ms for Clef-flash, against 524 ms for Jev. They also report Clef ahead of Jev on most rows of the Jev Decision Index and on three of four TypeSafe workflow evals, with Jev ahead on agent-trace observability and on When2Call and BRIGHT. Laya is faster still and much weaker on those quality rows.

The in-house use they describe is domain classification for threat intelligence: category probabilities such as fashion, ecommerce, and phishing, with the page fetched and rendered before the call. Fine-tuning targets they name are Trust & Safety submissions, support triage, and good-bot versus bad-bot. The fine-tune path is a forward-deployed service first, then a self-serve loop that captures traffic in AI Gateway, rolls out on Workers AI, scores in Containers, and redeploys the weights.

### d1 (Liquid)

d1 answers the same three question types, text and image, in one forward pass, with no generated tokens. Liquid's figure for a text decision is 200–300 ms. Price on their API is $0.04 per million input tokens and no output tokens. An image is 1.5 tokens per 32×32 patch, so a 1024×1024 image is 1,536 tokens. Each question is billed as its own prompt, including the images.

Direct API: `POST https://api.liquid.ai/decisions/v1/systemone` with `"model": "d1"`. Images travel as base64 data URLs in an `images` array. The blog says d1 is also on Vercel and on OpenRouter as `liquid/d1`, text only for now, with vision still to come on those two.

Applications they ran, each once, on 2026-10-05, against GPT-6.1 Sol and Claude Opus 5.5:

- Visual inspection of circuit boards, candles, cashews, and chewing gum from the public VisA set. They report 85–97% good-versus-defective, with a known-good part from the same line shown beside the part under test. They say the model was not trained on that task.
- Smart filter: a yes/no per support ticket, used as a predicate inside a query, over 150 tickets.
- Code search: walk the Hugging Face transformers tree, one folder at a time, down to a function.
- Smart folders: file a document, or a search question, into a folder and then a subfolder.
- Web agent: operate a flight-search site from a one-sentence goal, picking the next action from what the page allows.
- Context compaction: keep, trim, or drop each tool output in a coding session. They report 52% of tokens removed and every needed output kept.
- Games. Tetris scored 70 cleared lines from text and 81 with the screen. Wordle read the board from a screenshot and solved 12 of 12 in 3.8 guesses on average. Quick, Draw! recognized 5.2 of 6 doodles against a 62-word list.

Four of the text applications are adaptations of existing projects: [pg-jev](https://github.com/realZachi/pg-jev), [jevgrep](https://github.com/dzhng/jevgrep), [jev-ultrafast](https://github.com/browser-use/jev-ultrafast), and [fast-jev-compaction](https://github.com/tamaratran/fast-jev-compaction).

### Microsoft-Decision-1

A post-train of Qwen3.5-9B for a single scoring pass. Yes/no, multiple choice, rating, and rubric grading of a model or agent action. Available in Microsoft Foundry and, according to the post, on OpenRouter as `microsoft/microsoft-decision-1`. Input price matches the others at $0.042 per million tokens, output free. Docs: [use Foundry models, Microsoft Decision](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-microsoft-decision).

Their evaluation claims, on a 36-benchmark set they say was kept blind, covering about 150,000 questions: highest accuracy among the models they compared, about 2.5× the runner-up H2O-Lightning-4B v1.1 on speed, and about 35× GPT-6 Sol on P50 latency. Robustness: eight perturbations of the same request, 1.3% decision flips on average, and no flips when option text was paraphrased or when options were reversed or shuffled. Safety: 5,250 requests across 11 benchmarks of harmful content, jailbreaks, and prompt injection.

Internal uses they report: labeling 10,000 pieces of Xbox feedback into a fixed theme set; Copilot response quality control; incident knowledge retrieval; adaptive replanning inside Microsoft Discovery, where the decision model grades the previous experiment against a rubric.

The appendix list of other models in that comparison includes Quyet-1.0-Large, Surogate Rune 26B-A4B, GPT-6 Luna Decisions, deck-31B, H2O-Lightning-4B, and Strands-Decider 2B.

The use-case list in the post is the widest of the five: agent step control, model routing, skill-conditioned next actions, data labeling, judging a generated answer, intent, incident routing, input validation, recommendation, search relevance, content filtering, code scanning, safety screening, computer and UI actions, robot action selection, and screening hypotheses or experiments.

### The field guide (Vercel)

Vercel is the source that separates the category from its neighbors.

- A rule or a decision table applies when the policy can be written exactly.
- A classical classifier applies when the label set is fixed and there is training data, or a zero-shot classifier such as GLiClass.
- A native decision model applies when the program needs repeated, bounded judgments and a distribution.
- An LLM with structured output applies when the task also needs a written explanation, an extraction, or a plan.

Reward models overlap this category when the job is to grade an output, and a preference score is a different object from the probability that a business predicate is true.

Architectures inside the category already differ. Laya is an encoder plus a decision head. Typical reads the shared state into a cache and scores each option, and it exposes an abstention signal. An SDK that offers one function for all of them does not make the behavior the same: Vercel notes that the AI SDK's Anthropic and Google adapters are structured-output LLMs, omit the native distributions, and return a prompted boolean probability.

Open weights named in that guide, beyond Clef: Perplexity `pplx-decider-v1-27b` (Apache 2.0, text and image), Laya, and Typical. Hosted names beyond the four above: Telnyx (TypeSafe-compatible, beta) and Inception Mercury Decide (Jev-compatible schema on OpenRouter).

Practical rules they give, which this project will keep:

- Start from a repeated judgment whose answer set can be defined and whose mistakes can be counted.
- Leave exact fields to code. A trusted `refunded` column is a read, not a model call.
- Keep a review or insufficient-evidence outcome in the label set when a forced choice would hide a missing fact.
- If several labels can be true together, ask several noul questions.
- Measure calibration before an automated threshold. Include the cost of review and of fallbacks.
- After a model, a question, or a category definition changes, rerun the labeled set.

## What other people have already built

These are programs that wrap one decision call, taken from the posts above.

| Program | What the call does |
| --- | --- |
| pg-jev | A SQL predicate. The ticket either matches the question or it does not. |
| jevgrep | Walks a repository one directory at a time until it reaches the function that answers a question. |
| jev-ultrafast | Picks the next browser action from the actions the page currently allows. |
| fast-jev-compaction | Keeps, trims, or drops a tool result before the next coding step. |
| Doom bot, WikiRacing | TypeSafe demos: a fast loop over structured state, and a high-cardinality choice over links. |
| d1 games and visual inspection | The same call pointed at a screenshot or a production-line photo. |
| Cloudflare threat intel | Category probabilities for a rendered domain. |
| Microsoft internal loops | Theme labeling, response grading, incident retrieval, experiment replanning. |

Every one of these is a single node, or a hand-written loop of nodes. None of them is a learned or a generated tree.

## Consequence for this project

The missing composition is the one the APIs already force. Dependence between questions is a second call. That second call, with the parent answer written into its state, is an edge. A tree is those edges collected in code. A forest is several trees on one root state, combined by a rule that is itself either code or one more node.

The decision model is the scorer at a node. It is the wrong tool for proposing the tree. That job is the small language model in the setup note: it writes instructions and criteria, and the scorer stays fixed so a change in node text can be blamed on the text.

Two measurements have to come before a tree is worth building.

1. A single node, on a labeled set, with a recorded calibration. A tree of uncalibrated nodes will not become calibrated by being deeper.
2. The flat call that asks the whole judgment as independent questions on the original state. A tree is a win only where the dependence actually helps, because every extra level adds a round trip.

Vendor leaderboards are not a substitute for either measurement. Cloudflare ranks Clef above Jev on the Jev Decision Index. TypeSafe ranks Jev on the Pareto front of its workflow evals. Microsoft ranks Microsoft-Decision-1 first on a private 36-benchmark suite. The scorer used in an experiment here gets chosen per run and named in the run record.
