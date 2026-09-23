---
license: other
license_name: qwen-research
license_link: https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct/blob/main/LICENSE
base_model: Qwen/Qwen2.5-Coder-3B-Instruct
language:
- en
- sw
pipeline_tag: text-generation
library_name: gguf
tags:
- code
- coding-assistant
- education
- kiswahili
- swahili
- gguf
- llama.cpp
---

# CodeFellow Gate 2 — GGUF

CodeFellow is an offline coding tutor for English, Kiswahili, and natural English–Kiswahili programming code-switching. The current submitted artifact is `CodeFellow-qlora250-s100-Q4_K_M.gguf` for CPU-only `llama.cpp` inference.

## Model details

- Parent: `Qwen/Qwen2.5-Coder-3B-Instruct`
- Architecture: Qwen2 causal language model, approximately 3.09B parameters
- Parent revision: `488639f1ff808d1d3d0ba301aef8c11461451ec5`
- Adaptation: rank-16 QLoRA, 250 optimizer steps, merged at strength 1.0
- Quantization: standard GGUF `Q4_K_M` without an importance matrix
- Intended runtime: `llama.cpp`, native embedded ChatML/Jinja template
- Languages: English (`en`) and Kiswahili (`sw`), including code-switching
- Cloud dependency: none after download
- SHA-256: `92ae1b93b4248fec6efccc6fee0e83e1b4b0cb883ce740ab3d03a490c2647cb2`

## Training approach

The Gate 2 adapter used 4,000 training and 400 validation examples:

- 65% English coding replay
- 20% Kiswahili coding tutor interactions
- 15% English–Kiswahili code-switching

Training used assistant-response-only loss. The exact training records, validation records, adapter, trainer history, source licenses, and conversion scripts are in [`provenance/`](provenance/). The earlier 10,000-example curriculum and 0.45-strength adapter belonged to Gate 1; see the historical comparison in `REPORT.md`.

## Intended use

- beginner programming explanations;
- small Python and JavaScript implementations and repairs;
- strict code/JSON/format contracts;
- Kiswahili tutoring that naturally retains common English programming terms.

This model is not intended for unsupervised production deployment, malware generation, or safety-critical software. Generated code must be reviewed and tested.

## Historical Gate 1 results

The Gate 1 model passed 39/50 English, 21/50 Kiswahili, and 24/50 code-switched executable tasks. The untouched Qwen2.5 Q4 control passed 38/50, 24/50, and 29/50. The Gate 1 model improved strict exact-output contracts from 30/50 to 35/50 and improved measured language adherence, but it did not improve localized executable accuracy. These figures do not describe the Gate 2 GGUF.

The Gate 1 local ADTC profiler reported 0.82 ARC-Easy `acc_norm` over 50 samples. Five isolated four-core throughput runs produced a 4.67 tok/s median and 3,370.16 MiB worst observed peak RSS. These historical development results are not Gate 2 or organizer-device measurements.

## Basic llama.cpp use

```bash
llama-cli \
  -m model/CodeFellow-qlora250-s100-Q4_K_M.gguf \
  -t 4 -c 2048 -n 320 --temp 0 --jinja \
  -p 'Tekeleza Python function square(x), kisha eleza approach kwa sentensi moja ya Kiswahili.'
```

## Evaluation policy

The historical Gate 1 model comparisons used temperature zero, native chat templates, CPU-only inference, equal context/output limits, no translator, no response postprocessor, and executable hidden tests. Gate 2 paired development examples are recorded in `provenance/evaluation/`.

Development measurements do not guarantee identical results on organizer hardware or hidden prompts.

## License

The weights are a derivative of Qwen2.5-Coder-3B-Instruct and retain the Qwen Research License linked in the metadata above.
