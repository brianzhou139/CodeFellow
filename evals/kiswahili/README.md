# CodeFellow English/Kiswahili/code-switching evaluation

This frozen release evaluation measures the same 30 coding-assistant tasks in
English, Kiswahili, and natural Kiswahili/English code-switching. It produces
90 model responses in total. The directory name is retained only for historical
compatibility with the earlier language screen.

The task set contains:

- 10 Python implementation tasks
- 5 JavaScript implementation tasks
- 5 Python debugging tasks
- 5 JavaScript debugging tasks
- 5 programming explanation and diagnosis tasks

Code answers are executed against language-independent assertions in isolated,
resource-limited subprocesses. The evaluator rejects filesystem, network,
shell, and external-process access. It records technical correctness, requested
code-block formatting, unexpected example output, language evidence, token use,
finish reason, and inference time. Explanation tasks use explicit concept
rubrics and should also receive a manual fluency review.

## Requirements

- Linux or WSL (the runner uses POSIX resource limits)
- Python 3.10 or newer
- Node.js at `/usr/bin/node`
- A local llama.cpp server exposing the OpenAI-compatible chat endpoint

Production-lane evaluation also needs the local dependencies from
`requirements.txt` and the downloaded CTranslate2 translator. No cloud service
is used during evaluation.

## Run

Start the server from the workspace root:

```bash
./work/llama.cpp/build-server/bin/llama-server \
  -m ./work/model-candidates/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf \
  -ngl 0 -t 4 -c 4096 -np 1 \
  --host 127.0.0.1 --port 8181 --jinja --no-ui
```

Then run the full evaluation from the CodeFellow repository:

```bash
python3 evals/kiswahili/run_eval.py \
  --output english-kiswahili-codeswitch.json \
  --languages en,sw,sw_mix \
  --seed 42 \
  --fresh
```

Use `--limit 2` for a six-response smoke test. Without `--fresh`, the runner
resumes a compatible checkpoint and skips completed task-language pairs.

The default generation settings are temperature 0, 240 maximum output tokens
for code, and 160 for explanations. Keep these fixed when comparing model or
prompt variants.

## Interpreting the result

`technical_pass` is the primary code metric. `format_compliant` and
`side_effect_free` expose instruction-following failures that can still occur
when hidden tests pass. `language_adherent` is only a small lexical-evidence
check; it is not a fluency or translation-quality score. For `sw_mix`, the check
requires both Kiswahili evidence and at least one conventional English technical
term outside the code block. Manually review every explanation response and a
stratified sample of code explanations before making product claims.

This is a development evaluation, not an official ADTC benchmark. Add new tasks
to a held-out set rather than tuning directly against these 30 assertions.
