# Native chat-template audit

Status: **passed** for the frozen v14 step-100, strength-0.50 candidate.

## HF parent and merged model

- Original parent:
  `/home/debian_isle/codefellow-training/base-qwen25`
- Frozen merged model:
  `/home/debian_isle/codefellow-training/merged-sw-v14-step100-s050`
- Extracted `chat_template` SHA-256 for both models:
  `2b9959716c4694f8ecf6a387a88019d4797ad5a73cc371d36404d1bc44dfcbe1`
- Template: native Qwen ChatML/Jinja using `<|im_start|>ROLE`, message
  content, `<|im_end|>`, and `<|im_start|>assistant` for generation.
- `add_bos_token`: `false`.
- HF `eos_token`: `<|im_end|>`.

## Converted GGUF

- `tokenizer.ggml.eos_token_id`: `151645` (`<|im_end|>`).
- `tokenizer.ggml.bos_token_id`: `151643` (`<|endoftext|>`).
- `tokenizer.ggml.add_bos_token`: `false`.
- `tokenizer.chat_template` is embedded in the GGUF metadata.
- Special-token mapping also contains `151644 = <|im_start|>`.

## Evaluation path

`evals/kiswahili/run_eval.py` sends an OpenAI-compatible `messages` array to
`/v1/chat/completions`. `llama-server` is launched without
`--chat-template`, `--chat-template-file`, or another prompt override, so the
embedded native template is authoritative. Temperature is zero and no
translator, response normalizer, self-review pass, or application contract is
enabled under `--model-only`.

Conclusion: the observed pilot formatting and stopping failures are not caused
by an HF/GGUF/evaluator chat-template mismatch.
