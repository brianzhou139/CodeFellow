# CodeFellow

**Learn, debug, and build—completely offline.**

CodeFellow is a private, on-device coding tutor for learners who cannot assume reliable or affordable internet access. It combines the unchanged Qwen2.5-Coder-3B-Instruct Q4_K_M coding model, a 600 MB CPU-int8 Kiswahili translation model, and real local diagnostics from Python or Node.js. It supports English and the natural Kiswahili/English code-switching register used in programming classrooms, preserving terms such as `function`, `array`, `API`, and `runtime` instead of forcing artificial translations.

Qwen runs through `llama.cpp`; the Kiswahili language layer runs through CTranslate2 and SentencePiece. No cloud API is called during use.

## Why this problem

Many university, polytechnic, TVET, and bootcamp learners in Southern Africa practice on budget laptops and intermittent connections. A generic chatbot may invent compiler results and often gives away a full solution before a learner understands the bug. CodeFellow instead grounds its response in diagnostics produced on the learner's own laptop and lets the learner request either a guided hint or a full worked explanation.

## Cross-disciplinary integration

The primary pairing is **coding assistants + education**, with computational linguistics as a second load-bearing integration:

- hint mode asks questions, identifies one concept, and avoids replacing the whole solution;
- full mode explains the root cause, proposes a minimal patch, and suggests tests;
- the prompt includes real syntax diagnostics produced locally, so tutoring is tied to executable evidence rather than a cosmetic persona.
- a constrained Kiswahili programming glossary protects identifiers, operators, complexity notation, and semantic terms such as *shufwa* (even) before local translation;
- fenced code is never translated, while teaching prose can be rendered in Kiswahili or natural Kiswahili/English code-switching.

## Quick start

Requirements: Ubuntu/Linux, Python 3.10+, a current `llama.cpp` build containing `llama-cli`, roughly 3 GB of free disk space, and 8 GB RAM.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

bash download_model.sh
bash download_translation.sh

# Guided hint for a Python or JavaScript file
python3 codefellow.py app.py --question "Why does this fail on repeated values?"

# Full diagnosis and patch guidance
python3 codefellow.py app.py --full-answer

# Higher-accuracy two-pass mode: a second local critic checks the first draft
python3 codefellow.py app.py --full-answer --review

# Ground the answer in a trusted test command that you choose
python3 codefellow.py app.py --full-answer --test-command "python3 -m pytest -q"

# Reproduce the two included demo scenarios
python3 codefellow.py examples/longest_unique_bug.py \
  --question "Why is the answer for abba wrong?" --full-answer
python3 codefellow.py examples/average_bug.js \
  --question "Help me handle empty input and numeric strings."

# Kiswahili teaching prose with standard English coding vocabulary
python3 codefellow.py examples/average_bug.js --language sw-mix \
  --question "Kwa nini function hii inafeli ikiwa array ni empty?" --full-answer

# Override runtime paths when llama-cli is not on PATH
python3 codefellow.py app.py \
  --llama-cli /path/to/llama.cpp/build/bin/llama-cli \
  --model /path/to/model.gguf
```

CodeFellow reads at most 64 KiB from the selected source file. Python files are checked with the standard-library syntax parser without creating bytecode; JavaScript files are checked with `node --check` when Node.js is installed. A learner may explicitly supply a trusted `--test-command`; it runs without a shell, in the source directory, with a 45-second timeout and bounded captured output. Test evidence is placed in the model prompt so the diagnosis is tied to an actual failure.

For Kiswahili requests, CodeFellow first protects exact programming contracts and translates only the natural-language requirement to English. Qwen solves the technical problem in its strongest language. The local language layer then translates teaching prose back to Kiswahili while preserving fenced code exactly. In `sw-mix` mode it retains conventional English programming vocabulary. English requests bypass the translator completely, preserving the base model's speed and accuracy.

When a compact model returns bare replacement code in full-answer mode, CodeFellow's deterministic response-contract layer wraps it in one language-labelled code block and removes only obvious top-level demo execution after the final Python or JavaScript definition. The model still produces the implementation, and generated code is never executed by this layer. This makes formatting and safety predictable without weakening the underlying model or requiring a cloud retry.

The runtime explicitly disables hidden reasoning traces and reserves the token budget for the learner-facing answer. This keeps responses predictable on compact thinking-capable models.

## ADTC profiler smoke test

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install "git+https://github.com/Africa-Deep-Tech-Foundation/adtc-profiler.git"

adtc-profiler run \
  --submission . \
  --mode participant \
  --output submission.json \
  --skip-accuracy
```

The model is downloaded before evaluation. Once the model is present, both the application and profiler inference path operate without network access.

## Repository layout

- `codefellow.py` — offline tutor and local-diagnostics application
- `translation_backend.py` — terminology-aware Kiswahili routing and CPU-int8 NLLB runtime
- `response_contract.py` — deterministic formatting, demo removal, and code-switch register
- `metadata.json` — ADTC submission metadata and two declared prompts
- `download_model.sh` — public, resumable, checksum-verified model download
- `download_translation.sh` — public, resumable, checksum-verified translator download
- `REPORT.md` — design rationale and reproducible benchmark results
- `examples/` — small Python and JavaScript demo bugs
- `model/` — local GGUF weights, excluded from Git

## Safety and scope

CodeFellow is a learning tool. It does not execute model-generated code, make network requests, or silently edit the learner's files. It runs a project test command only when the learner explicitly supplies `--test-command`; that command is never constructed by the model.

## License

Repository code is distributed under [GPL-3.0](LICENSE). Qwen retains the Qwen Research License. The NLLB translator is CC-BY-NC-4.0 and is included for this non-commercial research/evaluation prototype; see `NOTICE` and `THIRD_PARTY_LICENSES/`.
