#!/usr/bin/env python3
"""Build an executable, localized HumanEval screen excluded from CodeFellow training."""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path

from datasets import DownloadConfig, load_dataset

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.build_parallel_dataset import (
    CTranslate2Teacher,
    back_translate_many,
    clean_translation,
    preserve_technical_terms,
    semantic_quality,
    translate_many_guarded,
    verify_program,
)


WORD_RE = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
STOP_WORDS = {
    "the", "and", "that", "this", "with", "from", "into", "according", "requirement",
    "python", "preserve", "exact", "name", "argument", "contract", "return",
}
WORD_ALIASES = {
    "write": "implement", "create": "implement", "build": "implement",
    "method": "function", "array": "list", "values": "value", "numbers": "number",
}
CONTRACT_RE = re.compile(
    r"^Implement the Python function (?P<signature>.+?)\. Preserve this exact function name "
    r"and argument contract\. Requirement: (?P<requirement>.*)$"
)
SWAHILI_REQUIREMENT_RE = re.compile(r"\b(?:Mahitaji|Sharti|Hitaji)\s*:\s*", re.IGNORECASE)


def normalized_words(text: str) -> set[str]:
    normalized = set()
    for raw_word in WORD_RE.findall(text):
        word = raw_word.casefold()
        if word.endswith("s") and len(word) > 4:
            word = word[:-1]
        word = WORD_ALIASES.get(word, word)
        if word not in STOP_WORDS:
            normalized.add(word)
    return normalized


def close_paraphrase(left: str, right: str) -> bool:
    left_words = normalized_words(left)
    right_words = normalized_words(right)
    union = left_words | right_words
    jaccard = len(left_words & right_words) / len(union) if union else 1.0
    compact_left = " ".join(sorted(left_words))
    compact_right = " ".join(sorted(right_words))
    sequence = SequenceMatcher(None, compact_left, compact_right).ratio()
    return jaccard >= 0.70 or sequence >= 0.86


def training_prompts(path: Path) -> list[str]:
    prompts: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        source_id = record.get("source_id") or record.get("parallel_id")
        messages = record.get("messages", [])
        if source_id and len(messages) >= 2:
            prompts.setdefault(source_id, messages[1]["content"])
    return list(prompts.values())


def function_contract(row: dict) -> tuple[str, str, str]:
    tree = ast.parse(row["prompt"])
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef))
    contract = ast.get_docstring(function, clean=True)
    if not contract:
        raise ValueError("missing docstring contract")
    for argument in function.args.posonlyargs + function.args.args + function.args.kwonlyargs:
        argument.annotation = None
    if function.args.vararg:
        function.args.vararg.annotation = None
    if function.args.kwarg:
        function.args.kwarg.annotation = None
    signature = f"{row['entry_point']}({ast.unparse(function.args)})"
    compact_contract = re.sub(r"\s+", " ", contract).strip()
    requirement = (
        f"Implement the Python function {signature}. Preserve this exact function name and argument "
        f"contract. Requirement: {compact_contract}"
    )
    reference = f"{row['prompt'].rstrip()}\n{row['canonical_solution'].rstrip()}"
    tests = f"{row['test'].rstrip()}\ncheck({row['entry_point']})"
    return requirement, reference, tests


def lock_localized_contract(prompt_en: str, prompt_sw: str) -> str:
    """Restore the exact executable signature after prose-only translation."""
    match = CONTRACT_RE.match(prompt_en)
    if not match:
        raise ValueError("English prompt does not contain the expected function contract")
    translated_parts = SWAHILI_REQUIREMENT_RE.split(prompt_sw, maxsplit=1)
    translated_requirement = translated_parts[-1].strip()
    return (
        f"Tekeleza Python function {match.group('signature')}. Hifadhi function name na argument "
        f"contract hizi bila kubadilisha. Mahitaji: {translated_requirement}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--training-jsonl", type=Path, required=True)
    parser.add_argument("--ct2-model", type=Path, required=True)
    parser.add_argument("--translation-cache", type=Path, required=True)
    parser.add_argument("--roundtrip-cache", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--translation-threads", type=int, default=4)
    args = parser.parse_args()

    if args.limit < 1:
        raise SystemExit("--limit must be positive")
    seen_training = training_prompts(args.training_jsonl)
    rows = load_dataset(
        "openai/openai_humaneval",
        split="test",
        download_config=DownloadConfig(local_files_only=True),
    )
    verified: list[tuple[dict, str, str]] = []
    rejected_near_training = 0
    rejected_execution = 0
    for row in rows:
        try:
            requirement, reference, tests = function_contract(row)
            if any(close_paraphrase(requirement, prompt) for prompt in seen_training):
                rejected_near_training += 1
                continue
            verify_program("python", reference, tests)
        except (StopIteration, SyntaxError, ValueError, RuntimeError, subprocess.TimeoutExpired):
            rejected_execution += 1
            continue
        verified.append((dict(row), requirement, tests))

    translator = CTranslate2Teacher(args.ct2_model, args.translation_cache, args.translation_threads)
    english = [item[1] for item in verified]
    swahili = [
        preserve_technical_terms(source, clean_translation(target))
        for source, target in zip(english, translate_many_guarded(translator, english))
    ]
    roundtrips = back_translate_many(translator, swahili, args.roundtrip_cache)
    accepted = []
    rejected_translation = 0
    for (row, prompt_en, tests), prompt_sw, roundtrip in zip(verified, swahili, roundtrips):
        score, anchors = semantic_quality(prompt_en, roundtrip)
        if score < 0.40 or not anchors:
            rejected_translation += 1
            continue
        accepted.append((row, prompt_en, lock_localized_contract(prompt_en, prompt_sw), tests, score))
    accepted.sort(key=lambda item: (-item[4], item[0]["task_id"]))
    accepted = accepted[: args.limit]
    if len(accepted) < args.limit:
        raise RuntimeError(f"only {len(accepted)} independent translated tasks passed; need {args.limit}")

    tasks = []
    for row, prompt_en, prompt_sw, tests, score in accepted:
        tasks.append(
            {
                "id": "he_" + row["task_id"].replace("/", "_"),
                "source": "openai/openai_humaneval",
                "source_task_id": row["task_id"],
                "category": "independent_implementation",
                "kind": "code",
                "runtime": "python",
                "prompt_en": prompt_en,
                "prompt_sw": prompt_sw,
                "tests": [tests],
                "translation_semantic_score": round(score, 4),
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(tasks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema": "codefellow-independent-screen-v1",
        "tasks": len(tasks),
        "source": "openai/openai_humaneval (MIT)",
        "training_source_overlap": 0,
        "deduplication": "token Jaccard < 0.70 and normalized sequence similarity < 0.86 against every unique v14 training prompt",
        "reference_verification": "canonical solution executed against upstream HumanEval check() before inclusion",
        "translation": "local NLLB CTranslate2 INT8 prose teacher; exact public signature restored; round-trip semantic and anchor gate",
        "rejected_near_training": rejected_near_training,
        "rejected_execution": rejected_execution,
        "rejected_translation": rejected_translation,
        "minimum_translation_semantic_score": min(task["translation_semantic_score"] for task in tasks),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
