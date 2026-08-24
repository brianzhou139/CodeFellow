# CodeFellow — DevPost Gate 1 Draft

## Project name

CodeFellow

## Elevator pitch

Learn, debug, and build—no internet required.

## Domain

Coding Assistants

## African use case

Programming students at universities, polytechnics, TVET institutions, and bootcamps cannot always assume affordable cloud APIs or reliable connectivity. CodeFellow puts a bilingual coding tutor directly on an ordinary 8 GB laptop. It explains Python and JavaScript in English, Kiswahili, or the natural English–Kiswahili code-switching register used in real classrooms, while preserving executable identifiers and conventional terms such as `function`, `list`, `API`, and `runtime`.

## What it does

CodeFellow is a 3B CPU-ready GGUF coding tutor that runs entirely through `llama.cpp`. It generates and debugs code, follows strict output contracts, and gives short beginner-friendly explanations. Kiswahili behavior is inside the submitted model; the judged path uses no translator, cloud API, response postprocessor, or external tool.

The optional local application can add syntax diagnostics and learner-supplied test output to the prompt. This connects coding assistance with programming education: a response must be technically useful and teach the concept at the learner's level.

## How it was built

We restarted from the original BF16/FP16 Qwen2.5-Coder-3B-Instruct model and created 10,000 verified assistant-response-only examples:

- 65% English coding replay;
- 20% Kiswahili programming tutoring;
- 15% English–Kiswahili code-switching.

Each parallel language triple keeps the executable solution identical and changes only the explanation. Python and JavaScript candidates are compiled or executed, edge cases are tested, and mutation testing rejects weak examples. A conservative LoRA checkpoint was merged at 0.45 strength after matched strength controls. The final Q4_K_M uses a domain importance matrix containing English code, debugging, Kiswahili prose, code-switching, tests, fences, JSON, and strict formatting contracts.

We compare the derivative against the untouched Qwen2.5-Coder-3B model, Qwen3-4B-Instruct-2507, and Qwen3.5-4B using native templates, temperature zero, four CPU cores, equal context/output limits, and no supporting application stack.

## What makes it different

- The African-language capability is in the GGUF itself, matching ADTC's model-only judging scope.
- It specializes in Kiswahili programming code-switching rather than unnatural word-for-word translation.
- Correct code is locked across parallel language variants.
- Executable tests and mutation gates filter the training set.
- A partial adapter merge protects the parent model's English coding behavior.
- The 3B model preserves throughput and RAM headroom on the reference laptop.
- The complete training and evaluation pipeline is public and reproducible.

## Challenges

The hardest problem was preventing language specialization from damaging code. Translation teachers sometimes changed a public identifier such as `add` to `kuongeza`, and small preliminary screens made single failures look larger than they were. We addressed this by locking code across parallel variants, auditing native chat-template parity, restoring exact public signatures in evaluation prompts, executing every benchmark solution, and invalidating results whenever the harness violated equal-context rules.

## Accomplishments

- One offline 3B GGUF with native English and Kiswahili/code-switching support.
- 10,000-example verified dataset with 662 unique source tasks.
- 90.8% generated mutation kill rate.
- Exact chat-template parity proven across parent, merge, and GGUF.
- Ordinary and importance-matrix Q4_K_M controls with published SHA-256 hashes.
- Independent HumanEval-derived screen deduplicated against all training source tasks.
- Strict exact-output suite covering fenced code, JSON, and bullet contracts.
- Reproducible four-core ADTC profiler and raw-model comparison scripts.
- Official local profiler: 0.82 accuracy, 4.67 tok/s five-run median, and 3,370.16 MiB worst peak RSS.
- Final 50-task audit showing both gains (English, format, adherence) and localized executable regressions, published without cherry-picking.

## What we learned

Multilingual coding quality cannot be measured by translated prose alone. Function signatures, identifiers, tests, and code must be treated as immutable contracts. We also learned that quantization, chat templates, per-slot context allocation, response formatting, throughput, and peak RSS must be audited together; a higher benchmark score on a large model does not automatically make it the best laptop submission.

## What's next

The current release is frozen for Gate 1. The next repair experiment will target localized executable regressions and exact JSON contracts with explanation-only loss and layer-restricted adapters, while enforcing the same English-retention and executable-code gates.

## Built with

Qwen2.5-Coder, PyTorch, Hugging Face Transformers, PEFT/LoRA, llama.cpp, GGUF Q4_K_M, Python, JavaScript, pytest, HumanEval, CTranslate2/NLLB as a data teacher, and the ADTC profiler.

## Links

- Source: https://github.com/brianzhou139/CodeFellow
- Model: https://github.com/brianzhou139/CodeFellow/releases/download/gate1-v1/CodeFellow-3B-Kiswahili-Instruct-Q4_K_M.gguf
- Video: submitted with the project on the ADTC platform (the platform entry is the source of truth for its hosted URL)
- Team ID: `codefellow`

## Two-minute video script

### 0:00–0:12 — Problem

Data fees, unreliable connectivity, and recurring API charges can decide who gets access to programming support.

### 0:12–0:22 — Product

Introduce CodeFellow as an offline coding tutor for the laptop a student already has.

### 0:22–0:51 — English and Kiswahili demos

Stream the audited English and Kiswahili/code-switched outputs, labelled as recorded local output. Show `127.0.0.1`, CPU inference, executable code, and short teaching explanations.

### 0:51–1:07 — Genuine debugging run

Show a real `codefellow.py` run against `average_bug.js`: the empty-array failure, a hint-first observation, and a concrete next step without silently editing the learner's file.

### 1:07–1:22 — Engineering

Show the 10,000-example verified data pipeline: identical code locked across languages, edge-case execution, and mutation testing.

### 1:22–1:37 — Measured performance

Show official local-profiler results: 4.72 tokens/second, 3.29 GiB peak memory, 0.82 ARC-Easy accuracy, four CPU cores, no GPU, and no thermal throttling.

### 1:37–1:52 — Impact

Connect the model to private, repeatable programming support for students, bootcamps, TVETs, and technical colleges.

### 1:52–2:00 — Close

"CodeFellow is open, reproducible, and ready for audit. Learn, debug, and build—no internet required."

## Final Gate 1 checklist

- [x] Set Team ID to `codefellow` in `metadata.json`, `REPORT.md`, and this file.
- [x] Publish the selected GGUF and test `download_model.sh` from a clean directory.
- [x] Commit and push the final source repository.
- [x] Add profiler JSON and benchmark summary.
- [x] Capture English and Kiswahili demo screenshots.
- [x] Render and verify the two-minute video.
- [x] Upload the two-minute video with the platform submission.
- [x] Submit the project on the ADTC platform.
