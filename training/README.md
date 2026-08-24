# CodeFellow model-embedded adaptation: second attempt

This pipeline starts from the original BF16/FP16
`Qwen2.5-Coder-3B-Instruct`, trains one conservative QLoRA epoch, selects a
checkpoint using raw `llama.cpp` responses, and quantizes only the winner. The
existing Q4_K_M model and all failed merged checkpoints are baselines, never
training parents.

## 1. Build 10,000 verified parallel records

```bash
python training/build_parallel_dataset.py \
  --output-dir artifacts/data-v2 \
  --total-records 10000 \
  --mbpp-limit 650 \
  --humaneval-limit 0 \
  --ct2-translation-model /home/debian_isle/codefellow-training/nllb-ct2-int8 \
  --translation-threads 4 \
  --translation-cache artifacts/data-v2/translation-cache.json

python training/validate_dataset.py \
  --train artifacts/data-v2/train.jsonl \
  --validation artifacts/data-v2/validation.jsonl \
  --languages en,sw,sw_mix \
  --min-records 8000 \
  --expected-ratios en=0.65,sw=0.20,sw_mix=0.15 \
  --require-parallel-lock \
  --require-verified
```

Every source task has English, Kiswahili, and English/Kiswahili code-switched
versions. The code block is SHA-256-identical across the three lanes. Reference
programs are compiled or executed against tests that are deliberately omitted
from the model response. NLLB supplies Kiswahili prose only and is never the
authority for code. Every assistant explanation is grounded in its specific
verified task; the builder does not cycle a small bank of generic localized
responses. Translated requirements and explanations are independently
translated back to English. Numeric constraints, negation, and semantic
contrasts such as character/digit and minimum/maximum must survive, or the task
is rejected. The preferred CTranslate2 INT8 teacher runs on CPU; the
Transformers fallback applies the 84 C to 80 C GPU thermal guard to both
forward and reverse translation.

The default source mix uses 650 strictly accepted MBPP tasks and the
project-authored repair curriculum. HumanEval is available only as an optional
executable fallback pool; if enabled, it is prohibited as a claimed
post-training benchmark. CodeFellow's frozen held-out suites remain the
checkpoint authority.

The source-level split keeps all variants of a task in one partition. Frozen
CodeFellow evaluations, competition metadata prompts, and application outputs
are excluded.

## 2. Train from the original parent

On the development laptop, first run a short, explicitly non-release pilot to
verify memory, thermals, loss masking, checkpoint recovery, and the direction
of the language trade-off:

```bash
python training/train_qlora.py \
  --model /home/debian_isle/codefellow-training/base-qwen25 \
  --train artifacts/data-v2/train.jsonl \
  --validation artifacts/data-v2/validation.jsonl \
  --output artifacts/run-v2-pilot-r16 \
  --lora-rank 16 --lora-alpha 32 --learning-rate 2e-5 \
  --max-steps 300 --stop-after-steps 100 \
  --max-seq-length 512 --gradient-accumulation-steps 1 \
  --gradient-checkpointing --eval-limit 20 \
  --checkpoint-interval 100
```

`--max-steps 300` exposes only 300 examples at batch size one. It is a laptop
screen, not the final one-epoch run, and never qualifies a release by itself.
Reject it immediately if raw responses show repetition, English regression, or
poor stopping. After the pipeline and data pass that screen, run the actual
one-epoch job on a suitable training VPS from the same original parent:

The accepted v14 corpus passed every integrity check. Its fresh step-100 adapter
was tested at uniform strengths 0.35, 0.45, 0.50, 0.75, and 1.0, plus intact-parent
domain quantization and an upper-layer-only control. The 0.45 Q4_K_M became the
Gate 1 competition artifact after a full 50-task and official-profiler comparison.
It does not pass the stronger localized executable-improvement target: that
exception is disclosed in `REPORT.md` and `selection-summary.json`. A future
weight release must be a fresh run from the original parent, not a continuation
of this pilot checkpoint.

```bash
python training/train_qlora.py \
  --model /home/debian_isle/codefellow-training/base-qwen25 \
  --train artifacts/data-v2/train.jsonl \
  --validation artifacts/data-v2/validation.jsonl \
  --output artifacts/run-v2-r16 \
  --lora-rank 16 \
  --lora-alpha 32 \
  --learning-rate 2e-5 \
  --num-train-epochs 1 \
  --max-steps -1 \
  --max-seq-length 672 \
  --gradient-accumulation-steps 4 \
  --checkpoint-interval 200 \
  --save-total-limit 12 \
  --english-repeat 1
```

The trainer refuses checkpoint, merged-model, GGUF, legacy-dataset, and wrong
architecture inputs. Loss applies only to assistant tokens. Complete-sequence
filtering is followed by a strict 65/20/15 rebalance, so truncation cannot
silently overrepresent a language. Validation and adapter recovery checkpoints
run every 200 optimizer steps. The laptop thermal guard pauses at 84 C and
resumes at 80 C.

## 3. Evaluate checkpoints and merge strengths

For promising checkpoints, merge the adapter against the same original parent
at all three supported strengths:

```bash
python training/merge_adapter.py \
  --model /home/debian_isle/codefellow-training/base-qwen25 \
  --adapter artifacts/run-v2-r16/checkpoint-N \
  --strength 0.50 \
  --output artifacts/checkpoint-N-strength-050
```

For targeted retention tests, also evaluate `--strength 0.25`, `0.35`, and
`0.45`; repeat with `--strength 0.75` and `--strength 1.0`. Convert each merged HF
directory to an F16 GGUF with `convert_hf_to_gguf.py`, then run it through
`llama-server`. Checkpoint comparisons must invoke the paired evaluator with
`--model-only`; do not pass translation, self-review, or application-contract
options.

```bash
python evals/kiswahili/run_eval.py \
  --endpoint http://127.0.0.1:8181/v1/chat/completions \
  --model CodeFellow-checkpoint-N-strength-050-F16 \
  --languages en,sw,sw_mix \
  --model-only --fresh \
  --output artifacts/evals/checkpoint-N-strength-050-paired.json

python evals/run_repairs.py \
  --endpoint http://127.0.0.1:8181/v1/chat/completions \
  --max-attempts 2 --overwrite \
  --output artifacts/evals/checkpoint-N-strength-050-repairs.json

python training/checkpoint_gate.py \
  --base-paired artifacts/evals/base-paired.json \
  --candidate-paired artifacts/evals/checkpoint-N-strength-050-paired.json \
  --base-repairs artifacts/evals/base-repairs.json \
  --candidate-repairs artifacts/evals/checkpoint-N-strength-050-repairs.json \
  --checkpoint checkpoint-N --strength 0.50 \
  --output artifacts/evals/checkpoint-N-strength-050-gate.json
```

The engineering gate requires English overall and executable-code scores to
equal or beat the base, clear Kiswahili and code-switching gains, at least 98%
formatting, and no repair regression. A candidate that fails is never described
as a gate pass. If a time-boxed competition artifact is nevertheless published
for a separately scored bonus tradeoff, the exception and every regression must
be explicit in the model card and technical report.

## 4. Quantize only the winner

```bash
python training/build_imatrix_corpus.py \
  --input artifacts/data-v2/train.jsonl \
  --output artifacts/winner-imatrix-corpus.txt \
  --max-records 800 \
  --ratios en=0.50,sw=0.25,sw_mix=0.25 \
  --min-debug-ratio 0.15 \
  --supplement training/imatrix_structured_supplement.txt

llama-imatrix \
  -m artifacts/CodeFellow-winner-F16.gguf \
  -f artifacts/winner-imatrix-corpus.txt \
  -o artifacts/CodeFellow-winner-imatrix.gguf \
  --parse-special --chunks 120

llama-quantize \
  --imatrix artifacts/CodeFellow-winner-imatrix.gguf \
  artifacts/CodeFellow-winner-F16.gguf \
  artifacts/CodeFellow-3B-Kiswahili-Q4_K_M.gguf \
  Q4_K_M
```

Run the raw paired suite, repairs, and official profiler again on this Q4_K_M.
`release_gate.py` applies the same model-only quality requirements plus
throughput and RAM limits. Set `african_alpha_claim` to `true` only after that
final quantized artifact passes.
