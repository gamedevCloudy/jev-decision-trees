# Run 003

Liquid was skipped on the rerun. The writers on the rerun are `qwen/qwen3.8-27b` and `google/gemma-4-31b-it`.

The ledger sum is $0.0169856875. The first pass is $0.0099011555. The rerun, including the grade, is $0.0070845320.

| Area | Sum |
| --- | --- |
| inbox | $0.0053088080 |
| money | $0.0054989175 |
| guard | $0.0059608220 |

The grade lines are area `grade` and sum to $0.0002171400. The guard area uses a product signal. Each area sum includes the first pass and the rerun.

The rerun has 4 items in each area. Every rerun item is valid.

| Area | Writer | Valid | Failed | Rerun writer cost |
| --- | --- | --- | --- | --- |
| inbox | `qwen/qwen3.8-27b` | 2 | 0 | $0.0018026000 |
| inbox | `google/gemma-4-31b-it` | 2 | 0 | $0.0002096400 |
| money | `qwen/qwen3.8-27b` | 2 | 0 | $0.0014135400 |
| money | `google/gemma-4-31b-it` | 2 | 0 | $0.0001860900 |
| guard | `qwen/qwen3.8-27b` | 2 | 0 | $0.0013166400 |
| guard | `google/gemma-4-31b-it` | 2 | 0 | $0.0001940600 |

DeepSeek is `~deepseek/deepseek-v4-flash-latest`. MiMo is `xiaomi/mimo-v2.6-flash`. The denominator is the items with a scorer option and that reference choice.

| Scorer | Calls | Cost | DeepSeek matches | MiMo matches |
| --- | --- | --- | --- | --- |
| `typesafe/jev-1.13` | 12 | $0.0002120160 | 10 of 12 | 9 of 11 |
| `cloudflare/clef-omni` | 12 | $0.0003952500 | 10 of 12 | 9 of 11 |
| `nace-ai/drex-v1.5` | 12 | $0.0000500400 | 11 of 12 | 10 of 11 |
| `microsoft/microsoft-decision-1` | 12 | $0.0000480060 | 8 of 10 | 7 of 9 |

| Item | DeepSeek | MiMo | Jev | Clef | Drex | Microsoft |
| --- | --- | --- | --- | --- | --- | --- |
| inbox-s1-qwen | provide | provide | provide | provide | provide | provide |
| inbox-s2-qwen | pause | pause | pause | pause | pause | pause |
| inbox-s1-gemma | done | done | done | done | done | none |
| inbox-s2-gemma | end | end | end | end | end | end |
| money-s1-qwen | process | process | process | process | process | none |
| money-s2-qwen | verify | verify | close | close | close | close |
| money-s1-gemma | do | do | do | do | do | do |
| money-s2-gemma | done | done | done | done | done | done |
| guard-s1-qwen | push | push | push | push | push | push |
| guard-s2-qwen | stop | stop | push | stop | stop | stop |
| guard-s1-gemma | fact | fact | fact | done | fact | done |
| guard-s2-gemma | halt | none | halt | halt | halt | halt |

Reference gaps are 0. Both references chose a key on 11 items. Inbox has 4. Money has 4. Guard has 3. The guard s2 Gemma item has no MiMo choice.

Clef gaps are 2 of 12. Inbox has 0 of 4. Money has 0 of 4. Guard has 2 of 4.

Drex gaps are 1 of 12. Inbox has 0 of 4. Money has 0 of 4. Guard has 1 of 4.

Microsoft-Decision-1 gaps are 2 of 10. Inbox has 0 of 3. Money has 0 of 3. Guard has 2 of 4.

| Scorer | Cost minus Jev cost |
| --- | --- |
| `typesafe/jev-1.13` | $0 |
| `cloudflare/clef-omni` | $0.0001832340 |
| `nace-ai/drex-v1.5` | -$0.0001619760 |
| `microsoft/microsoft-decision-1` | -$0.0001640100 |

Gaps: every HTTP 200 response had `usage.cost`. The first pass called `liquid/lfm-2.5-2.6b` six times. Each call returned HTTP 404, `No endpoints found for liquid/lfm-2.5-2.6b.`, at cost 0. The rerun did not call that id. The first-pass writer files are in `experiments/run-003/pass-1/`. Banned transcripts on the rerun: 0. Replacement calls: 0. No cap stopped an agent.

Three rerun calls failed on transport. `inbox-s1-gemma` on `microsoft/microsoft-decision-1` returned `Can't assign requested address`. `money-s1-qwen` on `microsoft/microsoft-decision-1` timed out. `guard-s2-gemma` on MiMo timed out. Those calls were not retried. A retry is only for HTTP 429 or 5xx.

## Appendix

The grade is a second view. The file is `experiments/run-003/grade.json`. The model is `typesafe/jev-1.13`. The grade made 12 calls and spent $0.0002171400. The ledger sum was under $1.80, so the grade step was open. The grade cap is 18 calls and $0.20.

`Disagree` asks whether the four scorer keys differ. `ClefGap` asks whether the Cloudflare key differs from the Jev key. The numbers below are noul values. The key counts in the tables above are a separate count.

| Item | Disagree | ClefGap |
| --- | --- | --- |
| inbox-s1-qwen | 0.61 | 0.96 |
| inbox-s2-qwen | 0.13 | 0.97 |
| inbox-s1-gemma | 0.69 | 0.97 |
| inbox-s2-gemma | 0.38 | 0.97 |
| money-s1-qwen | 0.77 | 0.95 |
| money-s2-qwen | 0.18 | 0.96 |
| money-s1-gemma | 0.07 | 0.95 |
| money-s2-gemma | 0.54 | 0.96 |
| guard-s1-qwen | 0.05 | 0.96 |
| guard-s2-qwen | 0.87 | 0.96 |
| guard-s1-gemma | 0.92 | 0.95 |
| guard-s2-gemma | 0.06 | 0.95 |
