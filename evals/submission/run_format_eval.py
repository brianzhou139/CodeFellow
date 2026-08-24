#!/usr/bin/env python3
"""Run 50 deterministic raw-model formatting and instruction-following probes."""

from __future__ import annotations

import argparse
import json
import re
import statistics
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


SYSTEM_PROMPT = """You are CodeFellow, an offline programming tutor. Follow the user's output
contract exactly. Preserve code, identifiers, literals, punctuation, and requested language."""
FENCE_RE = re.compile(r"\A```python\n(?P<code>.*?)\n```\s*\Z", re.DOTALL)
LANGUAGES = ("en", "sw", "sw_mix")


def format_tasks() -> list[dict]:
    tasks: list[dict] = []
    for number in range(1, 21):
        language = LANGUAGES[(number - 1) % len(LANGUAGES)]
        code = f"def format_probe_{number:02d}(value):\n    return value + {number}"
        if language == "en":
            instruction = "Copy the code below unchanged. Return exactly one closed python Markdown code fence and nothing else."
        elif language == "sw":
            instruction = "Nakili msimbo ulio hapa chini bila kuubadilisha. Toa code fence moja tu ya python iliyofungwa, bila maelezo mengine."
        else:
            instruction = "Copy code iliyo hapa chini exactly. Return closed python code fence moja tu, bila extra prose."
        tasks.append(
            {
                "id": f"format_fence_{number:02d}",
                "language": language,
                "contract": "exact_fence",
                "prompt": f"{instruction}\n\n{code}",
                "expected": code,
            }
        )
    for number in range(21, 36):
        language = LANGUAGES[(number - 1) % len(LANGUAGES)]
        expected = {"task": f"format_probe_{number:02d}", "status": "ready", "offline": True}
        rendered = json.dumps(expected, separators=(",", ":"))
        if language == "en":
            instruction = "Return the JSON object below only. Use no Markdown fence, heading, or explanation, and preserve all keys and values."
        elif language == "sw":
            instruction = "Rudisha JSON object iliyo hapa chini pekee. Usitumie Markdown fence, kichwa, au maelezo; hifadhi keys na values zote."
        else:
            instruction = "Return JSON object hii only. No Markdown fence, heading, or explanation; preserve every key na value."
        tasks.append(
            {
                "id": f"format_json_{number:02d}",
                "language": language,
                "contract": "exact_json",
                "prompt": f"{instruction}\n\n{rendered}",
                "expected": expected,
            }
        )
    for number in range(36, 51):
        language = LANGUAGES[(number - 1) % len(LANGUAGES)]
        expected = [
            f"- function: format_probe_{number:02d}",
            "- runtime: python",
            "- network: disabled",
        ]
        if language == "en":
            instruction = "Return exactly the following three Markdown bullet lines in this order. Add no heading, fence, or other prose."
        elif language == "sw":
            instruction = "Rudisha mistari hii mitatu tu ya Markdown kwa mpangilio huu. Usiongeze kichwa, fence, au maelezo mengine."
        else:
            instruction = "Return exactly bullet lines hizi tatu in this order. No heading, fence, au extra prose."
        tasks.append(
            {
                "id": f"format_bullets_{number:02d}",
                "language": language,
                "contract": "exact_bullets",
                "prompt": instruction + "\n\n" + "\n".join(expected),
                "expected": expected,
            }
        )
    return tasks


def grade(task: dict, response: str) -> tuple[bool, str]:
    stripped = response.strip()
    if task["contract"] == "exact_fence":
        match = FENCE_RE.fullmatch(stripped)
        if not match:
            return False, "response is not exactly one closed python fence"
        if match.group("code") != task["expected"]:
            return False, "code changed while copying"
        try:
            compile(match.group("code"), "<format-probe>", "exec")
        except SyntaxError:
            return False, "copied code does not compile"
        return True, "passed"
    if task["contract"] == "exact_json":
        if "```" in stripped:
            return False, "JSON was wrapped in Markdown"
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return False, "invalid JSON"
        if parsed != task["expected"] or list(parsed) != list(task["expected"]):
            return False, "JSON keys or values changed"
        return True, "passed"
    lines = stripped.splitlines()
    if lines != task["expected"]:
        return False, "bullet lines, ordering, or extra prose differ"
    return True, "passed"


def request(endpoint: str, model: str, task: dict, chat_template_kwargs: dict | None = None) -> dict:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task["prompt"]},
        ],
        "temperature": 0.0,
        "seed": 42,
        "max_tokens": 160,
        "stream": False,
        "cache_prompt": True,
    }
    if chat_template_kwargs is not None:
        payload["chat_template_kwargs"] = chat_template_kwargs
    started = time.perf_counter()
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = urllib.request.Request(
        endpoint, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(http_request, timeout=300) as http_response:
        document = json.loads(http_response.read().decode("utf-8"))
    elapsed = time.perf_counter() - started
    choice = document["choices"][0]
    response = choice["message"]["content"]
    passed, reason = grade(task, response)
    usage = document.get("usage") or {}
    return {
        **task,
        "response": response,
        "passed": passed,
        "reason": reason,
        "finish_reason": choice.get("finish_reason"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "inference_seconds": round(elapsed, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8181/v1/chat/completions")
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--chat-template-kwargs", type=json.loads, default=None)
    args = parser.parse_args()
    tasks = format_tasks()[: args.limit]
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                request, args.endpoint, args.model, task, args.chat_template_kwargs
            ): task
            for task in tasks
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            results.append(result)
            print(f"[{completed:02d}/{len(tasks)}] {result['id']} {'PASS' if result['passed'] else 'FAIL'}", flush=True)
    order = {task["id"]: index for index, task in enumerate(tasks)}
    results.sort(key=lambda result: order[result["id"]])
    durations = [result["inference_seconds"] for result in results]
    summary = {
        "total": len(results),
        "passed": sum(result["passed"] for result in results),
        "compliance_rate": round(sum(result["passed"] for result in results) / len(results), 4),
        "median_inference_seconds": round(statistics.median(durations), 3),
        "by_contract": {},
        "by_language": {},
    }
    for field, key in (("contract", "by_contract"), ("language", "by_language")):
        for value in sorted({result[field] for result in results}):
            rows = [result for result in results if result[field] == value]
            summary[key][value] = {
                "passed": sum(result["passed"] for result in rows),
                "total": len(rows),
                "rate": round(sum(result["passed"] for result in rows) / len(rows), 4),
            }
    document = {
        "schema": "codefellow-format-screen-v1",
        "model": args.model,
        "model_only": True,
        "temperature": 0.0,
        "chat_template_kwargs": args.chat_template_kwargs,
        "results": results,
        "summary": summary,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
