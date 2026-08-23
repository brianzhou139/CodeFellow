#!/usr/bin/env python3
"""Fail closed on split leakage, schema errors, or unexpected language lanes."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--languages", default="en,sw,sw_mix")
    args = parser.parse_args()
    expected = {item.strip() for item in args.languages.split(",") if item.strip()}
    train, validation = read_jsonl(args.train), read_jsonl(args.validation)
    all_rows = train + validation
    if not all_rows:
        raise SystemExit("dataset is empty")
    train_sources = {row["source_id"] for row in train}
    validation_sources = {row["source_id"] for row in validation}
    overlap = train_sources & validation_sources
    if overlap:
        raise SystemExit(f"source-level split leakage: {sorted(overlap)[:5]}")
    actual = {row.get("language") for row in all_rows}
    if actual != expected:
        raise SystemExit(f"language lanes are {sorted(actual)}, expected {sorted(expected)}")
    for index, row in enumerate(all_rows):
        messages = row.get("messages")
        roles = [message.get("role") for message in messages] if isinstance(messages, list) else []
        if roles not in (["user", "assistant"], ["system", "user", "assistant"]):
            raise SystemExit(f"row {index} has invalid message roles")
        if not all(isinstance(message.get("content"), str) and message["content"].strip() for message in messages):
            raise SystemExit(f"row {index} contains empty content")
    report = {
        "passed": True,
        "train_records": len(train),
        "validation_records": len(validation),
        "source_overlap": 0,
        "languages": Counter(row["language"] for row in all_rows),
        "kinds": Counter(row["kind"] for row in all_rows),
    }
    print(json.dumps(report, indent=2, default=dict))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
