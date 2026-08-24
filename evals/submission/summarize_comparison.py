#!/usr/bin/env python3
"""Summarize matched raw-model screens and ADTC profiler telemetry."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


LANGUAGES = ("en", "sw", "sw_mix")
API_ERROR_MARKERS = ("ModuleNotFoundError", "ImportError", "AttributeError", "NameError")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def estimated_score(accuracy: float, tps: float, peak_rss_mb: float) -> dict[str, float]:
    performance = min(tps / 15.0, 1.0) * 100.0
    peak_gb = peak_rss_mb / 1024.0
    efficiency = max(0.0, (7.0 - peak_gb) / 7.0) * 100.0
    total = 0.50 * accuracy + 0.30 * performance + 0.20 * efficiency
    return {
        "accuracy_component": round(accuracy, 2),
        "performance_component": round(performance, 2),
        "efficiency_component": round(efficiency, 2),
        "estimated_total": round(total, 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--labels", required=True, help="Comma-separated model labels")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    models = []
    for label in [item.strip() for item in args.labels.split(",") if item.strip()]:
        language_documents = {language: load(args.results / f"{label}-{language}.json") for language in LANGUAGES}
        format_document = load(args.results / f"{label}-format.json")
        metrics: dict[str, object] = {"label": label}
        for language, document in language_documents.items():
            lane = document["summary"]["languages"][language]
            metrics[f"{language}_code_pass_rate"] = float(lane["code_pass_rate"])
            metrics[f"{language}_format_rate"] = float(lane["format_compliance_rate"])
            metrics[f"{language}_language_adherence"] = float(lane["language_adherence_rate"])
        metrics["explicit_format_rate"] = float(format_document["summary"]["compliance_rate"])
        all_rows = [row for document in language_documents.values() for row in document["results"]]
        api_failures = sum(
            any(marker in (row.get("grade", {}).get("stderr") or "") for marker in API_ERROR_MARKERS)
            for row in all_rows
        )
        metrics["hallucinated_api_rate"] = round(api_failures / len(all_rows), 4)
        profiler_paths = sorted(args.results.glob(f"{label}-profiler-*.json"))
        if profiler_paths:
            profiler_documents = [load(path) for path in profiler_paths]
            tps_values = [float(document["throughput"]["tokens_per_second_generation"]) for document in profiler_documents]
            rss_values = [float(document["memory"]["peak_rss_mb"]) for document in profiler_documents]
            metrics["profiler_runs"] = len(profiler_documents)
            metrics["median_tps"] = round(statistics.median(tps_values), 2)
            metrics["highest_peak_rss_mb"] = round(max(rss_values), 2)
        else:
            metrics["profiler_runs"] = 0
            metrics["median_tps"] = None
            metrics["highest_peak_rss_mb"] = None

        accuracy = 100.0 * (
            0.30 * float(metrics["en_code_pass_rate"])
            + 0.25 * float(metrics["sw_code_pass_rate"])
            + 0.25 * float(metrics["sw_mix_code_pass_rate"])
            + 0.20 * float(metrics["explicit_format_rate"])
        )
        metrics["estimated_accuracy"] = round(accuracy, 2)
        if metrics["median_tps"] is not None and metrics["highest_peak_rss_mb"] is not None:
            metrics["estimated_adtc"] = estimated_score(
                accuracy, float(metrics["median_tps"]), float(metrics["highest_peak_rss_mb"])
            )
        models.append(metrics)

    ranked = sorted(
        models,
        key=lambda model: (
            (model.get("estimated_adtc") or {}).get("estimated_total", model["estimated_accuracy"]),
            model["estimated_accuracy"],
        ),
        reverse=True,
    )
    document = {
        "schema": "codefellow-q4-comparison-v1",
        "accuracy_estimate_weights": {"en_code": 0.30, "sw_code": 0.25, "sw_mix_code": 0.25, "format": 0.20},
        "adtc_formula": "0.50*accuracy + 0.30*min(TPS/15,1)*100 + 0.20*max(0,(7GB-peakRSS)/7GB)*100",
        "models": models,
        "ranking": [model["label"] for model in ranked],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(document, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
