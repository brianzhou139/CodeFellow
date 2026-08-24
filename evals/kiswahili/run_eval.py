#!/usr/bin/env python3
"""Run CodeFellow's English/Kiswahili/code-switching paired evaluation.

The harness talks only to a local llama.cpp OpenAI-compatible endpoint. Code
answers run in short-lived, resource-limited subprocesses; explanation answers
are graded against explicit per-language concept rubrics.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import resource
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from response_contract import normalize_code_response, normalize_explanation_response
from translation_backend import CTranslate2NllbTranslator, NllbTranslator


SYSTEM_PROMPT = """You are CodeFellow, an offline programming tutor.
Follow the requested response language exactly while keeping programming
identifiers and language keywords unchanged. Produce correct, minimal code
using only the standard library. Never access the network, filesystem, shell,
environment variables, or external processes."""

LANGUAGE_INSTRUCTIONS = {
    "en": {
        "code": (
            "Respond in English. Return exactly one fenced {runtime} code block "
            "containing the complete implementation. After the block, add one "
            "short English sentence explaining the approach. Do not include tests."
        ),
        "explanation": (
            "Respond in English in at most 90 words. Answer every clause in the question, including "
            "each requested comparison, consequence, constraint, or example. Preserve exact operators, "
            "identifiers, exception names, and complexity notation."
        ),
    },
    "sw": {
        "code": (
            "Jibu kwa Kiswahili. Toa kizuizi kimoja tu cha msimbo wa {runtime} "
            "chenye utekelezaji kamili. Baada ya kizuizi, ongeza sentensi moja "
            "fupi ya Kiswahili inayoeleza mbinu. Usijumuishe majaribio."
        ),
        "explanation": "Jibu kwa Kiswahili kwa maneno yasiyozidi 90.",
    },
    "sw_mix": {
        "code": (
            "Jibu kwa Kiswahili, lakini tumia English programming terms za kawaida kama function, "
            "variable, array, list, loop, class, object, API, database, compiler, runtime, pointer na "
            "recursion. Toa fenced {runtime} code block moja tu yenye implementation kamili. Baada "
            "ya block, ongeza sentensi moja fupi ya Kiswahili. Usijumuishe tests."
        ),
        "explanation": (
            "Jibu kwa maneno yasiyozidi 90 ukitumia Kiswahili katika maelezo na English programming "
            "terms pale programmers wanapozitumia kawaida."
        ),
    },
    "af": {
        "code": (
            "Antwoord in Afrikaans. Gee presies een omheinde {runtime}-kodeblok "
            "met die volledige implementering. Voeg ná die blok een kort "
            "Afrikaanse sin by wat die benadering verduidelik. Moenie toetse insluit nie."
        ),
        "explanation": "Antwoord in Afrikaans in hoogstens 90 woorde.",
    },
    "af_mix": {
        "code": (
            "Antwoord in Afrikaans, maar behou gewone Engelse programmeringsterme soos function, "
            "variable, array, list, loop, class, object, API, database, compiler, runtime, pointer en "
            "recursion. Gee presies een omheinde {runtime}-code block met die volledige implementation. "
            "Voeg ná die block een kort Afrikaanse sin by. Moenie tests insluit nie."
        ),
        "explanation": (
            "Antwoord in hoogstens 90 woorde met Afrikaanse onderrigprosa en die gewone Engelse "
            "programmeringsterme waar hulle natuurlik pas."
        ),
    },
    "ar": {
        "code": (
            "أجب باللغة العربية. قدّم كتلة شفرة {runtime} واحدة فقط محاطة "
            "بعلامات Markdown وتحتوي على التنفيذ الكامل. بعد الكتلة، أضف جملة "
            "عربية قصيرة واحدة تشرح النهج. لا تضمّن اختبارات أو أمثلة تشغيل."
        ),
        "explanation": "أجب باللغة العربية في 90 كلمة كحد أقصى.",
    },
    "ha": {
        "code": (
            "Ka amsa da Hausa. Ka bayar da katangar lambar {runtime} guda ɗaya "
            "tak mai ɗauke da cikakken aiwatarwa. Bayan katangar, ƙara gajeriyar "
            "jimlar Hausa guda ɗaya da ke bayyana hanyar. Kada ka haɗa gwaje-gwaje "
            "ko misalan kira."
        ),
        "explanation": "Ka amsa da Hausa cikin kalmomi 90 ko ƙasa da haka.",
    },
    "yo": {
        "code": (
            "Dáhùn ní èdè Yorùbá. Fi àkọsílẹ̀ kóòdù {runtime} kan ṣoṣo hàn, "
            "tí ó ní gbogbo ìmúlò náà. Lẹ́yìn àkọsílẹ̀ kóòdù, fi gbólóhùn "
            "Yorùbá kúkúrú kan ṣàlàyé ọ̀nà náà. Má fi ìdánwò tàbí àpẹẹrẹ ìpè sí i."
        ),
        "explanation": "Dáhùn ní èdè Yorùbá pẹ̀lú ọ̀rọ̀ 90 tàbí kéré sí i.",
    },
}

REVIEW_INSTRUCTIONS = {
    "en": (
        "Review your draft against every stated requirement. Check empty input, duplicates, "
        "normalization, invalid values, and boundary cases when relevant. Return only the complete "
        "corrected implementation; do not include tests or example calls."
    ),
    "sw": (
        "Kagua draft yako dhidi ya kila sharti lililotajwa. Angalia input tupu, duplicates, "
        "normalization, invalid values na boundary cases pale zinapohusika. Rudisha implementation "
        "kamili iliyosahihishwa pekee; usijumuishe tests wala example calls."
    ),
}

LANGUAGE_WORDS = {
    "en": {
        "the", "and", "a", "an", "is", "are", "this", "that", "with", "for",
        "to", "of", "in", "when", "while", "returns", "uses", "function",
        "value", "list", "code", "because", "otherwise", "each",
    },
    "sw": {
        "na", "kwa", "ya", "wa", "katika", "ni", "ili", "hii", "hili", "huu",
        "ikiwa", "vinginevyo", "inatumia", "hutumia", "inarejesha", "rejesha",
        "hupitia", "huongeza", "huondoa", "kila", "orodha", "thamani", "nambari",
        "kamba", "kipengele", "vipengele", "muda", "kumbukumbu", "msimbo",
        "kitendakazi", "tatizo", "suluhisho", "ambacho", "bila", "kisha",
        "hivyo", "sababu", "salama", "sahihi", "tofauti", "kubwa", "ndogo",
    },
    "af": {
        "die", "en", "van", "om", "te", "vir", "met", "as", "wat", "hierdie",
        "gebruik", "funksie", "kode", "lys", "waarde", "getal", "string", "fout",
        "korrek", "terug", "deur", "elke", "indien", "anders", "voeg", "verwyder",
        "tyd", "geheue", "oplossing", "verander", "sonder", "omdat", "word",
        "kan", "moet", "dan", "een", "ook", "veilig", "groter", "kleiner",
    },
    "ar": {
        "في", "من", "إلى", "على", "أن", "إذا", "وإلا", "لأن", "هذا",
        "هذه", "الدالة", "القيمة", "القيم", "قائمة", "مصفوفة", "تعيد",
        "يرجع", "استخدم", "باستخدام", "كل", "عنصر", "عناصر", "صحيح",
        "النوع", "الوقت", "التعقيد", "الحالة", "الأساسية", "يتوقف",
        "آمن", "خطأ", "الشفرة", "الكود", "الحل", "المدخلات", "النتيجة",
    },
    "ha": {
        "da", "na", "a", "ya", "ta", "su", "ko", "idan", "saboda",
        "wannan", "cewa", "don", "cikin", "daga", "zuwa", "kowane",
        "aiki", "mayar", "jerin", "ƙima", "ƙimomi", "lamba", "lambobi",
        "rubutu", "kuskure", "gyara", "amfani", "lokaci", "tasha",
        "tushen", "shigarwa", "sakamako", "hanya", "bincika", "aminci",
        "ba", "ne", "ce", "yana", "tana", "suna", "dole", "kuma",
    },
    "yo": {
        "àti", "ní", "ti", "sí", "lati", "láti", "fún", "pẹ̀lú", "bí",
        "tí", "nítorí", "yìí", "náà", "iṣẹ́", "àwọn", "ọ̀nà", "kóòdù",
        "àtòjọ", "iye", "ìye", "nọ́mbà", "ọ̀rọ̀", "padà", "dáhùn",
        "lo", "lò", "gbogbo", "kọ̀ọ̀kan", "àṣìṣe", "ṣe", "ṣàlàyé",
        "àkókò", "ìdúró", "ìpilẹ̀", "àbájáde", "ìwọlé", "àìléwu",
        "kò", "ó", "jẹ́", "má", "nítorí náà", "lẹ́yìn", "nígbà",
    },
}

LANGUAGE_WORDS["af_mix"] = LANGUAGE_WORDS["af"]
LANGUAGE_WORDS["sw_mix"] = LANGUAGE_WORDS["sw"]
CODE_SWITCH_TERMS = {
    "function", "variable", "array", "list", "loop", "class", "object", "api",
    "database", "compiler", "runtime", "pointer", "recursion", "code", "debug",
    "test", "tests", "input", "output", "return", "type", "scope", "stack",
}
AFRIKAANS_TO_CODING_TERM = {
    "funksies": "functions", "funksie": "function",
    "veranderlikes": "variables", "veranderlike": "variable",
    "skikkings": "arrays", "skikking": "array",
    "lyste": "lists", "lys": "list",
    "lusse": "loops", "lus": "loop",
    "klasse": "classes", "klas": "class",
    "objekte": "objects", "objek": "object",
    "databasisse": "databases", "databasis": "database",
    "samestellers": "compilers", "samesteller": "compiler",
    "looptyd": "runtime", "wysers": "pointers", "wyser": "pointer",
    "rekursie": "recursion", "kode": "code",
}
SWAHILI_TO_CODING_TERM = {
    "vitendakazi": "functions", "kitendakazi": "function",
    "vigeu": "variables", "kigeu": "variable", "safu": "array",
    "orodha": "list", "mizunguko": "loops", "mzunguko": "loop",
    "madarasa": "classes", "darasa": "class", "vitu": "objects",
    "kitu": "object", "kanzidata": "database", "mkusanyaji": "compiler",
    "viashiria": "pointers", "kiashiria": "pointer", "ujirudiaji": "recursion",
    "msimbo": "code",
}

CODE_BLOCK_RE = re.compile(
    r"```(?:python|py|javascript|js)?\s*\n(?P<code>.*?)```", re.IGNORECASE | re.DOTALL
)
OPEN_CODE_BLOCK_RE = re.compile(
    r"```(?:python|py|javascript|js)?\s*\n(?P<code>.*)$", re.IGNORECASE | re.DOTALL
)
ANY_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
TOKEN_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
UNSAFE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bimport\s+(?:os|sys|subprocess|socket|pathlib|urllib|requests)\b",
        r"\bfrom\s+(?:os|sys|subprocess|socket|pathlib|urllib)\b",
        r"\bopen\s*\(",
        r"\b(?:eval|exec|compile|__import__)\s*\(",
        r"child_process",
        r"require\s*\(\s*['\"](?:fs|net|http|https|child_process|os)['\"]",
        r"process\.(?:env|exit|kill)",
    )
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=Path, default=Path(__file__).with_name("tasks.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8181/v1/chat/completions")
    parser.add_argument("--model", default="Qwen2.5-Coder-3B-Instruct-Q4_K_M")
    parser.add_argument("--languages", default="en,sw,sw_mix")
    parser.add_argument(
        "--task-ids",
        default=None,
        help="Optional comma-separated task IDs; preserves their order in the task file.",
    )
    parser.add_argument(
        "--translations",
        type=Path,
        default=None,
        help="Optional JSON object mapping task IDs to additional prompt/rubric fields.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--code-max-tokens", type=int, default=240)
    parser.add_argument("--explanation-max-tokens", type=int, default=160)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--fresh", action="store_true", help="Ignore an existing checkpoint.")
    parser.add_argument(
        "--chat-template-kwargs",
        type=json.loads,
        default=None,
        help="JSON object passed to llama.cpp as chat_template_kwargs.",
    )
    parser.add_argument(
        "--model-only",
        action="store_true",
        help="Fail closed unless responses come directly from one model call with no translation, review, or postprocessing.",
    )
    parser.add_argument(
        "--application-contract",
        action="store_true",
        help="Evaluate CodeFellow's deterministic bare-code formatting and demo-removal layer.",
    )
    parser.add_argument(
        "--self-review",
        action="store_true",
        help="Use a second local model pass to review code against the stated requirements.",
    )
    parser.add_argument(
        "--translate-then-solve",
        action="store_true",
        help="Locally restate Kiswahili code requirements in English before solving them.",
    )
    parser.add_argument(
        "--nllb-model",
        default=None,
        help="Local NLLB model path/name for Kiswahili-to-English requirement translation.",
    )
    parser.add_argument(
        "--ct2-nllb-model",
        default=None,
        help="Local CPU-int8 CTranslate2 NLLB directory (production laptop path).",
    )
    parser.add_argument(
        "--nllb-roundtrip-explanations",
        action="store_true",
        help="Solve explanation tasks in English, then translate the answer back locally.",
    )
    return parser.parse_args()


def api_request(endpoint: str, payload: dict, attempts: int = 3) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            if attempt < attempts:
                time.sleep(attempt * 2)
    raise RuntimeError(f"local inference failed after {attempts} attempts: {last_error}")


def extract_code(content: str) -> tuple[str | None, bool]:
    match = CODE_BLOCK_RE.search(content)
    if match:
        return match.group("code").strip(), True
    # Preserve technical scoring when a model emits a valid opening fence but
    # forgets the closing fence. Formatting compliance is recorded separately.
    open_match = OPEN_CODE_BLOCK_RE.search(content)
    if open_match:
        return open_match.group("code").strip(), False
    return None, False


def non_code_text(content: str) -> str:
    return ANY_CODE_BLOCK_RE.sub(" ", content)


def language_evidence(content: str, language: str) -> tuple[int, list[str]]:
    words = {word.casefold() for word in TOKEN_RE.findall(non_code_text(content))}
    hits = sorted(words & LANGUAGE_WORDS[language])
    return len(hits), hits


def code_switch_prompt(text: str, language: str) -> str:
    mapping = AFRIKAANS_TO_CODING_TERM if language == "af_mix" else SWAHILI_TO_CODING_TERM
    pattern = re.compile(
        r"\b(" + "|".join(map(re.escape, mapping)) + r")\b",
        re.IGNORECASE,
    )
    return pattern.sub(lambda match: mapping[match.group(0).casefold()], text)


def code_switch_evidence(content: str) -> list[str]:
    words = {word.casefold() for word in TOKEN_RE.findall(non_code_text(content))}
    return sorted(words & CODE_SWITCH_TERMS)


def safe_limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))


def run_code(task: dict, code: str | None) -> dict:
    if not code:
        return {"passed": False, "reason": "missing fenced code block", "stderr": ""}
    for pattern in UNSAFE_PATTERNS:
        if pattern.search(code):
            return {"passed": False, "reason": f"unsafe code pattern: {pattern.pattern}", "stderr": ""}
    for forbidden in task.get("forbid", []):
        call_name = forbidden.rstrip("(").strip()
        if call_name.startswith("."):
            pattern = re.compile(re.escape(call_name) + r"\s*\(", re.IGNORECASE)
        else:
            pattern = re.compile(
                r"(?<![\w$])" + re.escape(call_name) + r"\s*\(", re.IGNORECASE
            )
        if pattern.search(code):
            return {"passed": False, "reason": f"forbidden construct: {forbidden}", "stderr": ""}

    runtime = task["runtime"]
    suffix = ".py" if runtime == "python" else ".js"
    tests = "\n".join(task["tests"])
    sentinel = "print('CODEFELLOW_TEST_PASS')" if runtime == "python" else "console.log('CODEFELLOW_TEST_PASS');"
    source = f"{code}\n\n{tests}\n{sentinel}\n"

    with tempfile.TemporaryDirectory(prefix="codefellow-eval-") as temp_dir:
        path = Path(temp_dir) / f"candidate{suffix}"
        path.write_text(source, encoding="utf-8")
        command = [sys.executable, "-I", str(path)] if runtime == "python" else ["/usr/bin/node", "--no-warnings", str(path)]
        started = time.perf_counter()
        try:
            process = subprocess.run(
                command,
                cwd=temp_dir,
                env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
                text=True,
                capture_output=True,
                timeout=5,
                preexec_fn=safe_limits,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"passed": False, "reason": "test timeout", "stderr": ""}
        duration = time.perf_counter() - started
        passed = process.returncode == 0 and "CODEFELLOW_TEST_PASS" in process.stdout
        output_lines = [line for line in process.stdout.splitlines() if line.strip()]
        return {
            "passed": passed,
            "reason": "passed" if passed else f"test process exited {process.returncode}",
            "side_effect_free": output_lines == ["CODEFELLOW_TEST_PASS"],
            "duration_seconds": round(duration, 4),
            "stdout": process.stdout[-1000:],
            "stderr": process.stderr[-1500:],
        }


def grade_explanation(task: dict, language: str, content: str) -> dict:
    rubric_language = {"af_mix": "af", "sw_mix": "sw"}.get(language, language)
    patterns = task[f"rubric_{rubric_language}"]
    matches = [bool(re.search(pattern, content, re.IGNORECASE)) for pattern in patterns]
    score = sum(matches) / len(matches)
    return {
        "passed": score >= 0.75,
        "score": round(score, 4),
        "concept_matches": matches,
        "patterns": patterns,
    }


def response_key(task_id: str, language: str) -> str:
    return f"{task_id}:{language}"


def write_checkpoint(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def summarize(tasks: list[dict], results: list[dict], languages: list[str]) -> dict:
    summary: dict[str, dict] = {}
    for language in languages:
        rows = [row for row in results if row["language"] == language and not row.get("error")]
        code_rows = [row for row in rows if row["kind"] == "code"]
        explanation_rows = [row for row in rows if row["kind"] == "explanation"]
        durations = [row["inference_seconds"] for row in rows]
        completion_tokens = [row["completion_tokens"] for row in rows if row["completion_tokens"] is not None]
        summary[language] = {
            "responses": len(rows),
            "code_passed": sum(row["technical_pass"] for row in code_rows),
            "code_total": len(code_rows),
            "code_pass_rate": round(sum(row["technical_pass"] for row in code_rows) / len(code_rows), 4) if code_rows else 0,
            "format_compliant": sum(row.get("format_compliant", False) for row in code_rows),
            "format_compliance_rate": round(sum(row.get("format_compliant", False) for row in code_rows) / len(code_rows), 4) if code_rows else 0,
            "side_effect_free": sum(row.get("grade", {}).get("side_effect_free", False) for row in code_rows),
            "side_effect_free_rate": round(sum(row.get("grade", {}).get("side_effect_free", False) for row in code_rows) / len(code_rows), 4) if code_rows else 0,
            "explanations_passed": sum(row["technical_pass"] for row in explanation_rows),
            "explanations_total": len(explanation_rows),
            "explanation_pass_rate": round(sum(row["technical_pass"] for row in explanation_rows) / len(explanation_rows), 4) if explanation_rows else 0,
            "overall_passed": sum(row["technical_pass"] for row in rows),
            "overall_total": len(rows),
            "overall_pass_rate": round(sum(row["technical_pass"] for row in rows) / len(rows), 4) if rows else 0,
            "language_adherent": sum(row["language_adherent"] for row in rows),
            "language_adherence_rate": round(sum(row["language_adherent"] for row in rows) / len(rows), 4) if rows else 0,
            "mean_inference_seconds": round(statistics.mean(durations), 3) if durations else None,
            "median_inference_seconds": round(statistics.median(durations), 3) if durations else None,
            "mean_completion_tokens": round(statistics.mean(completion_tokens), 2) if completion_tokens else None,
            "total_completion_tokens": sum(completion_tokens),
        }

    by_key = {(row["task_id"], row["language"]): row for row in results if not row.get("error")}
    complete_tasks = [
        task for task in tasks if all((task["id"], language) in by_key for language in languages)
    ]
    all_pass = sum(
        all(by_key[(task["id"], language)]["technical_pass"] for language in languages)
        for task in complete_tasks
    )
    localized_parity = {}
    if "en" in languages:
        for language in (lang for lang in languages if lang != "en"):
            localized_parity[language] = {
                "same_outcome_as_english": sum(
                    by_key[(task["id"], language)]["technical_pass"]
                    == by_key[(task["id"], "en")]["technical_pass"]
                    for task in complete_tasks
                ),
                "localized_pass_english_pass": sum(
                    by_key[(task["id"], language)]["technical_pass"]
                    and by_key[(task["id"], "en")]["technical_pass"]
                    for task in complete_tasks
                ),
                "localized_fail_english_pass": sum(
                    not by_key[(task["id"], language)]["technical_pass"]
                    and by_key[(task["id"], "en")]["technical_pass"]
                    for task in complete_tasks
                ),
            }
    return {
        "languages": summary,
        "complete_language_sets": len(complete_tasks),
        "all_languages_passed": all_pass,
        "all_languages_pass_rate": round(all_pass / len(complete_tasks), 4) if complete_tasks else 0,
        "localized_parity": localized_parity,
    }


def main() -> int:
    args = parse_args()
    if args.model_only and any(
        (
            args.application_contract,
            args.self_review,
            args.translate_then_solve,
            args.nllb_model,
            args.ct2_nllb_model,
            args.nllb_roundtrip_explanations,
        )
    ):
        raise SystemExit("--model-only cannot be combined with translation, review, or application-contract options")
    if args.nllb_model and args.ct2_nllb_model:
        raise SystemExit("choose either --nllb-model or --ct2-nllb-model, not both")
    translator_id = args.ct2_nllb_model or args.nllb_model
    nllb_translator = (
        CTranslate2NllbTranslator(args.ct2_nllb_model)
        if args.ct2_nllb_model
        else NllbTranslator(args.nllb_model)
        if args.nllb_model
        else None
    )
    languages = [language.strip() for language in args.languages.split(",") if language.strip()]
    invalid = [language for language in languages if language not in LANGUAGE_INSTRUCTIONS]
    if invalid:
        raise SystemExit(f"unsupported language codes: {invalid}")

    tasks = json.loads(args.tasks.read_text(encoding="utf-8"))
    if args.translations is not None:
        translations = json.loads(args.translations.read_text(encoding="utf-8"))
        by_id = {task["id"]: task for task in tasks}
        unknown_translation_ids = sorted(set(translations) - set(by_id))
        if unknown_translation_ids:
            raise SystemExit(f"translations reference unknown task IDs: {unknown_translation_ids}")
        for task_id, fields in translations.items():
            by_id[task_id].update(fields)
    if args.task_ids:
        requested_ids = [task_id.strip() for task_id in args.task_ids.split(",") if task_id.strip()]
        requested_set = set(requested_ids)
        available_ids = {task["id"] for task in tasks}
        unknown_task_ids = sorted(requested_set - available_ids)
        if unknown_task_ids:
            raise SystemExit(f"unknown task IDs: {unknown_task_ids}")
        tasks = [task for task in tasks if task["id"] in requested_set]
    if args.limit is not None:
        tasks = tasks[: args.limit]

    document = {
        "schema": "codefellow-english-kiswahili-codeswitch-eval-v3",
        "model": args.model,
        "endpoint": args.endpoint,
        "seed": args.seed,
        "languages": languages,
        "task_count": len(tasks),
        "chat_template_kwargs": args.chat_template_kwargs,
        "model_only": args.model_only,
        "application_contract": args.application_contract,
        "self_review": args.self_review,
        "translate_then_solve": args.translate_then_solve,
        "nllb_model": translator_id,
        "translation_runtime": "ctranslate2-int8" if args.ct2_nllb_model else "transformers",
        "nllb_roundtrip_explanations": args.nllb_roundtrip_explanations,
        "application_prompt_strategy": (
            "nllb_sw_then_solve_en_then_render_requested_register"
            if translator_id
            else "llm_translate_sw_then_solve_en_then_render_requested_register"
            if args.translate_then_solve
            else "solve_sw_then_render_sw_mix_for_code"
            if args.application_contract
            else "direct"
        ),
        "started_at_unix": int(time.time()),
        "results": [],
    }
    if args.output.exists() and not args.fresh:
        previous = json.loads(args.output.read_text(encoding="utf-8"))
        if (
            previous.get("model") == args.model
            and previous.get("languages") == languages
            and previous.get("chat_template_kwargs") == args.chat_template_kwargs
            and previous.get("application_contract", False) == args.application_contract
            and previous.get("self_review", False) == args.self_review
            and previous.get("translate_then_solve", False) == args.translate_then_solve
            and previous.get("nllb_model") == translator_id
            and previous.get("nllb_roundtrip_explanations", False)
            == args.nllb_roundtrip_explanations
        ):
            document = previous

    completed = {
        response_key(row["task_id"], row["language"])
        for row in document.get("results", [])
        if not row.get("error")
    }
    total = len(tasks) * len(languages)
    ordinal = len(completed)

    for task in tasks:
        for language in languages:
            key = response_key(task["id"], language)
            if key in completed:
                continue
            ordinal += 1
            model_language = (
                "sw"
                if args.application_contract and language == "sw_mix" and task["kind"] == "code"
                else language
            )
            instruction = LANGUAGE_INSTRUCTIONS[model_language][task["kind"]].format(
                runtime=task.get("runtime", "text")
            )
            prompt_language = {"af_mix": "af", "sw_mix": "sw"}.get(model_language, model_language)
            localized_prompt = task[f"prompt_{prompt_language}"]
            if (
                nllb_translator is not None
                and args.nllb_roundtrip_explanations
                and task["kind"] == "explanation"
                and language in {"sw", "sw_mix"}
            ):
                localized_prompt = task["prompt_sw"]
            if model_language in {"af_mix", "sw_mix"}:
                localized_prompt = code_switch_prompt(localized_prompt, model_language)
            prompt = f"{localized_prompt}\n\n{instruction}"
            max_tokens = args.code_max_tokens if task["kind"] == "code" else args.explanation_max_tokens
            payload = {
                "model": args.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.0,
                "seed": args.seed,
                "max_tokens": max_tokens,
                "stream": False,
                "cache_prompt": True,
            }
            if args.chat_template_kwargs is not None:
                payload["chat_template_kwargs"] = args.chat_template_kwargs
            print(f"[{ordinal:02d}/{total}] {task['id']} {language}", flush=True)
            try:
                inference_seconds = 0.0
                translation_usage: dict = {}
                translated_requirement: str | None = None
                translation_substitutions: list[dict[str, str]] = []
                original_prompt = prompt
                nllb_explanation = (
                    nllb_translator is not None
                    and args.nllb_roundtrip_explanations
                    and task["kind"] == "explanation"
                    and language in {"sw", "sw_mix"}
                )
                translate_requirement = language in {"sw", "sw_mix"} and (
                    ((args.translate_then_solve or nllb_translator is not None) and task["kind"] == "code")
                    or nllb_explanation
                )
                if translate_requirement:
                    translation_started = time.perf_counter()
                    if nllb_translator is not None:
                        translated_requirement, translation_substitutions = (
                            nllb_translator.translate_requirement(localized_prompt)
                        )
                    else:
                        translation_payload = {
                            **payload,
                            "messages": [
                                {
                                    "role": "system",
                                    "content": (
                                        "Translate programming requirements from Kiswahili to concise English. "
                                        "Preserve identifiers, literals, constraints, and standard programming "
                                        "terms exactly. Return only the translated requirement."
                                    ),
                                },
                                {"role": "user", "content": localized_prompt},
                            ],
                            "max_tokens": 160,
                        }
                        translation_response = api_request(args.endpoint, translation_payload)
                        translation_usage = translation_response.get("usage") or {}
                        translated_requirement = (
                            translation_response["choices"][0]["message"]["content"].strip()
                        )
                    inference_seconds += time.perf_counter() - translation_started
                    model_language = "en"
                    instruction = LANGUAGE_INSTRUCTIONS["en"][task["kind"]].format(
                        runtime=task.get("runtime", "text")
                    )
                    prompt = f"{translated_requirement}\n\n{instruction}"
                    payload = {
                        **payload,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                    }
                started = time.perf_counter()
                response = api_request(args.endpoint, payload)
                inference_seconds += time.perf_counter() - started
                choice = response["choices"][0]
                raw_content = choice["message"]["content"]
                english_response: str | None = None
                if nllb_explanation:
                    english_response = raw_content
                    rendering_started = time.perf_counter()
                    raw_content = nllb_translator.translate_to_swahili(raw_content)
                    inference_seconds += time.perf_counter() - rendering_started
                    if language == "sw_mix":
                        raw_content, explanation_actions = normalize_explanation_response(
                            raw_content, "sw_mix"
                        )
                    else:
                        explanation_actions = []
                first_response = raw_content
                content = raw_content
                review_applied = False
                first_usage = response.get("usage") or {}
                if args.self_review and task["kind"] == "code":
                    review_payload = {
                        **payload,
                        "messages": payload["messages"]
                        + [
                            {"role": "assistant", "content": raw_content},
                            {"role": "user", "content": REVIEW_INSTRUCTIONS[model_language]},
                        ],
                    }
                    review_started = time.perf_counter()
                    response = api_request(args.endpoint, review_payload)
                    inference_seconds += time.perf_counter() - review_started
                    choice = response["choices"][0]
                    raw_content = choice["message"]["content"]
                    content = raw_content
                    review_applied = True
                contract_actions: list[str] = []
                if args.application_contract and task["kind"] == "code":
                    content, contract_actions = normalize_code_response(
                        raw_content, task["runtime"], language
                    )
                elif args.application_contract and task["kind"] == "explanation":
                    content, contract_actions = normalize_explanation_response(raw_content, language)
                    if nllb_explanation:
                        contract_actions = list(dict.fromkeys(explanation_actions + contract_actions))
                usage = response.get("usage") or {}
                code, format_compliant = extract_code(content) if task["kind"] == "code" else (None, True)
                grade = run_code(task, code) if task["kind"] == "code" else grade_explanation(task, language, content)
                evidence_count, evidence_words = language_evidence(content, language)
                mixed_terms = code_switch_evidence(content) if language in {"af_mix", "sw_mix"} else []
                required_evidence = 2 if task["kind"] == "code" else 3
                row = {
                    "task_id": task["id"],
                    "category": task["category"],
                    "kind": task["kind"],
                    "runtime": task.get("runtime"),
                    "language": language,
                    "model_prompt_language": model_language,
                    "prompt": prompt,
                    "original_prompt": original_prompt if translated_requirement else None,
                    "translated_requirement": translated_requirement,
                    "translation_substitutions": translation_substitutions,
                    "english_response": english_response,
                    "response": content,
                    "first_response": first_response if review_applied else None,
                    "self_review_applied": review_applied,
                    "raw_response": raw_content if contract_actions else None,
                    "application_contract_actions": contract_actions,
                    "finish_reason": choice.get("finish_reason"),
                    "prompt_tokens": (
                        (translation_usage.get("prompt_tokens") or 0)
                        + (first_usage.get("prompt_tokens") or 0)
                        + (usage.get("prompt_tokens") or 0)
                        if review_applied
                        else (translation_usage.get("prompt_tokens") or 0)
                        + (usage.get("prompt_tokens") or 0)
                    ),
                    "completion_tokens": (
                        (translation_usage.get("completion_tokens") or 0)
                        + (first_usage.get("completion_tokens") or 0)
                        + (usage.get("completion_tokens") or 0)
                        if review_applied
                        else (translation_usage.get("completion_tokens") or 0)
                        + (usage.get("completion_tokens") or 0)
                    ),
                    "inference_seconds": round(inference_seconds, 3),
                    "technical_pass": bool(grade["passed"]),
                    "format_compliant": format_compliant,
                    "grade": grade,
                    "language_evidence_count": evidence_count,
                    "language_evidence_words": evidence_words,
                    "code_switch_terms": mixed_terms,
                    "language_adherent": evidence_count >= required_evidence
                    and (language not in {"af_mix", "sw_mix"} or bool(mixed_terms)),
                }
            except Exception as error:  # checkpoint and continue to expose all failures
                row = {
                    "task_id": task["id"],
                    "category": task["category"],
                    "kind": task["kind"],
                    "runtime": task.get("runtime"),
                    "language": language,
                    "prompt": prompt,
                    "error": f"{type(error).__name__}: {error}",
                    "technical_pass": False,
                    "language_adherent": False,
                }
                print(f"  ERROR: {row['error']}", file=sys.stderr, flush=True)
            document.setdefault("results", []).append(row)
            document["summary"] = summarize(tasks, document["results"], languages)
            write_checkpoint(args.output, document)
            status = "PASS" if row.get("technical_pass") else "FAIL"
            print(f"  {status} | {row.get('inference_seconds', 0):.1f}s", flush=True)

    document["finished_at_unix"] = int(time.time())
    document["summary"] = summarize(tasks, document["results"], languages)
    write_checkpoint(args.output, document)
    print(json.dumps(document["summary"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
