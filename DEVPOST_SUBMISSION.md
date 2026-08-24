# CodeFellow — DevPost Gate 1 Draft

## Project name

CodeFellow

## Elevator pitch

Learn, debug, and build—completely offline.

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
- Video: `ADD_2_MINUTE_VIDEO_URL`
- Team ID: `REPLACE_WITH_ADTF_TEAM_ID`

## Two-minute video script

### 0:00–0:15 — Problem

"Many African programming students learn on ordinary laptops and cannot depend on affordable cloud APIs or reliable internet. CodeFellow is an offline coding tutor for the hardware they already own."

### 0:15–0:35 — Product

"It is one 3B Q4_K_M model running locally through llama.cpp. It supports English, Kiswahili, and natural code-switching, while keeping programming identifiers and common English technical terms intact. No translator or cloud service is used in the submitted model path."

### 0:35–1:00 — Live demo

Show Task Prompt 1 in English, then Task Prompt 2 in Kiswahili/code-switching. Show the fenced implementation and one-sentence explanation. Disconnect networking or show that the endpoint is `127.0.0.1`.

### 1:00–1:25 — Engineering

"We trained from the original full-precision Qwen2.5-Coder parent on 10,000 verified examples. Parallel variants keep code identical across languages. Programs are executed, edge cases are tested, and weak examples are rejected with mutation testing. We partially merged the adapter to retain English quality and used a multilingual coding importance matrix for Q4 quantization."

### 1:25–1:48 — Evidence

Show the benchmark table and profiler JSON. Say: "All comparison runs use four CPU cores, native chat templates, temperature zero, equal 2,048-token contexts, no translator, and no postprocessing. The model stays below the 7 GB peak-RSS limit."

### 1:48–2:00 — Close

"CodeFellow combines coding assistance with education and useful Kiswahili access, completely offline. Learn, debug, and build—completely offline."

## Final Gate 1 checklist

- [ ] Replace Team ID in `metadata.json`, `REPORT.md`, and this file.
- [ ] Publish the selected GGUF and test `download_model.sh` from a clean directory.
- [x] Commit and push the final source repository.
- [x] Add profiler JSON and benchmark summary.
- [x] Capture English and Kiswahili demo screenshots.
- [ ] Record/upload the two-minute video and insert its URL.
- [ ] Submit on DevPost before the displayed deadline.
