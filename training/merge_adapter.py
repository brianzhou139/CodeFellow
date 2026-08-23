#!/usr/bin/env python3
"""Merge a CodeFellow LoRA adapter into the high-precision Qwen parent."""

from __future__ import annotations

import argparse
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-Coder-3B-Instruct")
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=torch.float16,
        device_map="cpu",
        low_cpu_mem_usage=True,
    )
    merged = PeftModel.from_pretrained(model, str(args.adapter)).merge_and_unload()
    merged.save_pretrained(args.output, safe_serialization=True, max_shard_size="4GB")
    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    tokenizer.save_pretrained(args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
