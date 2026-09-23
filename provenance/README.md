# CodeFellow Gate 2 provenance

This directory records the reproducible weight-level training and conversion
path for the Gate 2 candidate. It contains the adapter, training scripts,
run evidence, dataset description, parent revision, and quantization details.

The model was fine-tuned with QLoRA from the immutable
`Qwen/Qwen2.5-Coder-3B-Instruct` parent, merged into the parent weights, and
converted and quantized with `llama.cpp`. The inference submission contains
only the resulting GGUF and uses no network dependency after download.

The exact 4,000 training and 400 validation records are in `data/`. Source
names, licenses, counts, and file hashes are in `dataset-manifest.json`.
`training/trainer_state.json` contains the loss and evaluation history through
optimizer step 250; `training/training_result.json` records the final training
result. The adapter is included as direct proof of weight-level fine-tuning.
`evaluation/paired-examples.json` contains two recorded same-prompt comparisons
with the unmodified Qwen2.5-Coder-3B Q4 control. These are development
examples, not a final performance score. Native-speaker review is not claimed.
