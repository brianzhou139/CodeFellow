#!/usr/bin/env python3
"""Create a balanced code/Kiswahili calibration corpus from SFT records."""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-records", type=int, default=800)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    records = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    rng = random.Random(args.seed)
    by_language = defaultdict(list)
    for record in records:
        by_language[record["language"]].append(record)
    for lane in by_language.values():
        rng.shuffle(lane)
    languages = sorted(by_language)
    quota = args.max_records // len(languages)
    selected = []
    leftovers = []
    for language in languages:
        selected.extend(by_language[language][:quota])
        leftovers.extend(by_language[language][quota:])
    rng.shuffle(leftovers)
    selected.extend(leftovers[: max(0, args.max_records - len(selected))])
    rng.shuffle(selected)
    chunks = []
    for record in selected:
        for message in record["messages"]:
            chunks.append(f"{message['role'].upper()}:\n{message['content'].strip()}")
        chunks.append("END\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n\n".join(chunks), encoding="utf-8")
    counts = Counter(record["language"] for record in selected)
    print(f"wrote {len(selected)} balanced records to {args.output}: {dict(counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
