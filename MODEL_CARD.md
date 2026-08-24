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

# CodeFellow 3B Kiswahili Instruct — GGUF

CodeFellow is an offline coding tutor for English, Kiswahili, and natural English–Kiswahili programming code-switching. This repository contains the selected importance-matrix-calibrated `Q4_K_M` GGUF for CPU-only `llama.cpp` inference.

## Model details

- Parent: `Qwen/Qwen2.5-Coder-3B-Instruct`
- Architecture: Qwen2 causal language model, approximately 3.09B parameters
- Merge: step-100 LoRA adapter at 0.45 strength
- Quantization: GGUF `Q4_K_M`, calibrated with an 800-record multilingual coding importance corpus
- Intended runtime: `llama.cpp`, native embedded ChatML/Jinja template
- Languages: English (`en`) and Kiswahili (`sw`), including code-switching
- Cloud dependency: none after download
- SHA-256: `50177433b86f9fdcd0161a89bdfdf0ec2819b396e9987bee5d743b3e9e822ea5`

## Training approach

The adapter used 10,000 assistant-response-only examples:

- 65% English coding replay
- 20% Kiswahili coding tutor interactions
- 15% English–Kiswahili code-switching

Parallel language variants preserve identical executable code and vary only the explanation. Python and JavaScript solutions were executed before admission, hidden edge cases were used where available, and mutation testing rejected weak task/test pairs. The adapter was deliberately only partially merged to retain the parent's English coding behavior.

## Intended use

- beginner programming explanations;
- small Python and JavaScript implementations and repairs;
- strict code/JSON/format contracts;
- Kiswahili tutoring that naturally retains common English programming terms.

This model is not intended for unsupervised production deployment, malware generation, or safety-critical software. Generated code must be reviewed and tested.

## Measured results

On the final independent 50-task model-only screen, CodeFellow passed 39/50 English, 21/50 Kiswahili, and 24/50 code-switched executable tasks. The untouched Qwen2.5 Q4 control passed 38/50, 24/50, and 29/50. CodeFellow improved strict exact-output contracts from 30/50 to 35/50 and improved measured language adherence, but it did not improve localized executable accuracy.

The official local ADTC profiler reported 0.82 ARC-Easy `acc_norm` over 50 samples. Five isolated four-core throughput runs produced a 4.67 tok/s median and 3,370.16 MiB worst observed peak RSS. These development results are not organizer-device guarantees.

## Basic llama.cpp use

```bash
llama-cli \
  -m CodeFellow-3B-Kiswahili-Instruct-Q4_K_M.gguf \
  -t 4 -c 2048 -n 320 --temp 0 --jinja \
  -p 'Tekeleza Python function square(x), kisha eleza approach kwa sentensi moja ya Kiswahili.'
```

## Evaluation policy

Model comparisons use temperature zero, native chat templates, CPU-only inference, equal context/output limits, no translator, no response postprocessor, and executable hidden tests. The independent screen is deduplicated against all 662 source tasks used to construct the training examples. Full raw JSON, the chat-template audit, and the evaluation scripts are published in the CodeFellow source repository.

Development measurements do not guarantee identical results on organizer hardware or hidden prompts.

## License

The weights are a derivative of Qwen2.5-Coder-3B-Instruct and retain the Qwen Research License linked in the metadata above.
