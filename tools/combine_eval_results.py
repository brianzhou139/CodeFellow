#!/usr/bin/env python3
"""Combine checkpointed language runs and later audited task overrides."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALUATOR = ROOT / "evals" / "kiswahili" / "run_eval.py"


def load_summarizer():
    spec = importlib.util.spec_from_file_location("codefellow_evaluator", EVALUATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load evaluator: {EVALUATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.summarize


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", type=Path, required=True)
    parser.add_argument("--override", action="append", type=Path, default=[])
    parser.add_argument("--tasks", type=Path, default=ROOT / "evals" / "kiswahili" / "tasks.json")
    parser.add_argument("--languages", default="en,sw,sw_mix")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    languages = [language.strip() for language in args.languages.split(",") if language.strip()]
    sources = [*args.input, *args.override]
    documents = [json.loads(path.read_text(encoding="utf-8")) for path in sources]
    rows: dict[tuple[str, str], dict] = {}
    provenance: dict[str, str] = {}
    for path, document in zip(sources, documents):
        for row in document.get("results", []):
            key = (row["task_id"], row["language"])
            rows[key] = row
            provenance[f"{key[0]}:{key[1]}"] = str(path)

    tasks = json.loads(args.tasks.read_text(encoding="utf-8"))
    order = {task["id"]: index for index, task in enumerate(tasks)}
    language_order = {language: index for index, language in enumerate(languages)}
    selected = [
        row
        for (task_id, language), row in rows.items()
        if task_id in order and language in language_order
    ]
    selected.sort(key=lambda row: (order[row["task_id"]], language_order[row["language"]]))
    summarize = load_summarizer()
    document = {
        "schema": "codefellow-final-paired-eval-v1",
        "model": documents[0].get("model"),
        "languages": languages,
        "task_count": len(tasks),
        "application_contract": True,
        "translation_runtime": "ctranslate2-int8",
        "results": selected,
        "provenance": provenance,
    }
    document["summary"] = summarize(tasks, selected, languages)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(document["summary"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
