# Step-100 diagnostic — rejected

This was a laptop pilot from the untouched BF16
`Qwen2.5-Coder-3B-Instruct` parent. It is not a release checkpoint and was not
quantized. Evaluation used direct, raw F16 GGUF responses from `llama.cpp` with
`model_only: true`; no translation, self-review, application contract, or
postprocessing was enabled.

| Adapter strength | English code | Kiswahili code | Code-switched code | EN/SW/mix format |
|---:|---:|---:|---:|---:|
| 0.50 | 11/12 (91.7%) | 9/12 (75.0%) | 7/12 (58.3%) | 100% / 100% / 91.7% |
| 0.75 | 11/12 (91.7%) | 7/12 (58.3%) | 9/12 (75.0%) | 100% / 100% / 100% |
| 1.00 | 11/12 (91.7%) | 7/12 (58.3%) | 9/12 (75.0%) | 100% / 100% / 100% |

The 0.50 and 0.75 merges bracketed the desired language behavior, but no
strength met both multilingual gates. Full strength also increased pure
Kiswahili response length. Several failed localized responses repeated short
phrases until the token limit. Inspection traced this to only eight generic
localized explanations being cycled over the MBPP records.

Decision: reject every step-100 strength, preserve the files for audit, and do
not quantize. Rebuild the corpus with a unique, task-grounded explanation for
each verified source task. Translate and back-translate those explanations
independently, then restart the pilot from the original BF16 parent rather than
continuing the rejected adapter.

Raw result files in this directory are the source of truth. The interrupted
`step100-s075-screen12.json` file is not part of the comparison; the completed
per-language `step100-s075-screen12-{en,sw,sw_mix}.json` files are.
