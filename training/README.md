# CodeFellow adaptation pipeline

This directory builds a merged Qwen2.5-Coder-3B-Instruct derivative and then returns it to the competition's GGUF Q4_K_M format. The existing Q4_K_M is a baseline only; quantized weights are not trained or requantized.

## Data policy

- `evals/cases.py`, `evals/kiswahili/tasks.json`, and the two declared prompts are excluded from training and calibration.
- Project-authored repair solutions are executed before dataset creation.
- MBPP reference solutions are retained only when their tests pass locally.
- CodeFeedback data is used as English replay, not described as locally execution-verified.
- English, Kiswahili, and natural Kiswahili/English code-switching variants from the same source stay in the same train/validation split.

## Build data

```bash
python training/build_dataset.py \
  --output-dir artifacts/data \
  --codefeedback-limit 1800 \
  --mbpp-limit 400 \
  --swahili-mbpp-limit 400 \
  --swahili-scaffold-limit 0 \
  --mixed-mbpp-limit 400 \
  --locale-repeat 1
```

The default build downloads the public CodeFeedback and MBPP datasets. Project-authored repair and tutoring prompts provide reviewed Kiswahili. The active pure-Kiswahili lane uses NLLB translation for the natural-language task description while preserving each locally verified MBPP reference implementation. Its response contract mirrors the application's Kiswahili format instruction: exactly one fenced implementation, one short Kiswahili explanation, and no tests. The separate mixed lane keeps the exact English technical requirement and conventional English programming vocabulary. Do not combine the old English-requirement Kiswahili scaffold with this lane during training; it teaches a different prompt pattern and is retained only as an ablation switch. The trainer drops records that cannot fit with their assistant response intact; use `--english-repeat` to preserve English replay after that filter.

Fail closed if another language leaks into the active data or a source crosses splits:

```bash
python training/validate_dataset.py \
  --train artifacts/data/train.jsonl \
  --validation artifacts/data/validation.jsonl \
  --languages en,sw,sw_mix
```

## Train

The default configuration is intentionally conservative for a 6 GB GTX 1660 Ti and evaluates only at the final checkpoint:

```bash
python training/train_qlora.py \
  --train artifacts/data/train.jsonl \
  --validation artifacts/data/validation.jsonl \
  --output artifacts/run-r32 \
  --lora-rank 16 \
  --max-seq-length 320 \
  --max-steps 500 \
  --gradient-accumulation-steps 1 \
  --eval-limit 64 \
  --checkpoint-interval 100 \
  --english-repeat 2 \
  --learning-rate 2e-5
```

The trainer keeps only complete conversations that fit the token cap, then repeats the retained English lane once to counter the fact that shorter localized prompts survive length filtering at a higher rate. It checks GPU temperature after every micro-step, saves a recovery checkpoint every 100 steps, and runs validation only at the final step. It pauses at 84 C and resumes at 80 C by default. The thresholds can be changed with `--max-gpu-temp` and `--resume-gpu-temp`; disabling the guard is intentionally not the default on a laptop. Resume an interrupted run with `--resume-from-checkpoint artifacts/run-r32/checkpoint-N`.

## Merge and quantize

```bash
python training/merge_adapter.py \
  --adapter artifacts/run-r32/adapter \
  --output artifacts/merged-f16

python /path/to/llama.cpp/convert_hf_to_gguf.py \
  artifacts/merged-f16 \
  --outfile artifacts/CodeFellow-F16.gguf \
  --outtype f16

python training/build_imatrix_corpus.py \
  --input artifacts/data/train.jsonl \
  --output artifacts/imatrix-corpus.txt

llama-imatrix \
  -m artifacts/CodeFellow-F16.gguf \
  -f artifacts/imatrix-corpus.txt \
  -o artifacts/codefellow-imatrix.gguf \
  --parse-special --chunks 120

llama-quantize \
  --imatrix artifacts/codefellow-imatrix.gguf \
  artifacts/CodeFellow-F16.gguf \
  artifacts/CodeFellow-3B-RepairTutor-sw-Q4_K_M.gguf \
  Q4_K_M
```

The derivative is not eligible for release until it beats the original model on the frozen English/Kiswahili/code-switching evaluation and remains within the throughput, RAM, and thermal gates documented in `REPORT.md`. Apply the non-negotiable gates with:

```bash
python3 training/release_gate.py \
  --base-paired artifacts/evals/base-paired.json \
  --candidate-paired artifacts/evals/candidate-paired.json \
  --base-repairs artifacts/evals/base-repairs.json \
  --candidate-repairs artifacts/evals/candidate-repairs.json \
  --base-profiler artifacts/evals/base-profiler.json \
  --candidate-profiler artifacts/evals/candidate-profiler.json \
  --output artifacts/evals/release-gate.json
```
