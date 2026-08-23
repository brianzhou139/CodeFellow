#!/usr/bin/env python3
"""Run CodeFellow on 30 constrained repairs and execute the proposed code safely."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import resource
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import codefellow  # noqa: E402
from cases import CASES  # noqa: E402

EXECUTION_TIMEOUT_SECONDS = 5
MAX_OUTPUT_CHARS = 4000
PYTHON_BANNED_CALLS = {
    "__import__", "breakpoint", "compile", "eval", "exec", "getattr", "globals",
    "input", "locals", "open", "setattr", "delattr", "vars",
}
JAVASCRIPT_BANNED = (
    "require(", "import ", "process.", "child_process", "fetch(", "eval(",
    "function(", "websocket", "deno.", "bun.", "node:fs", "fs.",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--llama-cli")
    parser.add_argument(
        "--endpoint",
        help="Optional local OpenAI-compatible chat endpoint; avoids reloading GGUF for every case.",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--tokens", type=int, default=256)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--case", action="append", dest="case_ids", help="run only this case ID; repeatable")
    parser.add_argument("--max-attempts", type=int, choices=(1, 2), default=2)
    parser.add_argument("--generation-timeout", type=int, default=180)
    parser.add_argument("--rerun-failures", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def diagnostic_for(case: dict) -> str:
    with tempfile.TemporaryDirectory(prefix="codefellow-eval-source-") as directory:
        path = Path(directory) / case["filename"]
        path.write_text(case["source"], encoding="utf-8")
        return codefellow.local_diagnostic(path, case["source"])


def evaluation_prompt(case: dict) -> str:
    prompt = codefellow.build_prompt(
        Path(case["filename"]),
        case["source"],
        diagnostic_for(case),
        case["question"],
        True,
    )
    return prompt + f"""

Evaluation format constraint:
- In Next step, return exactly one fenced `{case['language']}` code block containing the complete
  corrected source file. Do not return a diff and do not place test code inside that block.
- Put the code block before Checks and keep the entire response under 180 words.
"""


def extract_code(response: str, language: str) -> str | None:
    names = "python|py" if language == "python" else "javascript|js"
    match = re.search(rf"```(?:{names})\s*\n(.*?)```", response, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        match = re.search(r"```\s*\n(.*?)```", response, flags=re.DOTALL)
    return match.group(1).strip() + "\n" if match else None


def retry_prompt(base_prompt: str, response: str, detail: str) -> str:
    return f"""{base_prompt}

Your previous candidate did not pass local verification.
Verification feedback:
{detail[-1200:]}

Previous answer:
{response[-3000:]}

Revise the answer now. Make the code change described by your explanation, dry-run the stated
edge case, and return one complete corrected source block in the required format.
"""


def python_preflight(source: str) -> str | None:
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return f"generated Python syntax error: {error.msg}"
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return "generated Python imports are not allowed in this benchmark"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in PYTHON_BANNED_CALLS:
                return f"generated Python call is not allowed: {node.func.id}"
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            return "generated Python dunder access is not allowed"
    return None


def javascript_preflight(source: str) -> str | None:
    lowered = re.sub(r"\s+", "", source.lower())
    for marker in JAVASCRIPT_BANNED:
        if marker.replace(" ", "") in lowered:
            return f"generated JavaScript construct is not allowed: {marker}"
    return None


def limit_child() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))


def execute(case: dict, source: str) -> tuple[bool, str]:
    if source.strip() == case["source"].strip():
        return False, "candidate is identical to the supplied buggy source"
    preflight = python_preflight(source) if case["language"] == "python" else javascript_preflight(source)
    if preflight:
        return False, preflight
    runtime = sys.executable if case["language"] == "python" else shutil.which("node")
    if not runtime:
        return False, "node runtime is unavailable"
    with tempfile.TemporaryDirectory(prefix="codefellow-eval-run-") as directory:
        path = Path(directory) / case["filename"]
        path.write_text(source + "\n" + case["tests"], encoding="utf-8")
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": directory}
        try:
            result = subprocess.run(
                [runtime, str(path)],
                cwd=directory,
                env=env,
                capture_output=True,
                text=True,
                timeout=EXECUTION_TIMEOUT_SECONDS,
                check=False,
                preexec_fn=limit_child,
            )
        except subprocess.TimeoutExpired:
            return False, f"execution exceeded {EXECUTION_TIMEOUT_SECONDS}s"
        output = (result.stdout + result.stderr).strip()[-MAX_OUTPUT_CHARS:]
        return result.returncode == 0, output or f"exit code {result.returncode}"


def write_report(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def server_inference(endpoint: str, prompt: str, tokens: int) -> tuple[int, str, str]:
    payload = {
        "model": "CodeFellow",
        "messages": [
            {"role": "system", "content": "You are CodeFellow, an offline coding tutor."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "seed": 42,
        "max_tokens": tokens,
        "stream": False,
        "cache_prompt": True,
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            document = json.loads(response.read().decode("utf-8"))
        return 0, document["choices"][0]["message"]["content"], ""
    except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as error:
        return 1, "", f"local inference endpoint failed: {error}"


def main() -> int:
    args = parse_args()
    if not args.endpoint and (args.model is None or args.llama_cli is None):
        raise SystemExit("pass --endpoint, or pass both --model and --llama-cli")
    model = args.model.resolve() if args.model else None
    if model is not None and not model.is_file():
        raise SystemExit(f"model not found: {model}")
    executable = codefellow.resolve_executable(args.llama_cli) if not args.endpoint else None
    selected = (
        [item for item in CASES if item["id"] in set(args.case_ids)]
        if args.case_ids
        else CASES[: max(0, min(args.limit, len(CASES)))]
    )
    if args.case_ids and len(selected) != len(set(args.case_ids)):
        known = {item["id"] for item in CASES}
        missing = sorted(set(args.case_ids) - known)
        raise SystemExit(f"unknown case ID(s): {', '.join(missing)}")
    payload = {
        "benchmark": "CodeFellow executable repair suite v1",
        "model": str(model) if model else "local-endpoint",
        "endpoint": args.endpoint,
        "threads": args.threads,
        "tokens": args.tokens,
        "max_attempts": args.max_attempts,
        "generation_timeout": args.generation_timeout,
        "total": len(selected),
        "results": [],
    }
    if args.output.exists() and not args.overwrite:
        payload = json.loads(args.output.read_text(encoding="utf-8"))
        payload.update(
            {
                "model": str(model) if model else "local-endpoint",
                "endpoint": args.endpoint,
                "threads": args.threads,
                "tokens": args.tokens,
                "max_attempts": args.max_attempts,
                "generation_timeout": args.generation_timeout,
                "total": len(selected),
            }
        )
        if args.rerun_failures:
            selected_ids = {item["id"] for item in selected}
            payload["results"] = [
                row
                for row in payload.get("results", [])
                if row["id"] not in selected_ids or row["passed"]
            ]
    completed = {row["id"] for row in payload.get("results", [])}

    for index, item in enumerate(selected, 1):
        if item["id"] in completed:
            print(f"[{index:02d}/{len(selected):02d}] {item['id']}: cached", flush=True)
            continue
        started = time.monotonic()
        base_prompt = evaluation_prompt(item)
        current_prompt = base_prompt
        attempts = []
        passed = False
        response = ""
        code = None
        detail = "no attempt completed"
        for attempt_number in range(1, args.max_attempts + 1):
            attempt_started = time.monotonic()
            if args.endpoint:
                return_code, response, stderr = server_inference(
                    args.endpoint, current_prompt, args.tokens
                )
            else:
                return_code, response, stderr = codefellow.run_inference(
                    executable,
                    model,
                    current_prompt,
                    threads=args.threads,
                    tokens=args.tokens,
                    timeout_seconds=args.generation_timeout,
                )
            code = extract_code(response, item["language"])
            if return_code != 0:
                passed, detail = False, stderr or f"llama-cli exit code {return_code}"
            elif code is None:
                passed, detail = False, "no complete fenced code block found"
            else:
                passed, detail = execute(item, code)
            attempts.append(
                {
                    "attempt": attempt_number,
                    "passed": passed,
                    "duration_seconds": round(time.monotonic() - attempt_started, 2),
                    "detail": detail,
                    "response": response,
                    "extracted_code": code,
                }
            )
            if passed:
                break
            current_prompt = retry_prompt(base_prompt, response, detail)
        row = {
            "id": item["id"],
            "language": item["language"],
            "passed": passed,
            "passed_first_attempt": attempts[0]["passed"],
            "duration_seconds": round(time.monotonic() - started, 2),
            "detail": detail,
            "response": response,
            "extracted_code": code,
            "attempts": attempts,
        }
        payload.setdefault("results", []).append(row)
        payload["passed"] = sum(result["passed"] for result in payload["results"])
        write_report(args.output, payload)
        print(
            f"[{index:02d}/{len(selected):02d}] {item['id']}: "
            f"{'PASS' if passed else 'FAIL'} ({row['duration_seconds']:.2f}s)",
            flush=True,
        )

    relevant = [row for row in payload["results"] if row["id"] in {item["id"] for item in selected}]
    passed = sum(row["passed"] for row in relevant)
    python_rows = [row for row in relevant if row["language"] == "python"]
    javascript_rows = [row for row in relevant if row["language"] == "javascript"]
    payload["summary"] = {
        "passed": passed,
        "total": len(relevant),
        "pass_rate": round(passed / len(relevant), 4) if relevant else 0.0,
        "pass_at_1": sum(row.get("passed_first_attempt", row["passed"]) for row in relevant),
        "pass_at_2": passed,
        "python_passed": sum(row["passed"] for row in python_rows),
        "python_total": len(python_rows),
        "javascript_passed": sum(row["passed"] for row in javascript_rows),
        "javascript_total": len(javascript_rows),
        "duration_seconds": round(sum(row["duration_seconds"] for row in relevant), 2),
    }
    write_report(args.output, payload)
    print(json.dumps(payload["summary"], indent=2), flush=True)
    return 0 if len(relevant) == len(selected) else 1


if __name__ == "__main__":
    raise SystemExit(main())
