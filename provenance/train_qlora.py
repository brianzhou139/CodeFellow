#!/usr/bin/env python3
"""Train the CodeFellow QLoRA adapter on a 6 GB CUDA GPU."""

from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import time
from collections import Counter
from pathlib import Path

import torch
from datasets import concatenate_datasets, load_dataset
from peft import LoraConfig, prepare_model_for_kbit_training
from transformers import (
    AutoConfig,
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainerCallback,
    set_seed,
)
from trl import DataCollatorForCompletionOnlyLM, SFTConfig, SFTTrainer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-Coder-3B-Instruct")
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-seq-length", type=int, default=672)
    parser.add_argument("--max-steps", type=int, default=-1)
    parser.add_argument("--num-train-epochs", type=float, default=1.0)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--lora-rank", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=4)
    parser.add_argument(
        "--gradient-checkpointing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Trade compute for VRAM; disable only after a representative memory smoke test.",
    )
    parser.add_argument(
        "--torch-compile",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Compile the training graph with TorchInductor after a smoke test on the target GPU.",
    )
    parser.add_argument("--eval-limit", type=int, default=0)
    parser.add_argument("--checkpoint-interval", type=int, default=200)
    parser.add_argument(
        "--stop-after-steps",
        type=int,
        default=0,
        help="Stop cleanly at this global optimizer step while retaining the max-steps LR schedule.",
    )
    parser.add_argument("--save-total-limit", type=int, default=12)
    parser.add_argument("--english-repeat", type=int, default=1)
    parser.add_argument("--resume-from-checkpoint", type=Path)
    parser.add_argument("--max-gpu-temp", type=int, default=84)
    parser.add_argument("--resume-gpu-temp", type=int, default=80)
    parser.add_argument("--seed", type=int, default=2026)
    return parser.parse_args()


def verify_base_and_dataset(args: argparse.Namespace) -> dict:
    """Fail closed on an adapted parent or legacy/non-parallel data."""
    model_text = str(args.model).casefold()
    if any(marker in model_text for marker in ("checkpoint", "merged-sw", "phase2", ".gguf")):
        raise SystemExit(
            "training must start from the original BF16/FP16 parent, not a checkpoint, merged model, or GGUF"
        )
    model_path = Path(args.model)
    if model_path.exists() and (model_path / "adapter_config.json").exists():
        raise SystemExit("the selected parent contains a PEFT adapter")
    config = AutoConfig.from_pretrained(args.model)
    architectures = set(config.architectures or [])
    if "Qwen2ForCausalLM" not in architectures:
        raise SystemExit(f"unexpected parent architecture: {sorted(architectures)}")
    if getattr(config, "num_hidden_layers", None) != 36 or getattr(config, "hidden_size", None) != 2048:
        raise SystemExit("the selected parent is not the expected Qwen2.5-Coder-3B architecture")
    manifest_path = args.train.parent / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"parallel dataset manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "codefellow-parallel-sft-v2":
        raise SystemExit("refusing legacy data: expected codefellow-parallel-sft-v2")
    if manifest.get("target_ratios") != {"en": 0.65, "sw": 0.2, "sw_mix": 0.15}:
        raise SystemExit("dataset does not declare the required 65/20/15 language mix")
    return {
        "requested_model": str(args.model),
        "config_name_or_path": getattr(config, "_name_or_path", None),
        "architectures": sorted(architectures),
        "hidden_size": config.hidden_size,
        "num_hidden_layers": config.num_hidden_layers,
        "dataset_manifest": str(manifest_path),
        "dataset_schema": manifest["schema"],
    }


def rebalance(dataset, seed: int):
    """Restore and block-interleave the exact 65/20/15 language mix."""
    ratios = {"en": 0.65, "sw": 0.20, "sw_mix": 0.15}
    by_language = {
        language: dataset.filter(lambda row, language=language: row["language"] == language)
        for language in ratios
    }
    max_total = min(int(len(by_language[language]) / ratio) for language, ratio in ratios.items())
    target_total = (max_total // 20) * 20
    if target_total <= 0:
        raise RuntimeError("not enough complete rows to restore the 65/20/15 mix")
    selected = []
    offsets = {}
    offset = 0
    for language, ratio in ratios.items():
        count = round(target_total * ratio)
        lane = by_language[language].shuffle(seed=seed).select(range(count))
        offsets[language] = offset
        offset += len(lane)
        selected.append(lane)
    combined = concatenate_datasets(selected)
    counters = {language: 0 for language in ratios}
    indices = []
    rng = random.Random(seed)
    for _ in range(target_total // 20):
        block = ["en"] * 13 + ["sw"] * 4 + ["sw_mix"] * 3
        rng.shuffle(block)
        for language in block:
            indices.append(offsets[language] + counters[language])
            counters[language] += 1
    return combined.select(indices)


class ThermalGuard(TrainerCallback):
    def __init__(self, max_temp: int, resume_temp: int):
        if resume_temp >= max_temp:
            raise ValueError("resume GPU temperature must be lower than maximum temperature")
        self.max_temp = max_temp
        self.resume_temp = resume_temp
        self.nvidia_smi = shutil.which("nvidia-smi")

    def temperature(self) -> int | None:
        if not self.nvidia_smi:
            return None
        try:
            output = subprocess.check_output(
                [self.nvidia_smi, "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                text=True,
                timeout=5,
            )
            return int(output.splitlines()[0].strip())
        except (OSError, subprocess.SubprocessError, ValueError, IndexError):
            return None

    def guard(self, control):
        temperature = self.temperature()
        if temperature is None or temperature < self.max_temp:
            return control
        print(f"GPU reached {temperature} C; cooling to {self.resume_temp} C", flush=True)
        while temperature is not None and temperature > self.resume_temp:
            time.sleep(10)
            temperature = self.temperature()
        print(f"GPU training resumed at {temperature} C", flush=True)
        return control

    def on_substep_end(self, args, state, control, **kwargs):
        return self.guard(control)

    def on_step_end(self, args, state, control, **kwargs):
        return self.guard(control)


class StagedStop(TrainerCallback):
    def __init__(self, stop_after_steps: int):
        self.stop_after_steps = stop_after_steps

    def on_step_end(self, args, state, control, **kwargs):
        if self.stop_after_steps and state.global_step >= self.stop_after_steps:
            control.should_save = True
            control.should_training_stop = True
        return control


def main() -> int:
    args = parse_args()
    if not torch.cuda.is_available():
        raise SystemExit("CUDA is required for this training configuration")
    set_seed(args.seed)
    args.output.mkdir(parents=True, exist_ok=True)
    provenance = verify_base_and_dataset(args)

    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    tokenizer.padding_side = "right"

    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        quantization_config=quantization,
        torch_dtype=torch.float16,
        device_map={"": 0},
        attn_implementation="sdpa",
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(
        model, use_gradient_checkpointing=args.gradient_checkpointing
    )

    dataset = load_dataset("json", data_files={"train": str(args.train), "validation": str(args.validation)})

    def render(row: dict) -> dict:
        text = tokenizer.apply_chat_template(row["messages"], tokenize=False, add_generation_prompt=False)
        return {
            "text": text,
            "token_length": len(tokenizer(text, add_special_tokens=False)["input_ids"]),
        }

    dataset = dataset.map(render)
    retention = {}
    for split in ("train", "validation"):
        before = Counter(dataset[split]["language"])
        dataset[split] = dataset[split].filter(
            lambda row: row["token_length"] <= args.max_seq_length,
            desc=f"Keeping complete {split} examples",
        )
        after = Counter(dataset[split]["language"])
        retention[split] = {
            "before": dict(before),
            "after": dict(after),
            "retained": len(dataset[split]),
        }
        dataset[split] = rebalance(dataset[split], args.seed + (1 if split == "validation" else 0))
        retention[split]["after_ratio_rebalance"] = dict(Counter(dataset[split]["language"]))
        retention[split]["rebalanced"] = len(dataset[split])
    if args.english_repeat != 1:
        raise ValueError("english-repeat must remain 1; the verified dataset already encodes the exact 65/20/15 mix")
    if args.english_repeat > 1:
        english = dataset["train"].filter(
            lambda row: row["language"] == "en",
            desc="Selecting retained English replay",
        )
        dataset["train"] = concatenate_datasets(
            [dataset["train"]] + [english] * (args.english_repeat - 1)
        ).shuffle(seed=args.seed)
        retention["train"]["after_english_repeat"] = dict(
            Counter(dataset["train"]["language"])
        )
        retention["train"]["used"] = len(dataset["train"])
    if args.eval_limit > 0 and len(dataset["validation"]) > args.eval_limit:
        dataset["validation"] = dataset["validation"].select(range(args.eval_limit))
        retention["validation"]["used"] = len(dataset["validation"])
    if not dataset["train"] or not dataset["validation"]:
        raise RuntimeError("length filtering removed an entire dataset split")
    removable = [column for column in dataset["train"].column_names if column != "text"]
    dataset = dataset.remove_columns(removable)
    (args.output / "dataset_retention.json").write_text(
        json.dumps(retention, indent=2), encoding="utf-8"
    )
    print(json.dumps({"dataset_retention": retention}, indent=2))
    response_marker = "<|im_start|>assistant\n"
    if response_marker not in dataset["train"][0]["text"]:
        raise RuntimeError("Qwen assistant marker was not found in the rendered chat template")
    collator = DataCollatorForCompletionOnlyLM(
        response_template=tokenizer.encode(response_marker, add_special_tokens=False),
        tokenizer=tokenizer,
    )
    lora = LoraConfig(
        r=args.lora_rank,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    if args.max_steps == 0 or args.max_steps < -1:
        raise ValueError("max-steps must be -1 for epoch training or a positive integer")
    if args.stop_after_steps < 0 or (
        args.stop_after_steps and args.max_steps > 0 and args.stop_after_steps > args.max_steps
    ):
        raise ValueError("stop-after-steps must be zero or a positive step no greater than max-steps")
    if not (1 <= args.lora_rank <= 64 and 1 <= args.lora_alpha <= 128):
        raise ValueError("LoRA rank/alpha are outside the conservative supported range")
    if not 2e-5 <= args.learning_rate <= 5e-5:
        raise ValueError("learning rate must remain between 2e-5 and 5e-5 for this attempt")
    checkpoint_interval = args.checkpoint_interval
    config = SFTConfig(
        output_dir=str(args.output),
        dataset_text_field="text",
        max_seq_length=args.max_seq_length,
        packing=False,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        gradient_checkpointing=args.gradient_checkpointing,
        max_steps=args.max_steps,
        num_train_epochs=args.num_train_epochs,
        learning_rate=args.learning_rate,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        optim="paged_adamw_8bit",
        fp16=True,
        bf16=False,
        logging_steps=min(5, args.max_steps),
        eval_strategy="steps",
        eval_steps=checkpoint_interval,
        save_strategy="steps",
        save_steps=checkpoint_interval,
        save_total_limit=args.save_total_limit,
        load_best_model_at_end=False,
        report_to="none",
        torch_compile=args.torch_compile,
        torch_compile_backend="inductor" if args.torch_compile else None,
        seed=args.seed,
        data_seed=args.seed,
    )
    trainer = SFTTrainer(
        model=model,
        args=config,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        processing_class=tokenizer,
        peft_config=lora,
        data_collator=collator,
        callbacks=[
            ThermalGuard(args.max_gpu_temp, args.resume_gpu_temp),
            StagedStop(args.stop_after_steps),
        ],
    )
    result = trainer.train(
        resume_from_checkpoint=(
            str(args.resume_from_checkpoint) if args.resume_from_checkpoint else None
        )
    )
    trainer.save_model(str(args.output / "adapter"))
    tokenizer.save_pretrained(str(args.output / "adapter"))
    metrics = dict(result.metrics)
    metrics["peak_gpu_memory_mb"] = round(torch.cuda.max_memory_allocated() / 1024**2, 2)
    metrics["model"] = args.model
    metrics["max_seq_length"] = args.max_seq_length
    metrics["max_steps"] = args.max_steps
    metrics["num_train_epochs"] = args.num_train_epochs
    metrics["lora_rank"] = args.lora_rank
    metrics["lora_alpha"] = args.lora_alpha
    metrics["gradient_accumulation_steps"] = args.gradient_accumulation_steps
    metrics["gradient_checkpointing"] = args.gradient_checkpointing
    metrics["torch_compile"] = args.torch_compile
    metrics["eval_limit"] = args.eval_limit
    metrics["checkpoint_interval"] = args.checkpoint_interval
    metrics["stop_after_steps"] = args.stop_after_steps
    metrics["completed_global_step"] = trainer.state.global_step
    metrics["english_repeat"] = args.english_repeat
    metrics["loss_scope"] = "assistant tokens only"
    metrics["provenance"] = provenance
    metrics["thermal_guard_c"] = {"pause": args.max_gpu_temp, "resume": args.resume_gpu_temp}
    (args.output / "training_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
