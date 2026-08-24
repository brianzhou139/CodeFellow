#!/usr/bin/env python3
"""Fail closed on split leakage, schema errors, or unexpected language lanes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


FENCE_RE = re.compile(r"```(?:python|py|javascript|js)\s*\n(.*?)```", re.I | re.S)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--languages", default="en,sw,sw_mix")
    parser.add_argument("--min-records", type=int, default=0)
    parser.add_argument(
        "--expected-ratios",
        default=None,
        help="Optional exact ratios, for example en=0.65,sw=0.20,sw_mix=0.15.",
    )
    parser.add_argument("--require-parallel-lock", action="store_true")
    parser.add_argument("--require-verified", action="store_true")
    args = parser.parse_args()
    expected = {item.strip() for item in args.languages.split(",") if item.strip()}
    train, validation = read_jsonl(args.train), read_jsonl(args.validation)
    all_rows = train + validation
    if not all_rows:
        raise SystemExit("dataset is empty")
    if len(all_rows) < args.min_records:
        raise SystemExit(f"dataset has {len(all_rows)} records; minimum is {args.min_records}")
    train_sources = {row.get("parallel_id", row["source_id"]) for row in train}
    validation_sources = {row.get("parallel_id", row["source_id"]) for row in validation}
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
        if args.require_verified and row.get("verification", {}).get("passed") is not True:
            raise SystemExit(f"row {index} is not marked locally verified")
        if args.require_verified and row.get("verification", {}).get("translation_anchors_verified") is not True:
            raise SystemExit(f"row {index} lacks semantic-anchor verification")
        if args.require_verified and float(row.get("verification", {}).get("translation_semantic_score", 0)) < 0.40:
            raise SystemExit(f"row {index} failed the translation semantic-score threshold")
        if args.require_verified and row.get("verification", {}).get("explanation_translation_anchors_verified") is not True:
            raise SystemExit(f"row {index} lacks explanation semantic-anchor verification")
        if args.require_verified and float(
            row.get("verification", {}).get("explanation_translation_semantic_score", 0)
        ) < 0.45:
            raise SystemExit(f"row {index} failed the explanation semantic-score threshold")
        accepted_explanation_methods = {
            "project-authored localized curriculum",
            "project-authored Kiswahili frame plus independently round-tripped task translation",
        }
        if args.require_verified and row.get("verification", {}).get(
            "explanation_verification_method"
        ) not in accepted_explanation_methods:
            raise SystemExit(f"row {index} has an unknown explanation verification method")
        if args.require_verified and str(row.get("source", "")).startswith("Muennighoff/mbpp"):
            mutation_total = int(row.get("verification", {}).get("mutation_total", 0))
            mutation_killed = int(row.get("verification", {}).get("mutation_killed", 0))
            if mutation_total < 1 or mutation_killed / mutation_total < 0.50:
                raise SystemExit(f"row {index} failed the mutation-test adequacy gate")

    ratio_report = {}
    if args.expected_ratios:
        expected_ratios = {}
        for item in args.expected_ratios.split(","):
            name, value = item.split("=", 1)
            expected_ratios[name.strip()] = float(value)
        if set(expected_ratios) != expected:
            raise SystemExit("ratio languages do not match --languages")
        if abs(sum(expected_ratios.values()) - 1.0) > 1e-9:
            raise SystemExit("expected ratios must sum to 1")
        counts = Counter(row["language"] for row in all_rows)
        for language, ratio in expected_ratios.items():
            expected_count = round(len(all_rows) * ratio)
            if counts[language] != expected_count:
                raise SystemExit(
                    f"{language} count is {counts[language]}, expected exactly {expected_count}"
                )
            ratio_report[language] = counts[language] / len(all_rows)

    parallel_report = {}
    if args.require_parallel_lock:
        groups: dict[str, list[dict]] = {}
        explanations_by_language = {language: set() for language in expected}
        for row in all_rows:
            parallel_id = row.get("parallel_id")
            if not parallel_id:
                raise SystemExit("parallel lock requested but a row has no parallel_id")
            groups.setdefault(parallel_id, []).append(row)
        for parallel_id, rows in groups.items():
            lanes = {row["language"] for row in rows}
            if lanes != expected:
                raise SystemExit(f"{parallel_id} lacks a complete language triple: {sorted(lanes)}")
            hashes = {row.get("code_sha256") for row in rows}
            if len(hashes) != 1 or None in hashes:
                raise SystemExit(f"{parallel_id} has non-identical declared code hashes")
            declared = next(iter(hashes))
            for row in rows:
                assistant = row["messages"][-1]["content"]
                fences = FENCE_RE.findall(assistant)
                if len(fences) != 1:
                    raise SystemExit(
                        f"{parallel_id}:{row['language']} must contain exactly one closed code fence"
                    )
                actual = hashlib.sha256(fences[0].strip().encode("utf-8")).hexdigest()
                if actual != declared:
                    raise SystemExit(f"{parallel_id}:{row['language']} violates the executable code lock")
                match = FENCE_RE.search(assistant)
                explanation = assistant[match.end():].strip()
                if not explanation:
                    raise SystemExit(f"{parallel_id}:{row['language']} lacks an explanation")
                if re.search(r"\b([\w'-]+)(?:\s+\1){2,}\b", explanation, re.I):
                    raise SystemExit(
                        f"{parallel_id}:{row['language']} contains a repeated-word collapse"
                    )
                explanations_by_language[row["language"]].add(explanation)
        minimum_unique = max(1, round(len(groups) * 0.90))
        unique_explanations = {
            language: len(explanations)
            for language, explanations in explanations_by_language.items()
        }
        for language, count in unique_explanations.items():
            if count < minimum_unique:
                raise SystemExit(
                    f"{language} has only {count} unique explanations; minimum is {minimum_unique}"
                )
        parallel_report = {
            "parallel_tasks": len(groups),
            "all_have_en_sw_sw_mix": True,
            "all_code_hashes_locked": True,
            "unique_explanations": unique_explanations,
            "minimum_unique_explanations": minimum_unique,
            "repeated_word_collapses": 0,
        }
    report = {
        "passed": True,
        "train_records": len(train),
        "validation_records": len(validation),
        "source_overlap": 0,
        "languages": Counter(row["language"] for row in all_rows),
        "kinds": Counter(row["kind"] for row in all_rows),
        "ratios": ratio_report,
        "parallel": parallel_report,
    }
    print(json.dumps(report, indent=2, default=dict))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
