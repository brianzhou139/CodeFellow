# Technical Report — CodeFellow

**Team ID:** pending ADTF registration value

**Domain:** coding assistants

**Cross-disciplinary pairing:** programming education, with computational linguistics

**Core model:** unchanged Qwen2.5-Coder-3B-Instruct Q4_K_M

**Kiswahili layer:** NLLB-200-distilled-600M, CTranslate2 INT8

## 1. Problem and product

CodeFellow is an offline coding tutor for university, polytechnic, TVET, and bootcamp learners using budget laptops and intermittent connectivity. It focuses on beginner Python and JavaScript debugging in English and in the Kiswahili/English register programmers actually use.

The target failure is ungrounded tutoring: a generic chatbot can invent test results, replace an exercise instead of teaching its invariant, mistranslate one word that changes executable behaviour, or stop working when connectivity is unavailable. CodeFellow combines real local diagnostics, hint-first pedagogy, a coding-specialized model, and a terminology-aware Kiswahili route. It never claims generated code ran and never silently edits the learner's files.

## 2. Architecture

English requests take the shortest path:

1. read one learner-selected source file, capped at 64 KiB;
2. run Python syntax parsing or `node --check`, plus an optional learner-supplied test command;
3. prompt the unchanged Qwen Q4_K_M model through CPU-only `llama.cpp`;
4. apply a deterministic response contract that preserves one fenced implementation and removes obvious top-level demo calls.

Kiswahili and code-switched requests add a local language layer:

1. a reviewed programming glossary protects high-impact terms such as *shufwa* → `even`, `thamani tofauti` → `distinct values`, exact public interfaces, operators, exception names, and Big-O notation;
2. CPU-int8 NLLB translates only the natural-language requirement to English;
3. Qwen solves the technical task in the language where its coding ability is strongest;
4. NLLB translates teaching prose back to Kiswahili while fenced code is preserved byte-for-byte;
5. `sw-mix` rendering retains conventional terms such as `function`, `variable`, `array`, `input`, and `output`.

This is deliberately an application built **alongside** the selected model, not an irreversible replacement of it. English never loads the translator, so the base model's speed and accuracy remain available. A second local critic is optional rather than mandatory because it adds latency and did not consistently repair the hardest boundary case.

## 3. Why this differentiates the base model

The raw Q4 model is already strong at English coding, but the frozen paired evaluation found 27/30 English passes and only 10/30 in each Kiswahili lane. General translation alone also failed: it translated “even” as “empty/odd,” changed “distinct” into “difference,” dropped function names, and damaged complexity notation.

The winning contribution is therefore not a new name on the same GGUF. It is a verifiable offline system around it:

- semantic, domain-constrained translation rather than unconstrained prompt translation;
- exact interface and source-code preservation;
- local compiler/test evidence with claims tied to actual exit status;
- hint and full-answer teaching modes;
- predictable response formatting and no generated-code execution;
- a frozen English/Kiswahili/code-switch evaluation with executable tests.

Two LoRA phases were trained and converted during development. They improved brevity and some Kiswahili behavior but regressed several correct base answers and still omitted required fences. They were rejected by the English-preservation gate. The submitted architecture keeps the stronger original Q4 weights and puts specialization in the application layer, where each intervention is testable and reversible.

## 4. Hardware fit and model selection

The official target is an Ubuntu 22.04 laptop with four representative CPU cores, 8 GB DDR4, integrated graphics, and no discrete GPU. Comparable local selection runs used CPU-only `llama.cpp`.

| Candidate | GGUF size | Generation | Peak RSS | Official-profiler result |
|---|---:|---:|---:|---|
| Qwen3.5-4B Q4_K_M | 2.55 GiB | 3.19 tok/s | 4268.43 MiB | pass |
| Qwen3-4B-Instruct-2507 Q4_K_M | 2.23 GiB | 4.24 tok/s | 4384.09 MiB | pass |
| Qwen2.5-Coder-3B-Instruct Q4_K_M | 1.80 GiB | **4.89 tok/s** | **3370.07 MiB** | pass |

Qwen2.5-Coder-3B was selected because it had the best measured generation throughput, lowest peak memory, and highest default profiler accuracy of the three. The production NLLB conversion occupies about 600 MB on disk, loads in 3.8 seconds, translates two representative requirements in 6.3 seconds, and peaked at 1.13 GiB resident memory in isolation. The conservative combined estimate is about 4.5 GiB, leaving substantial headroom below 8 GB.

The final package layout was profiled again after the long multilingual and repair runs. The complete official profile measured 4.54 tok/s, 3370.37 MiB peak RSS, and 0.84 ARC-Easy accuracy; an isolated telemetry-only repeat measured 4.58 tok/s and 3370.12 MiB. The 4.54–4.89 tok/s spread is reported as run-to-run development-laptop variation, not as a model change.

## 5. Frozen application evaluation

The paired suite has 30 matched interactions per language: 25 executable Python/JavaScript tasks and five concept explanations. Code runs in resource-limited subprocesses against private assertions. Explanation rubrics check requested concepts; separate checks cover language evidence, mixed programming terms, fences, and top-level side effects. The public task file is excluded from training and calibration data.

| System/lane | Code | Explanations | Overall | Format | Language adherence |
|---|---:|---:|---:|---:|---:|
| Raw base — English | 22/25 | 5/5 | 27/30 (90.0%) | 96% | 63.3% |
| Raw base — Kiswahili | 10/25 | 0/5 | 10/30 (33.3%) | 88% | 40.0% |
| Raw base — code-switch | 9/25 | 1/5 | 10/30 (33.3%) | 88% | 20.0% |
| CodeFellow — English | **24/25** | **5/5** | **29/30 (96.7%)** | 96% | 63.3% |
| CodeFellow — Kiswahili, production CT2 | **24/25** | **5/5** | **29/30 (96.7%)** | 96% | **96.7%** |
| CodeFellow — code-switch, production CT2 | **24/25** | **5/5** | **29/30 (96.7%)** | **100%** | **100%** |

The Kiswahili gain is 63.4 percentage points with no English loss; English instead improves by 6.7 points under the deterministic application contract. All three lanes reach the same 96% executable-code rate and have exactly the same per-task pass/fail outcome. The remaining shared miss is a supplied sliding-window implementation whose invariant requires repeated removal; it fails in English too, demonstrating that the residual issue is base-model debugging depth rather than translation.

The separate 30-case execution-grounded repair stress test scores 20/30 at Pass@1 and 20/30 after one feedback turn, evenly split between Python and JavaScript. This matches the frozen base result and confirms no regression, but it also shows that a generic second critic pass is not a reliable improvement for this 3B model; it remains optional in the application.

Results are development-machine measurements, not claims about the organizers' unseen benchmark. JSON checkpoints live outside the repository under `work/benchmark-results/` in the development workspace. The evaluator and task definitions needed to reproduce them are committed under `evals/kiswahili/`.

## 6. Reproduction

Install and download all artifacts before disconnecting the network:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
bash download_model.sh
bash download_translation.sh
```

Run the application:

```bash
python3 codefellow.py examples/longest_unique_bug.py --full-answer
python3 codefellow.py examples/average_bug.js --language sw-mix \
  --question "Kwa nini function hii inafeli ikiwa array ni empty?" --full-answer
```

Run the official profiler after the Qwen model is present:

```bash
taskset -c 0-3 adtc-profiler run \
  --submission . --mode participant --output submission.json
```

Run the paired application evaluator against a local `llama-server`:

```bash
python3 evals/kiswahili/run_eval.py \
  --output artifacts/paired.json \
  --endpoint http://127.0.0.1:8181/v1/chat/completions \
  --languages en,sw,sw_mix \
  --application-contract \
  --ct2-nllb-model translation/nllb-200-distilled-600M-ct2-int8 \
  --nllb-roundtrip-explanations
```

## 7. Safety, licensing, and limitations

- Generated code is displayed but not executed or written to the learner's file.
- Only a test command explicitly supplied by the learner can run; it is parsed without a shell and bounded by time and output limits.
- The translator is a terminology-aware aid, not a certified translator. Exact code interfaces and notation are restored deterministically because machine translation can still mistranslate prose.
- The current product specializes in Python and JavaScript; repository-scale retrieval, IDE integration, and more languages are deliberately out of scope for this submission.
- The Qwen weights retain the Qwen Research License. NLLB and its conversion are CC-BY-NC-4.0 and are used only for this non-commercial competition research/evaluation prototype. Repository code is GPL-3.0.

## 8. Final device gates

Before submission, repeat these checks on a clean 4-vCPU/8-GB Ubuntu VPS and then the ADTC Standard Laptop:

1. install from the public scripts and disconnect networking;
2. run all 90 paired interactions and the separate repair suite;
3. run the official profiler three times with CPU-only inference;
4. record model-only and combined application peak RSS;
5. run ten minutes of repeated generation and check for thermal throttling;
6. demo hint mode, full-answer mode, English, Kiswahili, and code-switching with real local diagnostics.
