#!/usr/bin/env python3
"""Measure the production translation lane's CPU latency and resident memory."""

from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from translation_backend import CTranslate2NllbTranslator


def current_rss_kib() -> int | None:
    status = Path("/proc/self/status")
    if not status.exists():
        return None
    for line in status.read_text(encoding="utf-8").splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()

    started = time.perf_counter()
    translator = CTranslate2NllbTranslator(str(args.model), threads=args.threads)
    load_seconds = time.perf_counter() - started
    samples = [
        "Tekeleza sum_even(numbers), ambayo inarejesha jumla ya nambari shufwa.",
        "Eleza uchangamano wa muda O(n) na O(n^2) kwa mwanafunzi.",
    ]
    translations = []
    translate_started = time.perf_counter()
    for sample in samples:
        translations.append(translator.translate_requirement(sample)[0])
    translate_seconds = time.perf_counter() - translate_started
    print(
        json.dumps(
            {
                "load_seconds": round(load_seconds, 3),
                "two_translations_seconds": round(translate_seconds, 3),
                "current_rss_mib": (
                    round(current_rss_kib() / 1024, 2) if current_rss_kib() is not None else None
                ),
                "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2),
                "translations": translations,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
