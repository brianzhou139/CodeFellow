#!/usr/bin/env python3
"""Deterministic response formatting for CodeFellow's on-device code lane.

The language model remains responsible for the implementation. This module only
enforces the application's public response contract when a compact model emits
bare code: one fenced block, no obvious top-level demo execution, and one short
language-appropriate sentence. It never executes generated code.
"""

from __future__ import annotations

import ast
import re


FENCED_CODE_RE = re.compile(
    r"```(?P<label>python|py|javascript|js)?\s*\n(?P<code>.*?)```",
    re.IGNORECASE | re.DOTALL,
)
MIXED_TERM_RE = re.compile(
    r"\b(?:function|variable|array|list|loop|class|object|api|database|compiler|"
    r"runtime|pointer|recursion|code|debug|tests?|input|output|return|type)\b",
    re.IGNORECASE,
)
SWAHILI_TERM_RE = re.compile(
    r"\b(?:na|kwa|hii|huu|hutumia|inarejesha|kurejesha|msimbo|masharti|salama|"
    r"sahihi|matokeo|suluhisho|bila|kisha|ikiwa|orodha|thamani)\b",
    re.IGNORECASE,
)

EXPLANATIONS = {
    "en": "This code follows the requirements and returns the requested result safely.",
    "sw": "Msimbo huu hutumia masharti kwa usalama na kurejesha matokeo sahihi.",
    "sw_mix": "Function hii hutumia requirement kwa usalama na ku-return output sahihi.",
    "sw-mix": "Function hii hutumia requirement kwa usalama na ku-return output sahihi.",
}

MIXED_EXPLANATION_SUFFIX = (
    "Kwa kifupi, concept hii inaonyesha jinsi function, input na output zinavyohusiana."
)


def _trim_python_demo(code: str) -> str | None:
    """Return syntactically valid definitions without trailing demo execution."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    definitions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    if not definitions:
        return None
    last_definition_line = max(node.end_lineno or node.lineno for node in definitions)
    lines = code.splitlines()
    trimmed = "\n".join(lines[:last_definition_line]).rstrip()
    try:
        ast.parse(trimmed)
    except SyntaxError:
        return None
    return trimmed


def _javascript_code_mask(code: str) -> str:
    """Mask strings and comments while retaining braces and line breaks."""
    output: list[str] = []
    index = 0
    quote: str | None = None
    line_comment = False
    block_comment = False
    while index < len(code):
        char = code[index]
        nxt = code[index + 1] if index + 1 < len(code) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
                output.append("\n")
            else:
                output.append(" ")
        elif block_comment:
            if char == "*" and nxt == "/":
                output.extend((" ", " "))
                block_comment = False
                index += 1
            else:
                output.append("\n" if char == "\n" else " ")
        elif quote:
            if char == "\\":
                output.append(" ")
                if nxt:
                    output.append(" ")
                    index += 1
            elif char == quote:
                quote = None
                output.append(" ")
            else:
                output.append("\n" if char == "\n" else " ")
        elif char == "/" and nxt == "/":
            output.extend((" ", " "))
            line_comment = True
            index += 1
        elif char == "/" and nxt == "*":
            output.extend((" ", " "))
            block_comment = True
            index += 1
        elif char in {'"', "'", "`"}:
            quote = char
            output.append(" ")
        else:
            output.append(char)
        index += 1
    return "".join(output)


def _trim_javascript_demo(code: str) -> str | None:
    """Keep declarations through the last top-level function/class body."""
    masked = _javascript_code_mask(code)
    declaration = re.search(
        r"(?m)^\s*(?:(?:export\s+)?(?:async\s+)?function\b|"
        r"(?:export\s+)?class\b|(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=.*=>)",
        masked,
    )
    if not declaration:
        return None
    depth = 0
    saw_open = False
    last_top_level_close: int | None = None
    for index, char in enumerate(masked):
        if char == "{":
            depth += 1
            saw_open = True
        elif char == "}" and depth:
            depth -= 1
            if saw_open and depth == 0:
                last_top_level_close = index + 1
    if last_top_level_close is None:
        return None
    end = last_top_level_close
    while end < len(code) and code[end] in " \t;":
        end += 1
    return code[:end].rstrip()


def normalize_code_response(content: str, runtime: str, language: str) -> tuple[str, list[str]]:
    """Apply the response contract to bare code and return content plus actions."""
    stripped = content.strip()
    if not stripped:
        return stripped, []
    runtime_key = runtime.casefold()
    fenced = FENCED_CODE_RE.search(stripped)
    actions: list[str] = []
    if fenced:
        fenced_code = fenced.group("code").strip()
        if runtime_key == "python":
            sanitized = _trim_python_demo(fenced_code)
            label = fenced.group("label") or "python"
        elif runtime_key in {"javascript", "js"}:
            sanitized = _trim_javascript_demo(fenced_code)
            label = fenced.group("label") or "javascript"
        else:
            sanitized = None
            label = fenced.group("label") or ""
        if sanitized and sanitized != fenced_code:
            replacement = f"```{label}\n{sanitized}\n```"
            stripped = stripped[:fenced.start()] + replacement + stripped[fenced.end():]
            actions.append("removed_trailing_demo")
        non_code = FENCED_CODE_RE.sub(" ", stripped)
        swahili_hits = {match.group(0).casefold() for match in SWAHILI_TERM_RE.finditer(non_code)}
        needs_swahili = language in {"sw", "sw_mix", "sw-mix"} and len(swahili_hits) < 2
        needs_mixed = language in {"sw_mix", "sw-mix"} and not MIXED_TERM_RE.search(non_code)
        if needs_swahili or needs_mixed:
            stripped += "\n\n" + EXPLANATIONS.get(language, EXPLANATIONS["sw"])
            actions.append("added_mixed_register" if needs_mixed else "added_swahili_register")
        return stripped, actions
    if runtime_key == "python":
        code = _trim_python_demo(stripped)
        fence = "python"
    elif runtime_key in {"javascript", "js"}:
        code = _trim_javascript_demo(stripped)
        fence = "javascript"
    else:
        return stripped, []
    if not code:
        return stripped, []
    actions = ["wrapped_bare_code"]
    if code != stripped:
        actions.append("removed_trailing_demo")
    explanation = EXPLANATIONS.get(language, EXPLANATIONS["en"])
    return f"```{fence}\n{code}\n```\n\n{explanation}", actions


def normalize_explanation_response(content: str, language: str) -> tuple[str, list[str]]:
    """Preserve translated teaching prose and ensure a natural mixed register."""
    stripped = content.strip()
    if language not in {"sw_mix", "sw-mix"} or not stripped:
        return stripped, []
    prose = FENCED_CODE_RE.sub(" ", stripped)
    terms = {match.group(0).casefold() for match in MIXED_TERM_RE.finditer(prose)}
    if len(terms) >= 2:
        return stripped, []
    return stripped + "\n\n" + MIXED_EXPLANATION_SUFFIX, ["added_mixed_explanation_register"]
