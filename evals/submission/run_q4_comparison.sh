#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 4 || $# -gt 6 ]]; then
  echo "usage: $0 MODEL_GGUF MODEL_LABEL TASKS_JSON OUTPUT_DIR [PORT] [LIMIT]" >&2
  exit 2
fi

model_path=$1
model_label=$2
tasks_path=$3
output_dir=$4
port=${5:-8181}
limit=${6:-}
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
server_bin=${CODEFELLOW_LLAMA_SERVER:-"$repo_root/../llama.cpp/build-server/bin/llama-server"}
python_bin=${CODEFELLOW_PYTHON:-python3}
context_size=${CODEFELLOW_CTX_SIZE:-8192}
if (( context_size % 4 != 0 )); then
  echo "CODEFELLOW_CTX_SIZE must be divisible by four slots" >&2
  exit 2
fi
expected_slot_context=$((context_size / 4))
endpoint="http://127.0.0.1:${port}/v1/chat/completions"

mkdir -p "$output_dir"
cd "$repo_root"

taskset -c 0-3 "$server_bin" \
  -m "$model_path" \
  --host 127.0.0.1 --port "$port" \
  -c "$context_size" -t 4 -tb 4 -np 4 -ngl 0 \
  >"$output_dir/${model_label}-server.log" 2>&1 &
server_pid=$!

cleanup() {
  kill "$server_pid" 2>/dev/null || true
  wait "$server_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

ready=0
for _ in $(seq 1 90); do
  if curl --silent --fail "http://127.0.0.1:${port}/health" >/dev/null; then
    ready=1
    break
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    tail -n 80 "$output_dir/${model_label}-server.log" >&2
    exit 1
  fi
  sleep 1
done
if [[ "$ready" -ne 1 ]]; then
  echo "llama-server did not become ready" >&2
  exit 1
fi
if ! grep -Eq "n_ctx_slot = +${expected_slot_context}([, ]|$)" "$output_dir/${model_label}-server.log"; then
  echo "llama-server did not allocate the expected ${expected_slot_context}-token context per slot" >&2
  grep -E "n_slots|n_ctx_slot" "$output_dir/${model_label}-server.log" >&2 || true
  exit 1
fi

pids=()
limit_args=()
if [[ -n "$limit" ]]; then
  limit_args=(--limit "$limit")
fi
fresh_args=(--fresh)
if [[ "${CODEFELLOW_RESUME:-0}" == "1" ]]; then
  fresh_args=()
fi
chat_template_args=()
if [[ "${CODEFELLOW_DISABLE_THINKING:-0}" == "1" ]]; then
  chat_template_args=(--chat-template-kwargs '{"enable_thinking":false}')
elif [[ -n "${CODEFELLOW_CHAT_TEMPLATE_KWARGS:-}" ]]; then
  chat_template_args=(--chat-template-kwargs "$CODEFELLOW_CHAT_TEMPLATE_KWARGS")
fi
for language in en sw sw_mix; do
  "$python_bin" evals/kiswahili/run_eval.py \
    --endpoint "$endpoint" \
    --model "$model_label" \
    --tasks "$tasks_path" \
    --languages "$language" \
    --model-only "${fresh_args[@]}" \
    --code-max-tokens 320 \
    "${chat_template_args[@]}" \
    "${limit_args[@]}" \
    --output "$output_dir/${model_label}-${language}.json" \
    >"$output_dir/${model_label}-${language}.log" 2>&1 &
  pids+=("$!")
done

"$python_bin" evals/submission/run_format_eval.py \
  --endpoint "$endpoint" \
  --model "$model_label" \
  --workers 1 \
  "${chat_template_args[@]}" \
  "${limit_args[@]}" \
  --output "$output_dir/${model_label}-format.json" \
  >"$output_dir/${model_label}-format.log" 2>&1 &
pids+=("$!")

status=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    status=1
  fi
done
if [[ "$status" -ne 0 ]]; then
  echo "one or more evaluation clients failed; inspect $output_dir/*.log" >&2
  exit "$status"
fi

echo "completed raw comparison for $model_label"
