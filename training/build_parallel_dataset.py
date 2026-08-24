#!/usr/bin/env python3
"""Build CodeFellow's verified, code-locked parallel SFT dataset.

Every source task is represented in English, Kiswahili, and natural
English/Kiswahili code-switching.  The natural-language teaching prose changes
between lanes; the executable implementation does not.
"""

from __future__ import annotations

import argparse
import ast
import copy
import difflib
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

try:
    from .build_dataset import (
        SWAHILI_CURRICULUM,
        Translator,
        clean_mbpp_prompt,
        code_switch_swahili,
    )
    from .curriculum import CURRICULUM
except ImportError:  # Direct execution.
    from build_dataset import (
        SWAHILI_CURRICULUM,
        Translator,
        clean_mbpp_prompt,
        code_switch_swahili,
    )
    from curriculum import CURRICULUM


SYSTEM_PROMPT = """You are CodeFellow, an offline programming tutor.
Answer in the requested language while preserving programming identifiers,
keywords, operators, literals, APIs, and code exactly. Return correct,
complete, standard-library code in a closed Markdown code fence. Do not access
the network, filesystem, shell, environment variables, or external processes."""

EN_WRAPPERS = (
    "{requirement}\n\nReturn one complete fenced {runtime} implementation, followed by one concise English explanation. Do not include tests or example calls.",
    "Implement the following requirement carefully:\n{requirement}\n\nUse one closed {runtime} code fence and briefly explain the approach in English.",
    "Write a correct, minimal solution for this task:\n{requirement}\n\nPreserve the requested interface and put the complete code before a short English explanation.",
    "A beginner needs a reliable implementation of this requirement:\n{requirement}\n\nGive exactly one fenced code block, then explain the key idea in one English sentence.",
    "Solve this without external packages:\n{requirement}\n\nReturn complete {runtime} code in one Markdown fence and a concise English explanation.",
    "Follow every boundary condition in this programming task:\n{requirement}\n\nProvide one fenced implementation and one short English teaching note.",
    "Produce an instruction-following answer for:\n{requirement}\n\nThe answer must contain one closed {runtime} fence, no tests, and a brief English explanation.",
    "Implement and mentally check normal, empty, and boundary inputs where relevant:\n{requirement}\n\nReturn the implementation first and a short English explanation second.",
    "Complete this coding task while keeping names and return behavior unchanged:\n{requirement}\n\nUse one fenced {runtime} block followed by one concise English sentence.",
    "Give the smallest complete solution that satisfies this contract:\n{requirement}\n\nOutput code in one closed fence, then explain the method briefly in English.",
)

SW_WRAPPERS = (
    "{requirement}\n\nJibu kwa Kiswahili. Toa implementation kamili ndani ya fenced {runtime} code block moja, kisha sentensi moja fupi ya maelezo. Usiongeze tests au example calls.",
    "Tekeleza requirement hii kwa makini:\n{requirement}\n\nHifadhi identifiers na programming terms. Rudisha closed code fence moja na maelezo mafupi ya Kiswahili.",
    "Mwanafunzi anahitaji solution sahihi ya task hii:\n{requirement}\n\nAnza na fenced {runtime} code kamili, kisha eleza approach kwa sentensi moja ya Kiswahili.",
    "Fuata conditions zote, pamoja na edge cases zinazohusika:\n{requirement}\n\nToa code block moja tu na teaching note fupi ya Kiswahili.",
    "Tengeneza implementation ndogo na sahihi bila external packages:\n{requirement}\n\nJibu liwe closed {runtime} code fence moja, halafu maelezo mafupi ya Kiswahili.",
)

MIX_WRAPPERS = (
    "{requirement}\n\nJibu kwa Kiswahili lakini tumia English programming terms kwa kawaida. Toa complete implementation ndani ya fenced {runtime} code block moja, then short explanation. Usiongeze tests.",
    "Implement requirement hii kwa makini:\n{requirement}\n\nKeep identifiers unchanged, return one closed code fence, kisha eleza approach kwa Kiswahili.",
    "Mwanafunzi ameomba reliable solution ya task hii:\n{requirement}\n\nAnza na complete {runtime} code, then toa concise Kiswahili teaching note yenye natural English coding terms.",
    "Check edge cases zinazohusika na ufuate interface hii:\n{requirement}\n\nOutput fenced code block moja na short Kiswahili explanation; no tests or example calls.",
    "Solve coding contract hii bila external packages:\n{requirement}\n\nReturn implementation kamili first, kisha sentence moja ya Kiswahili yenye normal English programming vocabulary.",
)

SEMANTIC_ANCHOR_GROUPS = (
    (("character", "characters", "letter", "letters"), ("digit", "digits")),
    (("minimum", "min", "smallest", "least"), ("maximum", "max", "largest", "greatest")),
    (("ascending", "increasing"), ("descending", "decreasing")),
    (("positive",), ("negative",)), (("even",), ("odd",)), (("first",), ("last",)),
    (("sum", "total"), ("product", "multiplication"), ("difference", "subtraction")),
    (("remove", "delete"), ("replace",)),
    (("unique", "distinct"), ("duplicate", "duplicates", "duplicant", "duplicants", "repeated")),
    (("uppercase", "upper"), ("lowercase", "lower")),
    (("square", "squares"), ("cube", "cubes")),
)
TECHNICAL_TERMS = (
    "function", "variable", "array", "list", "tuple", "string", "character",
    "dictionary", "set", "loop", "class", "object", "API", "database",
    "compiler", "runtime", "pointer", "recursion", "regex", "index",
)

INCOMPLETE_MARKERS = re.compile(r"\b(?:todo|fixme|your code here|not implemented|pass)\b", re.I)
UNSAFE_MARKERS = re.compile(
    r"\b(?:subprocess|socket|requests|urllib|child_process)\b|"
    r"\bopen\s*\(|\b(?:eval|exec|__import__)\s*\(|process\.env|require\s*\(\s*['\"](?:fs|net|http|https|os)",
    re.I,
)
FENCE_RE = re.compile(r"```(?:python|py|javascript|js)\s*\n(.*?)```", re.I | re.S)


@dataclass(frozen=True)
class VerifiedTask:
    parallel_id: str
    source: str
    runtime: str
    kind: str
    prompt_en: str
    prompt_sw: str
    prompt_mix: str
    code: str
    tests_sha256: str
    hidden_test_count: int
    explanation_en: str
    explanation_sw: str
    explanation_mix: str
    translation_score: float
    translation_anchors_verified: bool
    explanation_translation_score: float
    explanation_anchors_verified: bool
    explanation_verification_method: str
    mutation_killed: int
    mutation_total: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--total-records", type=int, default=10_000)
    parser.add_argument("--mbpp-limit", type=int, default=650)
    parser.add_argument("--humaneval-limit", type=int, default=0)
    parser.add_argument("--validation-fraction", type=float, default=0.05)
    parser.add_argument("--translation-model", default="facebook/nllb-200-distilled-600M")
    parser.add_argument(
        "--ct2-translation-model",
        type=Path,
        help="Optional local CTranslate2 INT8 NLLB directory; avoids GPU heat.",
    )
    parser.add_argument("--translation-threads", type=int, default=4)
    parser.add_argument("--translation-cache", type=Path)
    parser.add_argument("--seed", type=int, default=2026)
    return parser.parse_args()


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clean_translation(text: str) -> str:
    text = text.replace("```", "").strip()
    return re.sub(r"\s+", " ", text)


def gpu_temperature() -> int | None:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return None
    try:
        output = subprocess.check_output(
            [executable, "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            text=True, timeout=5,
        )
        return int(output.splitlines()[0].strip())
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def thermal_guard(maximum: int = 84, resume: int = 80) -> None:
    temperature = gpu_temperature()
    if temperature is None or temperature < maximum:
        return
    print(f"translation GPU reached {temperature} C; cooling to {resume} C", flush=True)
    while temperature is not None and temperature > resume:
        time.sleep(10)
        temperature = gpu_temperature()
    print(f"translation resumed at {temperature} C", flush=True)


class CTranslate2Teacher:
    """Batch-capable CPU-int8 NLLB prose teacher with the same cache contract."""

    def __init__(self, model_path: Path, cache_path: Path, threads: int) -> None:
        import ctranslate2
        import sentencepiece as spm

        self.cache_path = cache_path
        self.cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        self.sentencepiece = spm.SentencePieceProcessor()
        if not self.sentencepiece.load(str(model_path / "sentencepiece.bpe.model")):
            raise RuntimeError("could not load the NLLB SentencePiece tokenizer")
        self.engine = ctranslate2.Translator(
            str(model_path), device="cpu", compute_type="int8",
            inter_threads=1, intra_threads=threads,
        )

    def translate_cached(
        self,
        texts: list[str],
        *,
        source_lang: str,
        target_lang: str,
        cache_path: Path,
        short_keys: bool,
        batch_size: int = 8,
    ) -> list[str]:
        cache = (
            self.cache
            if cache_path == self.cache_path
            else json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        )
        key = (lambda text: digest(text)[:20]) if short_keys else digest
        pending = [text for text in texts if key(text) not in cache]
        for start in range(0, len(pending), batch_size):
            batch = pending[start:start + batch_size]
            sources = [
                [source_lang, *self.sentencepiece.encode_as_pieces(text), "</s>"]
                for text in batch
            ]
            results = self.engine.translate_batch(
                sources,
                target_prefix=[[target_lang] for _ in batch],
                beam_size=4,
                max_decoding_length=384,
            )
            for source, result in zip(batch, results):
                target = result.hypotheses[0]
                if target and target[0] == target_lang:
                    target = target[1:]
                target = [token for token in target if token != "</s>"]
                cache[key(source)] = self.sentencepiece.decode(target).strip()
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        if cache_path == self.cache_path:
            self.cache = cache
        return [cache[key(text)] for text in texts]


def translate_many_guarded(
    translator: Translator | CTranslate2Teacher, texts: list[str], batch_size: int = 8
) -> list[str]:
    """Run the prose teacher with incremental cache writes and thermal limits."""
    if isinstance(translator, CTranslate2Teacher):
        return translator.translate_cached(
            texts,
            source_lang="eng_Latn",
            target_lang="swh_Latn",
            cache_path=translator.cache_path,
            short_keys=True,
            batch_size=batch_size,
        )
    cache_key = lambda text: digest(text)[:20]
    pending = [text for text in texts if cache_key(text) not in translator.cache]
    for start in range(0, len(pending), batch_size):
        thermal_guard()
        batch = pending[start:start + batch_size]
        encoded = translator.tokenizer(
            batch, return_tensors="pt", padding=True, truncation=True, max_length=384
        ).to(translator.device)
        with translator.torch.inference_mode():
            output = translator.model.generate(
                **encoded,
                **translator.generation_args,
                max_new_tokens=384,
                num_beams=4,
            )
        translated = translator.tokenizer.batch_decode(output, skip_special_tokens=True)
        for source, target in zip(batch, translated):
            translator.cache[cache_key(source)] = target.strip()
        translator.cache_path.parent.mkdir(parents=True, exist_ok=True)
        translator.cache_path.write_text(
            json.dumps(translator.cache, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return [translator.cache[cache_key(text)] for text in texts]


def back_translate_many(
    translator: Translator | CTranslate2Teacher, texts: list[str], cache_path: Path
) -> list[str]:
    """Translate Kiswahili prose back to English for semantic rejection."""
    if isinstance(translator, CTranslate2Teacher):
        return translator.translate_cached(
            texts,
            source_lang="swh_Latn",
            target_lang="eng_Latn",
            cache_path=cache_path,
            short_keys=False,
        )
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    pending = [text for text in texts if digest(text) not in cache]
    tokenizer = translator.tokenizer
    old_source = getattr(tokenizer, "src_lang", "eng_Latn")
    tokenizer.src_lang = "swh_Latn"
    try:
        for start in range(0, len(pending), 8):
            thermal_guard()
            batch = pending[start:start + 8]
            encoded = tokenizer(
                batch, return_tensors="pt", padding=True, truncation=True, max_length=384
            ).to(translator.device)
            with translator.torch.inference_mode():
                output = translator.model.generate(
                    **encoded,
                    forced_bos_token_id=tokenizer.convert_tokens_to_ids("eng_Latn"),
                    max_new_tokens=384,
                    num_beams=4,
                )
            translated = tokenizer.batch_decode(output, skip_special_tokens=True)
            for source, target in zip(batch, translated):
                cache[digest(source)] = target.strip()
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        tokenizer.src_lang = old_source
    return [cache[digest(text)] for text in texts]


def semantic_quality(source: str, roundtrip: str) -> tuple[float, bool]:
    def tokens(text: str) -> list[str]:
        return re.findall(r"[a-z]+|\d+(?:\.\d+)?", text.casefold())

    source_tokens, target_tokens = tokens(source), tokens(roundtrip)
    source_set, target_set = set(source_tokens), set(target_tokens)
    overlap = len(source_set & target_set)
    f1 = 2 * overlap / max(1, len(source_set) + len(target_set))
    sequence = difflib.SequenceMatcher(
        None, " ".join(source_tokens), " ".join(target_tokens)
    ).ratio()
    numbers_preserved = set(re.findall(r"\d+(?:\.\d+)?", source)) == set(
        re.findall(r"\d+(?:\.\d+)?", roundtrip)
    )
    anchors_preserved = numbers_preserved
    for group in SEMANTIC_ANCHOR_GROUPS:
        source_hits = {
            index for index, alternatives in enumerate(group)
            if any(term in source_set for term in alternatives)
        }
        target_hits = {
            index for index, alternatives in enumerate(group)
            if any(term in target_set for term in alternatives)
        }
        if source_hits != target_hits:
            anchors_preserved = False
            break
    negations = {"not", "without", "except", "excluding", "no"}
    if bool(source_set & negations) != bool(target_set & negations):
        anchors_preserved = False
    return round((f1 + sequence) / 2, 4), anchors_preserved


def preserve_technical_terms(source: str, translation: str) -> str:
    present = [
        term for term in TECHNICAL_TERMS
        if re.search(rf"\b{re.escape(term)}s?\b", source, re.I)
    ]
    if re.search(r"\bcharacters?\b", source, re.I) and not re.search(r"\bdigits?\b", source, re.I):
        translation = re.sub(r"\btarakimu\b", "characters", translation, flags=re.I)
    if re.search(r"\bfunction\b", source, re.I):
        translation = re.sub(
            r"^(Andika|Tengeneza) kazi ya\b", r"\1 function ya", translation, flags=re.I
        )
    if present:
        translation += " Technical terms zihifadhiwe: " + ", ".join(present) + "."
    return translation


def language_name(runtime: str) -> str:
    return "python" if runtime == "python" else "javascript"


def task_specific_explanation(prompt: str) -> str:
    """Create concise, task-grounded prose for the translation teacher.

    Repeating a small bank of generic localized sentences caused early LoRA
    checkpoints to learn repetitive Kiswahili.  Grounding every explanation in
    its independently verified requirement provides hundreds of distinct prose
    targets while leaving the executable solution untouched.
    """
    requirement = re.sub(r"\s+", " ", prompt).strip().rstrip(".")
    if len(requirement) > 260:
        shortened = requirement[:260].rsplit(" ", 1)[0]
        requirement = shortened.rstrip(" ,;:") + "…"
    return (
        f"The implementation follows this required behavior: {requirement}; "
        "it preserves the requested interface and produces no extra output."
    )


def swahili_task_explanation(translated_prompt: str) -> str:
    """Use a natural authored frame around independently filtered teacher prose."""
    requirement = re.sub(r"\s+", " ", translated_prompt).strip().rstrip(".")
    requirement = re.sub(
        r"\s+Technical terms zihifadhiwe:.*$", "", requirement, flags=re.I
    ).rstrip(" .")
    return (
        f"Msimbo huu unatekeleza hitaji lifuatalo: {requirement}. "
        "Unahifadhi interface iliyoombwa na hautoi output ya ziada."
    )


def validate_python(code: str) -> None:
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name.split(".")[0] for alias in node.names]
            if any(name not in sys.stdlib_module_names for name in names):
                raise ValueError(f"non-standard Python import: {names}")
        if isinstance(node, ast.Expr):
            is_docstring = isinstance(node.value, ast.Constant) and isinstance(
                node.value.value, str
            )
            has_effect = isinstance(node.value, (ast.Call, ast.Await, ast.Yield, ast.YieldFrom))
            if not is_docstring and not has_effect:
                raise ValueError("no-effect Python expression statement")


def verify_program(runtime: str, code: str, tests: str, setup: str = "") -> tuple[str, int]:
    code = code.strip()
    tests = tests.strip()
    if not code or not tests:
        raise ValueError("code and hidden tests must be non-empty")
    if INCOMPLETE_MARKERS.search(code) or UNSAFE_MARKERS.search(code):
        raise ValueError("incomplete or unsafe reference implementation")
    if runtime == "python":
        validate_python(code)
        source = f"{setup.strip()}\n{code}\n{tests}\n"
        command_name, suffix = sys.executable, ".py"
    elif runtime == "javascript":
        source = f"{setup.strip()}\n{code}\n{tests}\n"
        command_name, suffix = "node", ".js"
    else:
        raise ValueError(f"unsupported runtime: {runtime}")
    with tempfile.TemporaryDirectory(prefix="codefellow-parallel-verify-") as directory:
        path = Path(directory) / f"reference{suffix}"
        path.write_text(source, encoding="utf-8")
        environment = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"), "LANG": "C.UTF-8"}
        result = subprocess.run(
            [command_name, str(path)], cwd=directory, env=environment,
            capture_output=True, text=True, timeout=15, check=False,
        )
    if result.returncode:
        raise ValueError(f"hidden verification failed: {result.stderr[-1000:]}")
    test_count = max(1, sum(1 for line in tests.splitlines() if "assert" in line))
    return digest(f"{setup.strip()}\n{tests}"), test_count


def mutation_score_python(
    code: str, tests: str, setup: str = "", max_mutants: int = 4
) -> tuple[int, int]:
    """Measure whether hidden tests kill simple deterministic code mutations."""
    tree = ast.parse(code)

    def kind(node: ast.AST) -> str | None:
        if isinstance(node, ast.Return) and node.value is not None:
            if not (isinstance(node.value, ast.Constant) and node.value.value is None):
                return "return_none"
        if isinstance(node, ast.Compare) and node.ops:
            if isinstance(node.ops[0], (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)):
                return "comparison"
        if isinstance(node, ast.BinOp) and isinstance(
            node.op, (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod)
        ):
            return "binary_operator"
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            return "boolean_operator"
        return None

    candidates = [index for index, node in enumerate(ast.walk(tree)) if kind(node)]
    mutants: list[str] = []
    for target in candidates:
        mutated = copy.deepcopy(tree)
        node = list(ast.walk(mutated))[target]
        mutation = kind(node)
        if mutation == "return_none":
            node.value = ast.Constant(value=None)
        elif mutation == "comparison":
            replacements = {
                ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE,
                ast.GtE: ast.Gt, ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
            }
            node.ops[0] = replacements[type(node.ops[0])]()
        elif mutation == "binary_operator":
            replacements = {
                ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.FloorDiv,
                ast.FloorDiv: ast.Mult, ast.Mod: ast.FloorDiv,
            }
            node.op = replacements[type(node.op)]()
        elif mutation == "boolean_operator":
            node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
        mutant = ast.unparse(ast.fix_missing_locations(mutated)).strip()
        if mutant != code.strip() and mutant not in mutants:
            mutants.append(mutant)
        if len(mutants) >= max_mutants:
            break

    killed = 0
    for mutant in mutants:
        try:
            verify_program("python", mutant, tests, setup)
        except (ValueError, SyntaxError, subprocess.SubprocessError, subprocess.TimeoutExpired):
            killed += 1
    return killed, len(mutants)


def curriculum_tasks() -> list[VerifiedTask]:
    tasks: list[VerifiedTask] = []
    for row in CURRICULUM:
        tests_hash, test_count = verify_program(row["runtime"], row["solution"], row["tests"])
        localized = SWAHILI_CURRICULUM[row["id"]]
        sw_prompt = localized["prompt"]
        sw_why = localized["why"]
        tasks.append(VerifiedTask(
            parallel_id=f"curriculum:{row['id']}", source="CodeFellow curriculum",
            runtime=row["runtime"], kind="debugging",
            prompt_en=f"Repair this buggy program. {row['prompt_en']}\n\nBuggy code:\n```{language_name(row['runtime'])}\n{row['buggy'].strip()}\n```",
            prompt_sw=f"Rekebisha buggy program hii. {sw_prompt}\n\nBuggy code:\n```{language_name(row['runtime'])}\n{row['buggy'].strip()}\n```",
            prompt_mix=f"Debug program hii. {code_switch_swahili(sw_prompt)}\n\nBuggy code:\n```{language_name(row['runtime'])}\n{row['buggy'].strip()}\n```",
            code=row["solution"].strip(), tests_sha256=tests_hash,
            hidden_test_count=test_count, explanation_en=row["why_en"],
            explanation_sw=sw_why, explanation_mix=code_switch_swahili(sw_why),
            translation_score=1.0, translation_anchors_verified=True,
            explanation_translation_score=1.0,
            explanation_anchors_verified=True,
            explanation_verification_method="project-authored localized curriculum",
            mutation_killed=0,
            mutation_total=0,
        ))
    return tasks


def mbpp_tasks(
    limit: int, translator: Translator | CTranslate2Teacher, roundtrip_cache: Path, seed: int
) -> list[VerifiedTask]:
    from datasets import load_dataset

    rows = list(load_dataset("Muennighoff/mbpp", "full", split="test"))
    random.Random(seed).shuffle(rows)
    verified: list[tuple[dict, str, str, int, int, int]] = []
    for row in rows:
        prompt = clean_mbpp_prompt(row["text"])
        if not 20 <= len(prompt) <= 600:
            continue
        setup = (row.get("test_setup_code") or "").strip()
        code = "\n".join(part for part in (setup, row["code"].strip()) if part)
        tests = "\n".join(
            [*(row.get("test_list") or []), *(row.get("challenge_test_list") or [])]
        )
        try:
            tests_hash, test_count = verify_program("python", code, tests)
            mutation_killed, mutation_total = mutation_score_python(code, tests)
            if mutation_total < 1 or mutation_killed / mutation_total < 0.50:
                continue
        except (ValueError, SyntaxError, subprocess.TimeoutExpired):
            continue
        verified.append(
            (row, code, tests_hash, test_count, mutation_killed, mutation_total)
        )
    if len(verified) < limit:
        raise RuntimeError(f"only {len(verified)} MBPP tasks passed strict local verification; requested {limit}")

    prompts_en = [clean_mbpp_prompt(row["text"]) for row, *_ in verified]
    prompts_sw = [clean_translation(text) for text in translate_many_guarded(translator, prompts_en)]
    roundtrips = back_translate_many(translator, prompts_sw, roundtrip_cache)
    accepted = []
    for item, prompt_en, prompt_sw, roundtrip in zip(verified, prompts_en, prompts_sw, roundtrips):
        score, anchors_verified = semantic_quality(prompt_en, roundtrip)
        if score >= 0.40 and anchors_verified:
            accepted.append((item, prompt_en, preserve_technical_terms(prompt_en, prompt_sw), score))
    accepted.sort(key=lambda item: (-item[3], int(item[0][0]["task_id"])))
    if len(accepted) < limit:
        raise RuntimeError(
            f"only {len(accepted)} MBPP translations passed round-trip semantic filtering; requested {limit}"
        )

    # NLLB is a prose teacher, never the code authority.  Embed the already
    # filtered task translation in a project-authored Kiswahili frame.
    explanation_candidates = accepted[: min(len(accepted), limit + 150)]
    explanations_en = [task_specific_explanation(item[1]) for item in explanation_candidates]
    explanations_sw = [
        swahili_task_explanation(item[2]) for item in explanation_candidates
    ]
    localized = []
    for item, explanation_en, explanation_sw in zip(
        explanation_candidates, explanations_en, explanations_sw
    ):
        # The task-specific portion is exactly the already round-tripped prompt
        # translation.  The surrounding Kiswahili sentence is authored and
        # regression-tested, not machine translated.  Record this composition
        # honestly instead of scoring the fixed frame with a lexical metric.
        explanation_score = item[3]
        if explanation_score < 0.45:
            continue
        localized.append(
            (
                item,
                explanation_en,
                explanation_sw,
                explanation_score,
            )
        )
    localized.sort(
        key=lambda item: (
            -min(item[0][3], item[3]),
            int(item[0][0][0]["task_id"]),
        )
    )
    localized = localized[:limit]
    if len(localized) < limit:
        raise RuntimeError(
            f"only {len(localized)} task-specific explanations passed round-trip filtering; requested {limit}"
        )

    tasks: list[VerifiedTask] = []
    for (
        ((row, code, tests_hash, test_count, mutation_killed, mutation_total), prompt_en, prompt_sw, score),
        explanation_en,
        explanation_sw,
        explanation_score,
    ) in localized:
        identifiers = sorted(set(re.findall(r"\b(?:def|class)\s+([A-Za-z_]\w*)", code)))
        identifier_note = f" Required identifiers: {', '.join(identifiers)}." if identifiers else ""
        tasks.append(VerifiedTask(
            parallel_id=f"mbpp:{row['task_id']}", source="Muennighoff/mbpp full",
            runtime="python", kind="code_generation", prompt_en=prompt_en + identifier_note,
            prompt_sw=prompt_sw + identifier_note,
            prompt_mix=code_switch_swahili(prompt_sw) + identifier_note,
            code=code, tests_sha256=tests_hash, hidden_test_count=test_count,
            explanation_en=explanation_en, explanation_sw=explanation_sw,
            explanation_mix=code_switch_swahili(explanation_sw),
            translation_score=score, translation_anchors_verified=True,
            explanation_translation_score=explanation_score,
            explanation_anchors_verified=True,
            explanation_verification_method=(
                "project-authored Kiswahili frame plus independently round-tripped task translation"
            ),
            mutation_killed=mutation_killed,
            mutation_total=mutation_total,
        ))
    return tasks


def humaneval_tasks(
    limit: int,
    translator: Translator | CTranslate2Teacher,
    roundtrip_cache: Path,
) -> list[VerifiedTask]:
    """Load, execute, localize, and independently filter HumanEval tasks."""
    if limit <= 0:
        return []
    from datasets import load_dataset

    verified = []
    for row in load_dataset("openai/openai_humaneval", split="test"):
        try:
            tree = ast.parse(row["prompt"])
            function = next(node for node in tree.body if isinstance(node, ast.FunctionDef))
            contract = ast.get_docstring(function, clean=True)
            if not contract:
                continue
            requirement = (
                f"Implement {row['entry_point']} according to this contract: "
                + re.sub(r"\s+", " ", contract).strip()
            )
            code = f"{row['prompt'].rstrip()}\n{row['canonical_solution'].rstrip()}"
            tests = f"{row['test'].rstrip()}\ncheck({row['entry_point']})"
            tests_hash, test_count = verify_program("python", code, tests)
        except (StopIteration, ValueError, SyntaxError, subprocess.TimeoutExpired):
            continue
        verified.append((row, requirement, code, tests_hash, test_count))

    prompts_en = [item[1] for item in verified]
    prompts_sw = [
        preserve_technical_terms(source, clean_translation(target))
        for source, target in zip(prompts_en, translate_many_guarded(translator, prompts_en))
    ]
    prompt_roundtrips = back_translate_many(translator, prompts_sw, roundtrip_cache)
    prompt_accepted = []
    for item, prompt_sw, roundtrip in zip(verified, prompts_sw, prompt_roundtrips):
        score, anchors = semantic_quality(item[1], roundtrip)
        if score >= 0.40 and anchors:
            prompt_accepted.append((item, prompt_sw, score))

    explanations_en = [task_specific_explanation(item[0][1]) for item in prompt_accepted]
    explanations_sw = [
        swahili_task_explanation(item[1]) for item in prompt_accepted
    ]
    localized = []
    for item, explanation_en, explanation_sw in zip(
        prompt_accepted, explanations_en, explanations_sw
    ):
        explanation_score = item[2]
        if explanation_score >= 0.45:
            localized.append((item, explanation_en, explanation_sw, explanation_score))
    localized.sort(
        key=lambda item: (-min(item[0][2], item[3]), item[0][0][0]["task_id"])
    )
    localized = localized[:limit]
    if len(localized) < limit:
        raise RuntimeError(
            f"only {len(localized)} HumanEval tasks passed executable and translation filters; requested {limit}"
        )

    tasks = []
    for (
        ((row, prompt_en, code, tests_hash, test_count), prompt_sw, prompt_score),
        explanation_en,
        explanation_sw,
        explanation_score,
    ) in localized:
        identifier_note = f" Required identifier: {row['entry_point']}."
        tasks.append(VerifiedTask(
            parallel_id=f"humaneval:{row['task_id']}",
            source="openai/openai_humaneval",
            runtime="python",
            kind="code_generation",
            prompt_en=prompt_en + identifier_note,
            prompt_sw=prompt_sw + identifier_note,
            prompt_mix=code_switch_swahili(prompt_sw) + identifier_note,
            code=code,
            tests_sha256=tests_hash,
            hidden_test_count=test_count,
            explanation_en=explanation_en,
            explanation_sw=explanation_sw,
            explanation_mix=code_switch_swahili(explanation_sw),
            translation_score=prompt_score,
            translation_anchors_verified=True,
            explanation_translation_score=explanation_score,
            explanation_anchors_verified=True,
            explanation_verification_method=(
                "project-authored Kiswahili frame plus independently round-tripped task translation"
            ),
            mutation_killed=0,
            mutation_total=0,
        ))
    return tasks


def split_tasks(tasks: list[VerifiedTask]) -> tuple[list[VerifiedTask], list[VerifiedTask]]:
    train, validation = [], []
    for task in tasks:
        bucket = int(digest(task.parallel_id)[:8], 16) % 20
        (validation if bucket == 0 else train).append(task)
    if not train or not validation:
        raise RuntimeError("deterministic source split produced an empty partition")
    return train, validation


def ratio_counts(total: int) -> dict[str, int]:
    english = round(total * 0.65)
    swahili = round(total * 0.20)
    return {"en": english, "sw": swahili, "sw_mix": total - english - swahili}


def assistant_answer(task: VerifiedTask, language: str) -> str:
    explanation = {
        "en": task.explanation_en,
        "sw": task.explanation_sw,
        "sw_mix": task.explanation_mix,
    }[language].strip()
    return f"```{language_name(task.runtime)}\n{task.code}\n```\n\n{explanation}"


def build_record(task: VerifiedTask, language: str, variant: int) -> dict:
    wrappers = {"en": EN_WRAPPERS, "sw": SW_WRAPPERS, "sw_mix": MIX_WRAPPERS}[language]
    requirement = {"en": task.prompt_en, "sw": task.prompt_sw, "sw_mix": task.prompt_mix}[language]
    prompt = wrappers[variant % len(wrappers)].format(
        requirement=requirement, runtime=language_name(task.runtime)
    )
    answer = assistant_answer(task, language)
    fences = FENCE_RE.findall(answer)
    if len(fences) != 1 or fences[0].strip() != task.code.strip():
        raise RuntimeError(f"code-lock or code-fence failure for {task.parallel_id}:{language}:{variant}")
    return {
        "schema": "codefellow-parallel-sft-v2",
        "source_id": task.parallel_id,
        "parallel_id": task.parallel_id,
        "source": task.source,
        "language": language,
        "kind": task.kind,
        "runtime": task.runtime,
        "variant": variant,
        "code_sha256": digest(task.code.strip()),
        "verification": {
            "passed": True,
            "tests_sha256": task.tests_sha256,
            "hidden_test_count": task.hidden_test_count,
            "code_authority": "locally executed reference; translation not used for code",
            "translation_semantic_score": task.translation_score,
            "translation_anchors_verified": task.translation_anchors_verified,
            "explanation_translation_semantic_score": task.explanation_translation_score,
            "explanation_translation_anchors_verified": task.explanation_anchors_verified,
            "explanation_verification_method": task.explanation_verification_method,
            "mutation_killed": task.mutation_killed,
            "mutation_total": task.mutation_total,
        },
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": answer},
        ],
    }


def expand_partition(tasks: list[VerifiedTask], total: int, seed: int) -> list[dict]:
    counts = ratio_counts(total)
    for language, count in counts.items():
        if count < len(tasks):
            raise ValueError(f"{language} quota {count} cannot cover all {len(tasks)} parallel tasks")
    records: list[dict] = []
    ordered = sorted(tasks, key=lambda task: digest(f"{seed}:{task.parallel_id}"))
    for language, count in counts.items():
        for index in range(count):
            task = ordered[index % len(ordered)]
            variant = index // len(ordered)
            records.append(build_record(task, language, variant))
    random.Random(seed).shuffle(records)
    return records


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def summarize(rows: list[dict]) -> dict:
    hidden_tests = {
        row["parallel_id"]: row["verification"]["hidden_test_count"] for row in rows
    }
    mutations = {
        row["parallel_id"]: (
            row["verification"]["mutation_killed"],
            row["verification"]["mutation_total"],
        )
        for row in rows
    }
    return {
        "records": len(rows),
        "languages": dict(Counter(row["language"] for row in rows)),
        "kinds": dict(Counter(row["kind"] for row in rows)),
        "runtimes": dict(Counter(row["runtime"] for row in rows)),
        "parallel_tasks": len({row["parallel_id"] for row in rows}),
        "hidden_tests_across_parallel_tasks": sum(hidden_tests.values()),
        "mutation_killed": sum(item[0] for item in mutations.values()),
        "mutation_total": sum(item[1] for item in mutations.values()),
        "verified_records": sum(row["verification"]["passed"] for row in rows),
    }


def main() -> int:
    args = parse_args()
    if not 8_000 <= args.total_records <= 15_000:
        raise SystemExit("total-records must be between 8,000 and 15,000")
    if not 0.01 <= args.validation_fraction <= 0.20:
        raise SystemExit("validation-fraction must be between 0.01 and 0.20")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    cache = args.translation_cache or args.output_dir / "translation-cache.json"
    translator = (
        CTranslate2Teacher(args.ct2_translation_model, cache, args.translation_threads)
        if args.ct2_translation_model
        else Translator(args.translation_model, cache)
    )
    roundtrip_cache = args.output_dir / "roundtrip-cache.json"
    tasks = (
        curriculum_tasks()
        + mbpp_tasks(args.mbpp_limit, translator, roundtrip_cache, args.seed)
        + humaneval_tasks(args.humaneval_limit, translator, roundtrip_cache)
    )
    train_tasks, validation_tasks = split_tasks(tasks)
    validation_total = round(args.total_records * args.validation_fraction)
    train = expand_partition(train_tasks, args.total_records - validation_total, args.seed)
    validation = expand_partition(validation_tasks, validation_total, args.seed + 1)
    write_jsonl(args.output_dir / "train.jsonl", train)
    write_jsonl(args.output_dir / "validation.jsonl", validation)
    combined = train + validation
    sources = {
        "Muennighoff/mbpp": "CC-BY-4.0; reference code locally executed against hidden tests",
        "CodeFellow curriculum": "project-authored; Python and JavaScript references locally executed",
        str(args.ct2_translation_model or args.translation_model): "Kiswahili prose teacher only",
    }
    evaluation_exclusions = [
        "evals/cases.py", "evals/kiswahili/tasks.json", "metadata.json test_prompts"
    ]
    if args.humaneval_limit:
        sources["openai/openai_humaneval"] = (
            "MIT; reference code locally executed against hidden tests"
        )
        evaluation_exclusions.append(
            "HumanEval (training source; never report as a post-training benchmark)"
        )
    manifest = {
        "schema": "codefellow-parallel-sft-v2",
        "seed": args.seed,
        "total": len(combined),
        "target_ratios": {"en": 0.65, "sw": 0.20, "sw_mix": 0.15},
        "train": summarize(train),
        "validation": summarize(validation),
        "combined": summarize(combined),
        "code_lock": "SHA-256-identical executable code across en/sw/sw_mix for every parallel_id",
        "verification": "Every reference compiled/executed against hidden tests; dynamic task prose passes anchor and round-trip checks; the Kiswahili explanation frame is project-authored and regression-tested",
        "translation_role": "NLLB teacher for Kiswahili prose only; never code authority",
        "sources": sources,
        "evaluation_exclusions": evaluation_exclusions,
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
