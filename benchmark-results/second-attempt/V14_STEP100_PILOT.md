# v14 step-100 laptop pilot — release rejected

This pilot began from the untouched BF16 `Qwen2.5-Coder-3B-Instruct` parent.
It used the mutation-gated v14 corpus and assistant-response-only QLoRA loss.
It is not a release checkpoint and was not quantized.

## Training provenance

- Dataset: 10,000 verified records at exactly 65% English, 20% Kiswahili,
  and 15% English/Kiswahili code-switching.
- Split: 9,500 train records and 500 validation records, with no source-task
  overlap.
- Code lock: SHA-256-identical code across every English/Kiswahili/mixed
  parallel triple.
- Verification: 2,009 hidden assertions over 662 source tasks; 1,594 of 1,756
  deterministic mutants killed (90.8%).
- Parent: `/home/debian_isle/codefellow-training/base-qwen25`.
- Checkpoint: `/home/debian_isle/codefellow-training/run-sw-v14-pilot-r16/checkpoint-100`.
- Adapter SHA-256:
  `8548c6745f2d97f4fe7bcca306005d9dd487bba566913ac11154acbc3126dc27`.
- LoRA: rank 16, alpha 32, learning rate `2e-5`, maximum sequence length
  512, gradient checkpointing, and assistant-response-only loss.
- Post-tokenization training mix: 6,149 English, 1,892 Kiswahili, and 1,419
  mixed records (65/20/15 after rounding), 9,460 total.
- Step-100 validation loss: 0.373872; validation token accuracy: 0.901089.
- Peak allocated GPU memory: 4,070.7 MiB.

This stopped after 100 optimizer steps, so it exposed only 100 training
examples at batch size one. It is a pipeline and direction-of-travel test, not
the requested one-epoch training run.

## Raw `llama.cpp` screen

All results below came directly from the merged F16 GGUF through `llama.cpp`.
The evaluator used `model_only: true`; translation, self-review, application
contracts, and postprocessing were disabled.

| Strength | English | Kiswahili | Mixed | EN/SW/mix format | EN/SW/mix language adherence |
|---:|---:|---:|---:|---:|---:|
| 0.50 | 11/12 (91.7%) | 9/12 (75.0%) | 7/12 (58.3%) | 100% / 91.7% / 91.7% | 100% / 91.7% / 41.7% |
| 0.75 | 11/12 (91.7%) | 7/12 (58.3%) | 7/12 (58.3%) | 100% / 100% / 100% | 100% / 41.7% / 58.3% |
| 1.00 | 11/12 (91.7%) | 8/12 (66.7%) | 8/12 (66.7%) | 100% / 83.3% / 100% | 100% / 50.0% / 33.3% |

The 0.50 merge is the best pilot candidate. It preserves the English screen
score and raises pure Kiswahili substantially over the previously measured
base, but it fails the mixed-language and 98% formatting gates. No strength is
eligible for full evaluation or quantization.

## Failure diagnosis

1. Localized responses sometimes over-generate examples or repeat prose until
   the 240-token cap. This can leave an unclosed fence or put executable test
   output inside the only code block.
2. Some code misses hidden edge cases: for example, punctuation normalization
   in word frequency and the empty-list case in rotation.
3. The binary-search and longest-unique-substring failures are algorithmic.
   The latter is also the single English screen failure, so English quality was
   preserved rather than improved at this early checkpoint.
4. Adapter strength changes the distribution of language adherence and
   verbosity, but does not consistently repair the underlying algorithms.

## Decision

Reject all three step-100 merges and retain their raw result JSON files for
audit. Do not quantize. The corpus and training pipeline passed their integrity
checks and the light merge showed the intended language direction, so the next
authorized experiment is the actual one-epoch VPS run from the same original
BF16 parent. Save every 200 optimizer steps, screen checkpoints directly in
`llama.cpp`, and merge only promising checkpoints at 0.50, 0.75, and 1.00.
Quantization remains forbidden until a full checkpoint passes every hard gate.
