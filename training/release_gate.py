#!/usr/bin/env python3
"""Reject an adapted GGUF unless it beats the base without losing its advantages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-paired", type=Path, required=True)
    parser.add_argument("--candidate-paired", type=Path, required=True)
    parser.add_argument("--base-repairs", type=Path, required=True)
    parser.add_argument("--candidate-repairs", type=Path, required=True)
    parser.add_argument("--base-profiler", type=Path, required=True)
    parser.add_argument("--candidate-profiler", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def paired(document: dict, language: str, metric: str) -> float:
    return float(document["summary"]["languages"][language][metric])


def repair_rate(document: dict, metric: str) -> float:
    summary = document["summary"]
    return float(summary[metric]) / float(summary["total"])


def main() -> int:
    args = parse_args()
    base_paired, candidate_paired = load(args.base_paired), load(args.candidate_paired)
    base_repairs, candidate_repairs = load(args.base_repairs), load(args.candidate_repairs)
    base_profiler, candidate_profiler = load(args.base_profiler), load(args.candidate_profiler)

    metrics = {
        "base_en": paired(base_paired, "en", "overall_pass_rate"),
        "candidate_en": paired(candidate_paired, "en", "overall_pass_rate"),
        "base_sw": paired(base_paired, "sw", "overall_pass_rate"),
        "candidate_sw": paired(candidate_paired, "sw", "overall_pass_rate"),
        "base_sw_mix": paired(base_paired, "sw_mix", "overall_pass_rate"),
        "candidate_sw_mix": paired(candidate_paired, "sw_mix", "overall_pass_rate"),
        "candidate_en_format": paired(candidate_paired, "en", "format_compliance_rate"),
        "candidate_sw_format": paired(candidate_paired, "sw", "format_compliance_rate"),
        "candidate_sw_mix_format": paired(candidate_paired, "sw_mix", "format_compliance_rate"),
        "candidate_sw_language_adherence": paired(candidate_paired, "sw", "language_adherence_rate"),
        "candidate_sw_mix_language_adherence": paired(
            candidate_paired, "sw_mix", "language_adherence_rate"
        ),
        "base_repair_pass_at_1": repair_rate(base_repairs, "pass_at_1"),
        "candidate_repair_pass_at_1": repair_rate(candidate_repairs, "pass_at_1"),
        "base_repair_pass_at_2": repair_rate(base_repairs, "pass_at_2"),
        "candidate_repair_pass_at_2": repair_rate(candidate_repairs, "pass_at_2"),
        "base_tps": float(base_profiler["throughput"]["tokens_per_second_generation"]),
        "candidate_tps": float(candidate_profiler["throughput"]["tokens_per_second_generation"]),
        "base_peak_rss_mb": float(base_profiler["memory"]["peak_rss_mb"]),
        "candidate_peak_rss_mb": float(candidate_profiler["memory"]["peak_rss_mb"]),
    }
    checks = {
        "kiswahili_at_least_75_percent": metrics["candidate_sw"] >= 0.75,
        "kiswahili_gain_at_least_10_points": metrics["candidate_sw"] - metrics["base_sw"] >= 0.10,
        "kiswahili_code_switching_at_least_85_percent": metrics["candidate_sw_mix"] >= 0.85,
        "kiswahili_code_switching_gain_at_least_15_points": (
            metrics["candidate_sw_mix"] - metrics["base_sw_mix"] >= 0.15
        ),
        "english_at_least_88_percent": metrics["candidate_en"] >= 0.88,
        "english_loss_at_most_2_points": metrics["candidate_en"] >= metrics["base_en"] - 0.02,
        "all_language_formats_at_least_95_percent": min(
            metrics["candidate_en_format"],
            metrics["candidate_sw_format"],
            metrics["candidate_sw_mix_format"],
        )
        >= 0.95,
        "kiswahili_language_adherence_at_least_80_percent": (
            metrics["candidate_sw_language_adherence"] >= 0.80
        ),
        "code_switch_language_adherence_at_least_80_percent": (
            metrics["candidate_sw_mix_language_adherence"] >= 0.80
        ),
        "repair_pass_at_1_not_lower": metrics["candidate_repair_pass_at_1"] >= metrics["base_repair_pass_at_1"],
        "repair_pass_at_2_not_lower": metrics["candidate_repair_pass_at_2"] >= metrics["base_repair_pass_at_2"],
        "throughput_within_3_percent": metrics["candidate_tps"] >= metrics["base_tps"] * 0.97,
        "peak_ram_within_128_mb": metrics["candidate_peak_rss_mb"] <= metrics["base_peak_rss_mb"] + 128,
        "peak_ram_below_7_gb": metrics["candidate_peak_rss_mb"] < 7168,
    }
    document = {"passed": all(checks.values()), "checks": checks, "metrics": metrics}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(document, indent=2))
    return 0 if document["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
