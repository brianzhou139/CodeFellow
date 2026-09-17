# CodeFellow Gate 2 provenance

This directory records the reproducible weight-level training and conversion
path for the Gate 2 candidate. It contains the adapter, training scripts,
run evidence, dataset description, parent revision, and quantization details.

The model was fine-tuned with QLoRA from the immutable
`Qwen/Qwen2.5-Coder-3B-Instruct` parent, merged into the parent weights, and
converted and quantized with `llama.cpp`. The inference submission contains
only the resulting GGUF and uses no network dependency after download.

Training records are project-authored and derived from licensed programming
task sources where noted in the dataset manifest. The full training corpus is
not committed here; the representative manifest and review description are
included instead. The adapter is included as direct proof of weight-level
fine-tuning.
