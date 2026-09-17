#!/usr/bin/env python3
"""Merge a CodeFellow LoRA adapter into the high-precision Qwen parent."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


LAYER_PATTERN = re.compile(r"(?:^|\.)layers\.(\d+)(?:\.|$)")


def scale_loaded_adapter(
    model,
    strength: float,
    *,
    layer_min: int | None = None,
    layer_max: int | None = None,
) -> tuple[int, int]:
    """Scale selected PEFT deltas and zero every unselected LoRA module."""
    if not 0.0 < strength <= 1.0:
        raise ValueError("adapter strength must be greater than zero and at most one")
    if (layer_min is None) != (layer_max is None):
        raise ValueError("layer-min and layer-max must be provided together")
    if layer_min is not None and (layer_min < 0 or layer_max < layer_min):
        raise ValueError("invalid layer range")
    selected = 0
    total = 0
    for module_name, module in model.named_modules():
        scaling = getattr(module, "scaling", None)
        if not isinstance(scaling, dict):
            continue
        match = LAYER_PATTERN.search(module_name)
        layer_index = int(match.group(1)) if match else None
        keep = layer_min is None or (
            layer_index is not None and layer_min <= layer_index <= layer_max
        )
        for adapter_name in list(scaling):
            total += 1
            if keep:
                scaling[adapter_name] *= strength
                selected += 1
            else:
                scaling[adapter_name] = 0.0
    if total == 0:
        raise RuntimeError("no LoRA scaling entries were found in the loaded adapter")
    if selected == 0:
        raise RuntimeError("the requested layer range selected no LoRA modules")
    return selected, total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-Coder-3B-Instruct")
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--strength",
        type=float,
        choices=(0.25, 0.35, 0.45, 0.5, 0.75, 1.0),
        default=1.0,
    )
    parser.add_argument("--layer-min", type=int)
    parser.add_argument("--layer-max", type=int)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=torch.float16,
        device_map="cpu",
        low_cpu_mem_usage=True,
    )
    peft_model = PeftModel.from_pretrained(model, str(args.adapter))
    selected_modules, total_modules = scale_loaded_adapter(
        peft_model,
        args.strength,
        layer_min=args.layer_min,
        layer_max=args.layer_max,
    )
    merged = peft_model.merge_and_unload()
    merged.save_pretrained(args.output, safe_serialization=True, max_shard_size="4GB")
    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    tokenizer.save_pretrained(args.output)
    (args.output / "codefellow_merge.json").write_text(
        json.dumps(
            {
                "base_model": str(args.model),
                "adapter": str(args.adapter.resolve()),
                "adapter_strength": args.strength,
                "selected_layer_min": args.layer_min,
                "selected_layer_max": args.layer_max,
                "selected_lora_modules": selected_modules,
                "total_lora_modules": total_modules,
                "precision": "float16",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
