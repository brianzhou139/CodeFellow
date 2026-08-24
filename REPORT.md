# Technical Report — CodeFellow

**Team ID:** `codefellow`

**Domain:** Coding Assistants

**Cross-disciplinary integration:** Programming education

**Submitted model:** CodeFellow-3B-Kiswahili-Instruct-Q4_K_M

## 1. Submission summary

CodeFellow is a model-only-capable, offline coding tutor for English, Kiswahili, and natural English–Kiswahili code-switching. The submitted artifact is one `Q4_K_M` GGUF that runs directly in `llama.cpp`; no translator, cloud API, postprocessor, or external tool is present in the judged inference path.

The design goal is not general translation. It is to keep executable identifiers and conventional programming vocabulary exact while teaching the surrounding concept in the learner's language. The 3B parent was retained to maximize CPU throughput and RAM headroom on the ADTC Standard Laptop.

## 2. Artifact identity

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| Selected 0.45 imatrix Q4_K_M | 1,929,902,784 | `50177433b86f9fdcd0161a89bdfdf0ec2819b396e9987bee5d743b3e9e822ea5` |
| Experimental 0.50 imatrix control | 1,929,902,784 | `a7dd12a18cec1998e30989207c72fdf4d54da4704274abfb782e4985b9a70efb` |
| Experimental 0.50 ordinary control | 1,929,902,464 | `9f841f692acfb9fbd6f83727ae8be283dd868c3bcb5a48b4e4b3b6dcdbc4efa1` |

The selected GGUF was produced with `llama.cpp` quantizer version `0.2.0-dev`, commit `e85caa8`. `benchmark-results/submission-2026/quantization-manifest.json` records the commands and hashes.

## 3. Chat-template audit

Template parity was checked before attributing any failure to training:

- original and merged Hugging Face tokenizers contain the same Qwen ChatML/Jinja template;
- exact template SHA-256: `2b9959716c4694f8ecf6a387a88019d4797ad5a73cc371d36404d1bc44dfcbe1`;
- EOS is `<|im_end|>` (token 151645), assistant start is token 151644, and automatic BOS insertion is disabled;
- the GGUF embeds the native template;
- evaluation sends structured `messages` to `/v1/chat/completions` with temperature zero and no manual prompt approximation.

Conclusion: the observed differences are model behavior, not a template mismatch. The complete audit is in `benchmark-results/submission-2026/CHAT_TEMPLATE_AUDIT.md`.

## 4. Dataset and training

Training restarted from the original BF16/FP16 `Qwen2.5-Coder-3B-Instruct`; no failed checkpoint or quantized model was used as a parent.

The frozen v14 dataset contains 10,000 assistant-response-only examples:

| Lane | Share | Examples |
|---|---:|---:|
| English coding replay | 65% | 6,500 |
| Kiswahili coding tutor | 20% | 2,000 |
| English–Kiswahili code-switching | 15% | 1,500 |

There are 662 unique source tasks. Parallel variants lock the executable solution and vary only the teaching prose. Dataset gates include:

- Python/JavaScript execution;
- edge-case assertions;
- interface, code-fence, and completeness checks;
- rejection of invented APIs and unsafe constructs;
- mutation testing, with 90.8% of generated mutants killed;
- exact source-task separation between train and validation data.

The conservative LoRA run used assistant-response-only loss and checkpointed frequently. Step 100 was frozen and tested at uniform merge strengths 0.35, 0.45, 0.50, 0.75, and 1.00. Intact-parent domain quantization and an upper-eight-layer-only merge were also tested and rejected. Strength 0.45 was selected as the Gate 1 competition tradeoff after the full matched screen and official profiler run.

## 5. Importance-matrix quantization

The importance corpus has 800 records:

- 400 English;
- 200 Kiswahili;
- 200 code-switched;
- 686 generation and 114 debugging records;
- supplemental exact fences, tests, JSON, and output contracts.

In the original matched 12-task 0.50 quantization A/B, ordinary and imatrix builds tied on English (11/12) and Kiswahili (7/12), while imatrix improved code-switch executable pass rate from 6/12 to 8/12. That evidence fixed the quantization recipe before testing the 0.45 merge. The calibration activations were collected on the nearby 0.50 merge; this is disclosed in the quantization manifest.

## 6. Independent model-only evaluation

The screen is constructed from the MIT-licensed HumanEval corpus and is independent of the 662 training source tasks. Every canonical solution is executed against the upstream `check()` function before inclusion. Normalized token-Jaccard and sequence-similarity gates reject close training paraphrases.

Kiswahili prose is produced by a local teacher and must pass a round-trip semantic/anchor gate. Exact public function signatures are restored after prose translation and verified across all 50 tasks. An earlier partial screen was invalidated when this audit found that the teacher had translated a few public names; those results are kept out of the final comparison.

All raw-model runs use:

- CPU-only `llama.cpp` on cores 0–3;
- native embedded chat template;
- temperature 0;
- equal 2,048-token per-request context and equal output limits;
- no translator, review pass, application prompt, or response postprocessor;
- executable hidden tests in resource-limited subprocesses.

### Final 50-task matched screen

| Model | English code | Kiswahili code | Code-switch code | Strict contracts |
|---|---:|---:|---:|---:|
| **CodeFellow 0.45 imatrix Q4_K_M** | **39/50 (78%)** | 21/50 (42%) | 24/50 (48%) | **35/50 (70%)** |
| Qwen2.5-Coder-3B-Instruct Q4_K_M | 38/50 (76%) | **24/50 (48%)** | **29/50 (58%)** | 30/50 (60%) |

CodeFellow improved English execution by one task, strict contracts by five tasks, Kiswahili adherence from 42% to 52%, and code-switch adherence from 6% to 24%. The base retained a three-task Kiswahili and five-task code-switch execution lead. Exact fences were 20/20 for both; CodeFellow improved exact JSON from 0/15 to 5/15. The weighted local composite was 59.9 for CodeFellow versus 61.3 for the base, a 1.4-point gap before any African-use-case bonus.

### Broader 12-task model screen

| Model | English | Kiswahili | Code-switch | Strict format |
|---|---:|---:|---:|---:|
| CodeFellow 0.45 | 11/12 | 8/12 | 9/12 | 12/12 |
| Qwen2.5-Coder-3B | 12/12 | 8/12 | 10/12 | 12/12 |
| Qwen3-4B-Instruct-2507 | 10/12 | 7/12 | 7/12 | 12/12 |
| Qwen3.5-4B, non-thinking | 11/12 | 7/12 | 9/12 | 12/12 |

Qwen3.5 was evaluated with its official `enable_thinking=false` chat-template option. It matched CodeFellow's rapid executable counts but required more RAM and was materially slower. Raw JSON, native template parameters, and rejected-candidate results are published under `benchmark-results/submission-2026/`.

## 7. Hardware selection

The ADTC profiler is run separately from the accuracy clients because concurrent evaluation latency is not a throughput measurement. Existing CPU-only comparison telemetry on the development machine is:

| Candidate | Generation | Peak RSS | Profiler accuracy | Result |
|---|---:|---:|---:|---|
| Qwen2.5-Coder-3B-Instruct Q4_K_M | 4.89 tok/s | 3,370.07 MiB | 0.84 | pass |
| **CodeFellow 0.45 Q4_K_M** | **4.67 tok/s median** | **3,370.16 MiB max** | **0.82** | **pass** |
| Qwen3-4B-Instruct-2507 Q4_K_M | 4.24 tok/s | 4,384.09 MiB | 0.82 | pass |
| Qwen3.5-4B Q4_K_M | 3.19 tok/s | 4,268.43 MiB | 0.76 | pass |

CodeFellow's five clean four-core runs measured 4.66, 4.68, 4.67, 4.68, and 4.67 tok/s. Peak RSS ranged from 3,369.98 to 3,370.16 MiB. A separate accuracy-enabled official run produced 0.82 `acc_norm` over 50 ARC-Easy samples and a schema-valid report. These are local selection measurements, not organizer-device claims.

The final full participant rerun after synchronizing the Devpost prompts produced 4.74 generation tok/s, 14,183.56 ms first-token latency, 3,369.94 MiB peak RSS, and 0.82 `acc_norm` over 50 samples. It records Team ID `codefellow` and source commit `847b98bfd94f` in `benchmark-results/submission-2026/submission.json`. Using the profiler's published formulas, the self-reported form scores are **Sperf 31.60** and **Seff 52.99**. The development laptop contains an NVIDIA GPU, but the profiler forces CPU inference with `-ngl 0`; these remain development measurements rather than Standard Laptop claims.

## 8. Failure analysis and release decision

The full screen rejects the claim that this checkpoint universally improves localized coding: it does not. The 0.45 merge loses three Kiswahili and five code-switch executable tasks relative to the base, even while improving English, exact contracts, adherence, and concision. Uniform 0.35/0.50, intact-parent domain quantization, and upper-layer-only controls did not produce a better rapid balance.

Gate 1 selection is therefore a calculated scoring decision, not a claim of dominance on every lane. The official accuracy loss is 0.02, speed/RAM remain in the stronger 3B class, and CodeFellow adds measurable format/adherence behavior that supports ADTC's African-use-case bonus of up to 10 points. A future weight release must recover the localized executable regressions before replacing this frozen artifact.

## 9. Reproduction

Download the final GGUF and verify its published checksum:

```bash
bash download_model.sh
sha256sum model/CodeFellow-Q4_K_M.gguf
```

Run the official profiler:

```bash
taskset -c 0-3 adtc-profiler run \
  --submission . --mode participant \
  --output benchmark-results/submission-2026/submission.json
```

Run the raw comparison helper:

```bash
CODEFELLOW_PYTHON=.venv/bin/python \
bash evals/submission/run_q4_comparison.sh \
  model/CodeFellow-Q4_K_M.gguf \
  codefellow \
  benchmark-results/submission-2026/humaneval-screen50.json \
  benchmark-results/submission-2026/reproduction
```

## 10. Safety, licensing, and limitations

- Generated code must be reviewed and tested.
- The optional application never executes model-generated code or silently edits learner files.
- The specialization targets Python/JavaScript learning and natural Kiswahili programming code-switching; it is not a general translation system.
- Qwen derivative weights retain the Qwen Research License. Repository code is GPL-3.0.
- Results are development measurements and do not predict the three hidden judge prompts with certainty.
