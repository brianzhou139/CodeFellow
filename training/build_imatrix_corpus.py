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
    parser.add_argument(
        "--ratios",
        default="en=0.50,sw=0.25,sw_mix=0.25",
        help="Calibration mix; defaults to English code plus equal pure/mixed Kiswahili coverage.",
    )
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument(
        "--min-debug-ratio",
        type=float,
        default=0.15,
        help="Minimum debugging share requested inside each language lane when enough records exist.",
    )
    parser.add_argument(
        "--supplement",
        type=Path,
        help="Optional authored calibration text containing tests and strict-format examples.",
    )
    args = parser.parse_args()
    if not 0.0 <= args.min_debug_ratio <= 1.0:
        raise SystemExit("--min-debug-ratio must be between 0 and 1")

    records = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    rng = random.Random(args.seed)
    by_language = defaultdict(list)
    for record in records:
        by_language[record["language"]].append(record)
    ratios = {}
    for item in args.ratios.split(","):
        language, value = item.split("=", 1)
        ratios[language.strip()] = float(value)
    languages = sorted(by_language)
    if set(ratios) != set(languages) or abs(sum(ratios.values()) - 1.0) > 1e-9:
        raise SystemExit("--ratios must name every input language exactly and sum to 1")
    selected = []
    leftovers = []
    for language in languages:
        quota = round(args.max_records * ratios[language])
        debugging = [record for record in by_language[language] if record.get("kind") == "debugging"]
        other = [record for record in by_language[language] if record.get("kind") != "debugging"]
        rng.shuffle(debugging)
        rng.shuffle(other)
        debug_quota = min(round(quota * args.min_debug_ratio), len(debugging))
        lane_selected = debugging[:debug_quota]
        lane_selected.extend(other[: max(0, quota - len(lane_selected))])
        if len(lane_selected) < quota:
            lane_selected.extend(debugging[debug_quota : debug_quota + quota - len(lane_selected)])
        selected.extend(lane_selected)
        selected_ids = {id(record) for record in lane_selected}
        leftovers.extend(record for record in by_language[language] if id(record) not in selected_ids)
    rng.shuffle(leftovers)
    selected.extend(leftovers[: max(0, args.max_records - len(selected))])
    rng.shuffle(selected)
    chunks = []
    for record in selected:
        for message in record["messages"]:
            chunks.append(f"{message['role'].upper()}:\n{message['content'].strip()}")
        chunks.append("END\n")
    if args.supplement:
        chunks.append("CALIBRATION SUPPLEMENT:\n" + args.supplement.read_text(encoding="utf-8").strip())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n\n".join(chunks), encoding="utf-8")
    counts = Counter(record["language"] for record in selected)
    kinds = Counter(record.get("kind", "unknown") for record in selected)
    print(
        f"wrote {len(selected)} balanced records to {args.output}: "
        f"languages={dict(counts)}, kinds={dict(kinds)}, supplement={bool(args.supplement)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
