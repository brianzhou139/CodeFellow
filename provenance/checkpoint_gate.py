#!/usr/bin/env python3
"""Gate an unquantized merged checkpoint using raw llama.cpp responses only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def paired(document: dict, language: str, metric: str) -> float:
    return float(document["summary"]["languages"][language][metric])


def repair_rate(document: dict, metric: str) -> float:
    summary = document["summary"]
    return float(summary[metric]) / float(summary["total"])


def direct_model_only(document: dict) -> bool:
    return (
        document.get("model_only") is True
        and document.get("application_prompt_strategy") == "direct"
        and not document.get("application_contract", False)
        and not document.get("self_review", False)
        and not document.get("translate_then_solve", False)
        and not document.get("nllb_model")
        and not document.get("nllb_roundtrip_explanations", False)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-paired", type=Path, required=True)
    parser.add_argument("--candidate-paired", type=Path, required=True)
    parser.add_argument("--base-repairs", type=Path, required=True)
    parser.add_argument("--candidate-repairs", type=Path, required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--strength", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    base_paired = load(args.base_paired)
    candidate_paired = load(args.candidate_paired)
    base_repairs = load(args.base_repairs)
    candidate_repairs = load(args.candidate_repairs)
    metrics = {
        "base_en": paired(base_paired, "en", "overall_pass_rate"),
        "candidate_en": paired(candidate_paired, "en", "overall_pass_rate"),
        "base_en_code": paired(base_paired, "en", "code_pass_rate"),
        "candidate_en_code": paired(candidate_paired, "en", "code_pass_rate"),
        "base_sw": paired(base_paired, "sw", "overall_pass_rate"),
        "candidate_sw": paired(candidate_paired, "sw", "overall_pass_rate"),
        "base_sw_mix": paired(base_paired, "sw_mix", "overall_pass_rate"),
        "candidate_sw_mix": paired(candidate_paired, "sw_mix", "overall_pass_rate"),
        "minimum_candidate_format": min(
            paired(candidate_paired, language, "format_compliance_rate")
            for language in ("en", "sw", "sw_mix")
        ),
        "base_repair_pass_at_1": repair_rate(base_repairs, "pass_at_1"),
        "candidate_repair_pass_at_1": repair_rate(candidate_repairs, "pass_at_1"),
        "base_repair_pass_at_2": repair_rate(base_repairs, "pass_at_2"),
        "candidate_repair_pass_at_2": repair_rate(candidate_repairs, "pass_at_2"),
    }
    checks = {
        "raw_model_only_evaluation": direct_model_only(candidate_paired),
        "english_overall_not_below_base": metrics["candidate_en"] >= metrics["base_en"],
        "english_executable_code_not_below_base": metrics["candidate_en_code"] >= metrics["base_en_code"],
        "kiswahili_at_least_75_percent": metrics["candidate_sw"] >= 0.75,
        "kiswahili_gain_at_least_10_points": metrics["candidate_sw"] >= metrics["base_sw"] + 0.10,
        "code_switching_at_least_85_percent": metrics["candidate_sw_mix"] >= 0.85,
        "code_switching_gain_at_least_15_points": metrics["candidate_sw_mix"] >= metrics["base_sw_mix"] + 0.15,
        "format_compliance_at_least_98_percent": metrics["minimum_candidate_format"] >= 0.98,
        "repair_pass_at_1_not_below_base": metrics["candidate_repair_pass_at_1"] >= metrics["base_repair_pass_at_1"],
        "repair_pass_at_2_not_below_base": metrics["candidate_repair_pass_at_2"] >= metrics["base_repair_pass_at_2"],
    }
    document = {
        "schema": "codefellow-checkpoint-gate-v2",
        "checkpoint": args.checkpoint,
        "adapter_strength": args.strength,
        "passed": all(checks.values()),
        "checks": checks,
        "metrics": metrics,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(document, indent=2))
    return 0 if document["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
