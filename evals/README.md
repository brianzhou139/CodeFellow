# Executable repair evaluation

`run_repairs.py` evaluates the configured model on 30 deterministic beginner repairs: 15 Python and 15 JavaScript. The evaluator asks for one complete corrected source file, extracts its fenced code block, applies a conservative static safety check, and runs the code with fixed tests under CPU, memory, file-size, descriptor, and wall-time limits.

Run from the repository root on Linux:

```bash
python3 evals/run_repairs.py \
  --model /path/to/CodeFellow-Q4_K_M.gguf \
  --llama-cli /path/to/llama-cli \
  --output /tmp/codefellow-repairs.json
```

For faster repeated evaluation, keep the same GGUF loaded in a local
`llama-server` and use `--endpoint http://127.0.0.1:8181/v1/chat/completions`
instead of `--model` and `--llama-cli`. This changes only model loading; prompts,
extraction, safety checks, private execution, and repair feedback are identical.

The JSON file is saved atomically after every case. Re-run the same command to resume; pass `--overwrite` to start again. The report separates first-attempt success from success after one execution-grounded repair turn (`Pass@1` and `Pass@2`). Use `--max-attempts 1` to disable repair feedback. Generated code is executed only by this explicit evaluation tool. The learner-facing `codefellow.py` application continues to display suggestions without executing them.

Each model turn has a 180-second benchmark timeout by default (`--generation-timeout`). The learner-facing application uses a five-minute ceiling for its larger default answer budget.

Use `--case py12_rotate_right` to run one named case in isolation; repeat `--case` to select several cases.
Use `--rerun-failures` to keep passing checkpoints while retesting failed selected cases.
