#!/usr/bin/env python3
"""CodeFellow: a small offline, diagnostics-grounded coding tutor."""

from __future__ import annotations

import argparse
import ast
import json
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from response_contract import normalize_code_response, normalize_explanation_response
from translation_backend import CTranslate2NllbTranslator

MAX_SOURCE_BYTES = 64 * 1024
DIAGNOSTIC_TIMEOUT_SECONDS = 20
GENERATION_TIMEOUT_SECONDS = 300
TEST_TIMEOUT_SECONDS = 45
MAX_EVIDENCE_CHARS = 8000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ask an on-device model for a hint or full diagnosis of one source file."
    )
    parser.add_argument("source", type=Path, help="Python or JavaScript source file to inspect")
    parser.add_argument("--question", default="Help me understand and fix this code.")
    parser.add_argument(
        "--language",
        choices=("en", "sw", "sw-mix"),
        default="en",
        help="response language; the specialized bilingual mode is sw-mix",
    )
    parser.add_argument("--full-answer", action="store_true", help="request a worked answer instead of one guided hint")
    parser.add_argument(
        "--review",
        action="store_true",
        help="run a second local critic pass for higher full-answer accuracy",
    )
    parser.add_argument("--model", type=Path, help="GGUF path; defaults to _runtime.model_path in metadata.json")
    parser.add_argument(
        "--translator",
        type=Path,
        help="CTranslate2 NLLB directory; defaults to _runtime.translation_path in metadata.json",
    )
    parser.add_argument("--llama-cli", help="llama-cli executable or path; defaults to PATH")
    parser.add_argument(
        "--test-command",
        help="optional trusted local test command to run in the source file's directory",
    )
    parser.add_argument("--threads", type=int, default=4, help="CPU threads used by llama.cpp (default: 4)")
    parser.add_argument("--tokens", type=int, default=640, help="maximum generated tokens (default: 640)")
    return parser.parse_args()


def default_model_path() -> Path:
    root = Path(__file__).resolve().parent
    metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    return root / metadata["_runtime"]["model_path"]


def default_translator_path() -> Path:
    root = Path(__file__).resolve().parent
    metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    return root / metadata["_runtime"]["translation_path"]


def resolve_executable(value: str | None) -> str:
    candidate = value or "llama-cli"
    if Path(candidate).is_file():
        return str(Path(candidate).resolve())
    found = shutil.which(candidate)
    if not found:
        raise SystemExit(
            "error: llama-cli was not found; pass --llama-cli /path/to/llama-cli"
        )
    return found


def read_source(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"error: source file not found: {path}")
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise SystemExit(f"error: source file exceeds {MAX_SOURCE_BYTES // 1024} KiB limit")
    return path.read_text(encoding="utf-8", errors="replace")


def local_diagnostic(path: Path, source: str) -> str:
    suffix = path.suffix.lower()
    if suffix == ".py":
        try:
            ast.parse(source, filename=str(path))
        except SyntaxError as error:
            location = f"line {error.lineno}, column {error.offset}"
            return f"Local Python syntax diagnostic failed ({location}).\n{error.msg}"
        return "Local Python syntax diagnostic passed.\n(no diagnostic output)"
    elif suffix in {".js", ".mjs", ".cjs"}:
        node = shutil.which("node")
        if not node:
            return "Node.js is not installed; JavaScript syntax check was unavailable."
        command = [node, "--check", str(path)]
    else:
        return f"No built-in diagnostic is configured for {suffix or 'extensionless'} files."

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=DIAGNOSTIC_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return f"Local diagnostic timed out after {DIAGNOSTIC_TIMEOUT_SECONDS} seconds."

    output = (result.stdout + result.stderr).strip()
    status = "passed" if result.returncode == 0 else f"failed (exit {result.returncode})"
    return f"Local syntax diagnostic {status}.\n{output or '(no diagnostic output)'}"


def local_test_evidence(path: Path, command_text: str) -> str:
    """Run only the learner-supplied test command, never model-generated commands."""
    try:
        command = shlex.split(command_text)
    except ValueError as error:
        return f"Local test command could not be parsed: {error}"
    if not command:
        return "Local test command was empty."
    try:
        result = subprocess.run(
            command,
            cwd=path.resolve().parent,
            capture_output=True,
            text=True,
            timeout=TEST_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        return f"Local test command was not found: {command[0]}"
    except subprocess.TimeoutExpired:
        return f"Local test command timed out after {TEST_TIMEOUT_SECONDS} seconds."
    output = (result.stdout + result.stderr).strip()
    if len(output) > MAX_EVIDENCE_CHARS:
        output = "[earlier output truncated]\n" + output[-MAX_EVIDENCE_CHARS:]
    status = "passed" if result.returncode == 0 else f"failed (exit {result.returncode})"
    return f"Learner-supplied local tests {status}.\n{output or '(no test output)'}"


def build_prompt(
    path: Path,
    source: str,
    diagnostic: str,
    question: str,
    full: bool,
    language: str = "en",
) -> str:
    if language in {"sw", "sw-mix"}:
        teaching_mode = (
            "JIBU KAMILI: Weka Uchunguzi katika sentensi moja. Katika Hatua inayofuata, onyesha "
            "marekebisho madogo sahihi; toa function nzima iliyobadilishwa ikiwa kipande kinaweza "
            "kuchanganya. Katika Majaribio, toa tests tatu fupi. Katika Sababu, eleza chanzo cha bug "
            "na invariant bila kufuatilia zaidi ya iterations mbili. Ikiwa mwanafunzi ametoa wrong "
            "result inayoweza kurudiwa, patch lazima itofautiane na source isipokuwa requirement "
            "yenyewe inapingana."
            if full
            else
            "DOKEZO LINALOONGOZA: Weka Uchunguzi katika sentensi moja. Toa dokezo moja linaloweza "
            "kutekelezwa na swali moja la kumsaidia mwanafunzi kufikiri. Usitoe implementation nzima."
        )
        language_instruction = (
            "Jibu kwa Kiswahili cha kawaida, lakini tumia maneno ya kawaida ya Kiingereza ya "
            "programming: function, variable, array, list, loop, class, object, API, database, "
            "compiler, runtime, pointer na recursion pale programmers wanapoyatumia kawaida. Acha "
            "identifiers na language keywords bila kubadilishwa. Usilazimishe tafsiri za technical "
            "terms. Tumia headings hizi hasa: Uchunguzi, Hatua inayofuata, Majaribio, Sababu."
            if language == "sw-mix"
            else
            "Jibu kwa Kiswahili cha kawaida. Acha programmer identifiers na language keywords bila "
            "kubadilishwa. Tumia headings hizi hasa: Uchunguzi, Hatua inayofuata, Majaribio, Sababu."
        )
        headings = "Uchunguzi, Hatua inayofuata, Majaribio, Sababu"
    else:
        teaching_mode = (
            "FULL ANSWER: Keep Observation to one sentence. In Next step, show the smallest correct "
            "patch; prefer one complete changed function when a fragment could be ambiguous. In Checks, "
            "give three concise tests before detailed explanation. In Why, explain the root cause and "
            "invariant without tracing more than two iterations. If the learner reports a reproducible "
            "wrong result, the proposed patch must differ from the supplied source unless you clearly "
            "demonstrate that the stated requirement is inconsistent."
            if full
            else
            "GUIDED HINT: Keep Observation to one sentence. Give exactly one actionable hint and one "
            "question that helps the learner reason. Do not provide a complete replacement implementation."
        )
        language_instruction = "Respond in clear English."
        headings = "Observation, Next step, Checks, Why"
    return f"""You are CodeFellow, an offline coding tutor for a beginner.
Use plain language and ground every claim in the supplied code and local diagnostic.
Before answering, silently simulate every example stated by the learner. Treat stated expected
outputs as constraints; do not replace them with invented values. Check empty input, repeated
values, type conversions, and loop or index boundaries whenever they are relevant.
The local evidence below is a syntax check, not proof that behavior tests passed. Never claim code
or tests ran unless that evidence explicitly says so. Label suggested checks as unrun.
Prefer a minimal repair that preserves the learner's structure and public function signature.
For a loop with a set, stack, window, or index boundary, identify its invariant and make sure each
update fully restores it before the next iteration; one state update may need to repeat. For numeric
input, normalize and validate types before arithmetic and handle empty input explicitly.
{teaching_mode}
{language_instruction}

Learner question:
{question}

File: {path.name}
Local evidence:
{diagnostic}

Source code:
```{path.suffix.lstrip('.')}
{source}
```

Respond with these headings: {headings}.
"""


def extract_assistant_response(transcript: str) -> str:
    """Return the final assistant block from llama-cli's transcript format."""
    marker = "Assistant:\n"
    return transcript.rsplit(marker, 1)[-1].strip() if marker in transcript else ""


def build_review_prompt(original_prompt: str, draft: str, language: str) -> str:
    instruction = (
        "Kagua draft dhidi ya source, local evidence na kila sharti la mwanafunzi. Rekebisha "
        "makosa ya logic au boundary cases bila kudai tests ziliendeshwa. Hifadhi headings na "
        "Kiswahili/English programming register iliyoombwa. Rudisha jibu kamili lililoboreshwa."
        if language in {"sw", "sw-mix"}
        else
        "Review the draft against the source, local evidence, and every learner requirement. Fix "
        "logic or boundary errors without claiming tests ran. Preserve the requested headings and "
        "return the complete improved answer."
    )
    return f"{original_prompt}\n\nDraft answer to review:\n{draft}\n\n{instruction}"


def run_inference(
    executable: str,
    model: Path,
    prompt: str,
    *,
    threads: int = 4,
    tokens: int = 640,
    timeout_seconds: int = GENERATION_TIMEOUT_SECONDS,
) -> tuple[int, str, str]:
    """Run one private local turn and return (exit code, response, stderr)."""
    command = [
        executable,
        "-m",
        str(model),
        "-p",
        prompt,
        "-n",
        str(tokens),
        "-t",
        str(threads),
        "-c",
        "4096",
        "--temp",
        "0.0",
        "--no-display-prompt",
        "--no-warmup",
        "--simple-io",
        "--conversation",
        "--single-turn",
        "--jinja",
    ]
    with tempfile.TemporaryDirectory(prefix="codefellow-") as directory:
        transcript_path = Path(directory) / "turn.txt"
        command.extend(["--output-file", str(transcript_path)])
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return 124, "", f"llama-cli exceeded the {timeout_seconds}-second generation limit"
        transcript = (
            transcript_path.read_text(encoding="utf-8", errors="replace")
            if transcript_path.exists()
            else ""
        )
        return result.returncode, extract_assistant_response(transcript), result.stderr.strip()


def main() -> int:
    args = parse_args()
    model = (args.model or default_model_path()).resolve()
    if not model.is_file():
        raise SystemExit(f"error: model not found: {model}; run bash download_model.sh")

    executable = resolve_executable(args.llama_cli)
    source = read_source(args.source)
    diagnostic = local_diagnostic(args.source, source)
    if args.test_command:
        diagnostic += "\n\n" + local_test_evidence(args.source, args.test_command)
    translator = None
    model_language = args.language
    question = args.question
    if args.language in {"sw", "sw-mix"}:
        translator_path = (args.translator or default_translator_path()).resolve()
        if not translator_path.is_dir():
            raise SystemExit(
                f"error: Kiswahili translator not found: {translator_path}; "
                "run bash download_translation.sh"
            )
        translator = CTranslate2NllbTranslator(str(translator_path), threads=args.threads)
        question, _ = translator.translate_requirement(args.question)
        model_language = "en"
    prompt = build_prompt(
        args.source, source, diagnostic, question, args.full_answer, model_language
    )

    return_code, response, stderr = run_inference(
        executable,
        model,
        prompt,
        threads=args.threads,
        tokens=args.tokens,
    )
    if args.review and args.full_answer and response and return_code == 0:
        review_code, reviewed, review_stderr = run_inference(
            executable,
            model,
            build_review_prompt(prompt, response, model_language),
            threads=args.threads,
            tokens=args.tokens,
        )
        if review_code == 0 and reviewed:
            response = reviewed
        elif review_stderr:
            stderr = (stderr + "\n" + review_stderr).strip()
    if response and translator is not None:
        response = translator.translate_markdown_to_swahili(response)
        response, _ = normalize_explanation_response(response, args.language)
    if response and args.full_answer:
        runtime = "python" if args.source.suffix.lower() == ".py" else "javascript"
        response, _ = normalize_code_response(response, runtime, args.language)
    if response:
        print(response)
    if return_code != 0:
        print(stderr or "llama-cli failed without an error message", file=sys.stderr)
    elif not response:
        print("error: llama-cli returned no tutor response", file=sys.stderr)
        return 1
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
