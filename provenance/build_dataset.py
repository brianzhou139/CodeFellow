#!/usr/bin/env python3
"""Build CodeFellow's replay-protected English/Kiswahili SFT dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import subprocess
import tempfile
import time
from collections import Counter
from pathlib import Path

try:
    from .curriculum import CURRICULUM
except ImportError:  # Direct execution: python training/build_dataset.py
    from curriculum import CURRICULUM


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--codefeedback-limit", type=int, default=1800)
    parser.add_argument("--mbpp-limit", type=int, default=400)
    parser.add_argument("--swahili-mbpp-limit", type=int, default=0)
    parser.add_argument("--swahili-scaffold-limit", type=int, default=400)
    parser.add_argument("--mixed-mbpp-limit", type=int, default=400)
    parser.add_argument("--locale-repeat", type=int, default=1)
    parser.add_argument("--translation-model", default="facebook/nllb-200-distilled-600M")
    parser.add_argument("--translation-cache", type=Path)
    parser.add_argument("--seed", type=int, default=2026)
    return parser.parse_args()


def stable_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]


def run_solution(row: dict) -> None:
    with tempfile.TemporaryDirectory(prefix="codefellow-curriculum-") as directory:
        suffix = ".py" if row["runtime"] == "python" else ".js"
        path = Path(directory) / f"candidate{suffix}"
        path.write_text(f"{row['solution']}\n{row['tests']}\n", encoding="utf-8")
        command = ["python3", str(path)] if row["runtime"] == "python" else ["node", str(path)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)
        if result.returncode:
            raise RuntimeError(f"curriculum verification failed for {row['id']}:\n{result.stderr}")


SWAHILI_CODE_SWITCH_TERMS = {
    "vitendakazi": "functions", "kitendakazi": "function",
    "vigeu": "variables", "kigeu": "variable",
    "safu": "array", "orodha": "list",
    "mizunguko": "loops", "mzunguko": "loop",
    "madarasa": "classes", "darasa": "class",
    "vitu": "objects", "kitu": "object",
    "kanzidata": "database", "mkusanyaji": "compiler",
    "wakati wa utekelezaji": "runtime",
    "viashiria": "pointers", "kiashiria": "pointer",
    "ujirudiaji": "recursion", "msimbo": "code",
}


def code_switch_swahili(text: str) -> str:
    """Keep Kiswahili teaching prose while restoring normal English coding terms."""
    pattern = re.compile(
        r"\b(" + "|".join(map(re.escape, SWAHILI_CODE_SWITCH_TERMS)) + r")\b",
        re.IGNORECASE,
    )
    return pattern.sub(lambda match: SWAHILI_CODE_SWITCH_TERMS[match.group(0).casefold()], text)


MIXED_TUTORIALS = [
    (
        "function_variable",
        "Function yangu inafanya kazi, lakini sielewi kwa nini variable ya ndani haipatikani nje. Nielezee kwa urahisi.",
        "Variable inayoundwa ndani ya function huwa na local scope. Hiyo function pekee ndiyo inaweza kuitumia moja kwa moja. Ikiwa code nyingine inahitaji value hiyo, function inaweza kuitoa kwa return au unaweza kuipitisha wazi kama argument.",
    ),
    (
        "array_list",
        "Nitumie array lini na list lini? Ninaona terms zote mbili kwenye tutorials.",
        "Maana sahihi inategemea programming language. JavaScript hutumia Array kama collection ya kawaida; Python hutumia list. Usitafsiri jina bila kuangalia language, type yake na API inayopatikana.",
    ),
    (
        "loop_boundary",
        "Loop yangu inaacha item ya mwisho. Nifikirieje loop boundary?",
        "Andika invariant kwanza: ni indexes zipi tayari zimeshughulikiwa kila iteration inapoanza? Kisha linganisha stop condition na index ya mwisho. Kwa list yenye urefu n, index ya mwisho ni n - 1, lakini end-exclusive range husimama kwenye n.",
    ),
    (
        "class_object",
        "Tofauti ya vitendo kati ya class na object ni nini?",
        "Class inaeleza structure na behaviour ya instances. Object ni instance moja halisi yenye state yake. Fikiria class kama design, na kila object kama kitu maalum kilichoundwa kwa design hiyo.",
    ),
    (
        "api_database",
        "Frontend yangu izungumze moja kwa moja na database au kupitia API?",
        "Tumia API kwa kawaida. API inavalidate input, inatumia permissions na inalinda database credentials zisionekane kwa client. Browser ikifikia database moja kwa moja, security, versioning na business rules huwa vigumu kudhibiti.",
    ),
    (
        "compiler_runtime",
        "Compiler inakubali code yangu, lakini inapata crash wakati wa runtime. Hilo linawezekanaje?",
        "Compiler hukagua syntax na baadhi ya static rules. Runtime error hutokea execution path fulani inapoendeshwa, kama division by zero au kutumia value ambayo haipo. Kwa hiyo 'compiles' haimaanishi behaviour yote ni sahihi.",
    ),
    (
        "pointer",
        "Nielezee pointer katika C bila kutafsiri English term hiyo.",
        "Pointer ni variable inayohifadhi memory address. Dereferencing hutumia address hiyo kusoma au kubadilisha value. Pointer lazima ibaki valid wakati wote wa access; null, uninitialized au dangling pointer inaweza kusababisha undefined behaviour.",
    ),
    (
        "recursion",
        "Recursion yangu inaendelea mpaka stack overflow. Niangalie nini?",
        "Kila recursive call lazima isogee kuelekea base case. Hakikisha base case inatambua input sahihi na recursive step inapunguza tatizo. Moja ikikosekana, call stack itaendelea kukua.",
    ),
    (
        "debug_tests",
        "Test yangu inafeli kwa empty input tu. Nipe debugging plan, si solution nzima.",
        "Anza kwenye failing assertion na uandike contract ya empty input. Fuata execution path hiyo pekee na uone assumption ya kwanza kuhusu length au index. Ongeza guard ndogo au identity value sahihi, kisha run focused test tena.",
    ),
    (
        "type_conversion",
        "Kwa nini '2' + 3 wakati mwingine inakuwa '23'? Nataka kuelewa type conversion bug.",
        "Operand moja ni string, kwa hiyo baadhi ya runtimes huchagua concatenation badala ya numeric addition. Normalize input kwa conversion function ya language, validate matokeo, ndipo ufanye arithmetic.",
    ),
]


CODEFELLOW_SYSTEM_PROMPT = """You are CodeFellow, an offline programming tutor.
Follow the requested response language exactly while keeping programming
identifiers and language keywords unchanged. Produce correct, minimal code
using only the standard library. Never access the network, filesystem, shell,
environment variables, or external processes."""

SWAHILI_FORMAT_EXPLANATIONS = (
    "Msimbo huu hutimiza masharti na kurejesha matokeo sahihi bila output ya ziada.",
    "Suluhisho hili hupitia vipengele kwa usalama na kurejesha thamani inayotakiwa.",
    "Msimbo huu unatumia masharti ya tatizo na kutoa jibu sahihi bila mfano wa ziada.",
    "Njia hii hushughulikia input kwa usalama kisha inarejesha matokeo yanayotakiwa.",
    "Suluhisho hili ni fupi, salama na halitoi matokeo ya pembeni.",
    "Msimbo huu hufuata mahitaji na kurejesha thamani sahihi kwa kila input.",
    "Njia hii hupitia data inayohitajika na kuepuka output yoyote ya ziada.",
    "Suluhisho hili hutumia hatua chache na kurejesha matokeo kwa usahihi.",
)

MIXED_FORMAT_EXPLANATIONS = (
    "Function hii hufuata requirement na kurejesha output sahihi bila example ya ziada.",
    "Implementation hii hupitia list kwa usalama na ku-return value inayotakiwa.",
    "Loop hii hushughulikia kila input na kurejesha output sahihi bila tests za ziada.",
    "Function hii inatumia condition sahihi na ku-return matokeo yanayotakiwa.",
    "Implementation hii inalinda edge cases na kurejesha value sahihi kwa kila input.",
    "Code hii hutimiza requirement kwa usalama bila print au example output.",
    "Function hii huhifadhi order inayotakiwa na ku-return list sahihi.",
    "Implementation hii hutumia standard library pekee na haitoi output ya ziada.",
)


SWAHILI_CURRICULUM = {
    "py_median_value": {
        "prompt": "Kwa list tupu rudisha None. Kwa input yenye idadi ya values isiyo shufwa au shufwa, rudisha statistical median bila kubadilisha input.",
        "diagnostic": "Implementation inarudisha upper middle value pekee kwa list yenye size shufwa na inapata error kwa input tupu.",
        "hint": "Shughulikia empty case kwanza; length ikiwa shufwa, pata average ya values mbili za katikati baada ya ku-sort.",
        "why": "Ku-sort copy kunaacha input bila kubadilika. Length isiyo shufwa ina middle item moja; length shufwa ina mbili.",
    },
    "py_compress_runs": {
        "prompt": "Ondoa consecutive duplicate characters, lakini hifadhi repetitions ambazo hazifuatani, na ushughulikie text tupu.",
        "diagnostic": "Access ya result[-1] inapata error kabla character ya kwanza haijaongezwa.",
        "hint": "Previous output character inapatikana tu baada ya angalau character moja kuongezwa.",
        "why": "Output list huhifadhi representative mmoja wa kila run; empty check inalinda iteration ya kwanza.",
    },
    "py_paginate": {
        "prompt": "Tumia page numbers zinazoanzia 1, rudisha list mpya, na raise ValueError ikiwa number au size si positive.",
        "diagnostic": "Start offset inachukulia page numbers kuwa zero-based na invalid arguments zinakubaliwa.",
        "hint": "Kwa one-based page, page 1 inaanza index 0; kwa hiyo toa 1 kabla ya kuzidisha kwa size.",
        "why": "Offset invariant ni (page_number - 1) * page_size. Slicing yenyewe hurudisha final page fupi au tupu.",
    },
    "py_parse_sensor": {
        "prompt": "Ondoa whitespace, kubali C ya mwisho ikiwa ipo, kataa non-finite readings, na raise ValueError kwa invalid input.",
        "diagnostic": "Unit suffix haiondolewi, na float inakubali NaN pamoja na infinity.",
        "hint": "Normalize optional suffix kabla ya conversion, kisha tumia math.isfinite kwa parsed value.",
        "why": "Parsing na validation ni hatua tofauti: float conversion ikifaulu haithibitishi kuwa sensor reading ni finite.",
    },
    "py_rolling_average": {
        "prompt": "Rudisha averages za complete windows pekee na raise ValueError ikiwa width si positive.",
        "diagnostic": "Loop inajumuisha incomplete windows za mwisho lakini bado inazigawa kwa full width.",
        "hint": "Complete window inaweza kuanza hadi index len(values) - width pekee.",
        "why": "Start range yenye n - width + 1 inahesabu complete windows zote; huwa tupu width ikizidi data length.",
    },
    "py_nearest_station": {
        "prompt": "Rudisha None ikiwa hakuna stations, na uchague station yenye numeric distance iliyo karibu zaidi na position bila kubadilisha input.",
        "diagnostic": "Signed subtraction inapendelea negative differences kubwa badala ya absolute difference ndogo zaidi.",
        "hint": "Closeness inategemea magnitude ya difference, si sign yake.",
        "why": "Absolute distance si negative, kwa hiyo min huchagua station iliyo karibu kweli upande wowote wa position.",
    },
    "js_total_cost": {
        "prompt": "Rudisha 0 kwa array tupu, kubali numeric strings, kataa non-finite values kwa TypeError, na usibadilishe items.",
        "diagnostic": "reduce haina initial value, na fields hazifanyiwi explicit conversion wala validation.",
        "hint": "Ipe reduce numeric accumulator ya kuanzia na validate matokeo ya Number(...) kwa Number.isFinite.",
        "why": "Explicit zero hushughulikia empty input na kuzuia object ya kwanza kuwa accumulator.",
    },
    "js_find_by_code": {
        "prompt": "Rudisha matching object hata ikiwa iko index zero, na rudisha null ikiwa haipo.",
        "diagnostic": "Index zero ni falsy, lakini not-found sentinel -1 ni truthy.",
        "hint": "Linganisha result ya findIndex moja kwa moja na not-found sentinel badala ya kupima truthiness.",
        "why": "findIndex hurudisha -1 kwa absence pekee; kila index kuanzia zero ni valid.",
    },
    "js_count_available": {
        "prompt": "Hesabu elements za array ambazo property ya available ni true hasa.",
        "diagnostic": "for...in inazunguka string indexes, si item objects.",
        "hint": "Tumia array iteration inayotoa values badala ya property names.",
        "why": "for...of hutoa kila object, na strict equality huzuia truthy values nyingine kuhesabiwa kama booleans.",
    },
    "js_chunk_array": {
        "prompt": "Rudisha consecutive copied chunks pamoja na final chunk fupi, kataa size isiyo positive, na uache input bila kubadilika.",
        "diagnostic": "splice inabadilisha na kufupisha input wakati loop index inaendelea kuongezeka.",
        "hint": "Tumia non-mutating range-copy method na validate size kabla loop haijaanza.",
        "why": "slice hunakili kila half-open range, hivyo input length na indexes hubaki stable.",
    },
    "js_retry_delays": {
        "prompt": "Rudisha exponential delays kwa attempts zote ukianzia base, na ukatae attempts au base iliyo negative.",
        "diagnostic": "Exponent inaanza 1, kwa hiyo kila delay inadouble step moja mapema.",
        "hint": "Element ya kwanza hutumia exponent zero kwa sababu base * 2**0 hubaki base.",
        "why": "Index tayari ni idadi ya doublings; kuongeza 1 kunasababisha off-by-one error.",
    },
    "js_parse_percentage": {
        "prompt": "Kubali strings zinazoishia %, trim whitespace, kataa trailing junk na non-finite values, kisha rudisha decimal ratio.",
        "diagnostic": "parseFloat inakubali numeric prefix na kupuuza invalid trailing characters.",
        "hint": "Validate trimmed string yote kwa anchored pattern kabla ya ku-convert captured numeric part.",
        "why": "Anchors zinahitaji kila input character imatch, tofauti na permissive prefix parsing ya parseFloat.",
    },
}


def mixed_tutorial_records() -> list[dict]:
    records = []
    for tutorial_id, prompt, answer in MIXED_TUTORIALS:
        prompts = [
            prompt,
            "Nifundishe kama beginner: " + prompt,
            prompt + " Tumia Kiswahili lakini uache English programming terms kama zilivyo.",
            "Nipe jibu fupi na la vitendo. " + prompt,
        ]
        for variant, variant_prompt in enumerate(prompts):
            records.append({
                "source_id": f"mixed-tutorial:{tutorial_id}",
                "language": "sw_mix",
                "kind": "code_switch_tutorial",
                "messages": [
                    {"role": "user", "content": variant_prompt},
                    {"role": "assistant", "content": answer},
                ],
                "variant": variant,
            })
    return records


def build_curriculum_lane(row: dict, language: str, localized: dict[str, str]) -> list[dict]:
    is_english = language == "en"
    fence = "python" if row["runtime"] == "python" else "javascript"
    labels = (
        {"diagnosis": "Diagnosis", "patch": "Patch", "tests": "Checks", "why": "Why", "hint": "Hint"}
        if is_english
        else {"diagnosis": "Utambuzi", "patch": "Marekebisho", "tests": "Majaribio", "why": "Sababu", "hint": "Dokezo"}
    )
    full = (
        f"{labels['diagnosis']}:\n{localized['diagnostic']}\n\n{labels['patch']}:\n"
        f"```{fence}\n{row['solution'].rstrip()}\n```\n\n{labels['tests']}:\n"
        f"```{fence}\n{row['tests'].rstrip()}\n```\n\n{labels['why']}:\n{localized['why']}"
    )
    hint = f"{labels['hint']}:\n{localized['hint']}"
    action = (
        "Give the smallest safe correction and focused tests."
        if is_english
        else "Toa smallest safe correction na focused tests."
    )
    full_prompts = [
        f"{localized['prompt']}\n\nBuggy code:\n```{fence}\n{row['buggy'].rstrip()}\n```",
        f"{localized['prompt']}\n\nLocal failing diagnostic: {localized['diagnostic']}\n\n```{fence}\n{row['buggy'].rstrip()}\n```",
        f"{localized['prompt']}\n\n{action}\n```{fence}\n{row['buggy'].rstrip()}\n```",
    ]
    if not is_english:
        full_prompts.extend([
            f"Nisaidie ku-debug code hii. {localized['prompt']}\n\n```{fence}\n{row['buggy'].rstrip()}\n```",
            f"Eleza root cause kisha utoe minimal patch. {localized['prompt']}\n\n```{fence}\n{row['buggy'].rstrip()}\n```",
            f"Tumia local diagnostic hii kama evidence: {localized['diagnostic']}\n\nRequirement: {localized['prompt']}\n\n```{fence}\n{row['buggy'].rstrip()}\n```",
        ])
    records = [
        {
            "source_id": f"curriculum:{row['id']}",
            "language": language,
            "kind": "repair_full",
            "messages": [{"role": "user", "content": prompt}, {"role": "assistant", "content": full}],
            "variant": variant,
        }
        for variant, prompt in enumerate(full_prompts)
    ]
    hint_suffix = (
        "\n\nGive one hint only; do not reveal the full solution."
        if is_english
        else "\n\nToa dokezo moja tu; usionyeshe solution nzima."
    )
    hint_prompts = [full_prompts[0] + hint_suffix]
    if not is_english:
        hint_prompts.append(
            f"Niongoze bila kunipa full solution. {localized['prompt']}\n\n```{fence}\n{row['buggy'].rstrip()}\n```"
        )
    for offset, prompt in enumerate(hint_prompts, start=len(full_prompts)):
        records.append({
            "source_id": f"curriculum:{row['id']}",
            "language": language,
            "kind": "repair_hint",
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": hint},
            ],
            "variant": offset,
        })
    return records


def curriculum_records() -> list[dict]:
    records = []
    for row in CURRICULUM:
        run_solution(row)
        localized = {field: row[f"{field}_en"] for field in ("prompt", "diagnostic", "hint", "why")}
        records.extend(build_curriculum_lane(row, "en", localized))
    return records


def extract_pair(row: dict) -> tuple[str, str] | None:
    for prompt_key, answer_key in (("query", "answer"), ("instruction", "output"), ("prompt", "response")):
        prompt, answer = row.get(prompt_key), row.get(answer_key)
        if isinstance(prompt, str) and isinstance(answer, str):
            return prompt.strip(), answer.strip()
    messages = row.get("messages")
    if isinstance(messages, list):
        users = [item.get("content") for item in messages if item.get("role") == "user"]
        assistants = [item.get("content") for item in messages if item.get("role") == "assistant"]
        if users and assistants and isinstance(users[-1], str) and isinstance(assistants[-1], str):
            return users[-1].strip(), assistants[-1].strip()
    return None


def codefeedback_records(limit: int, seed: int) -> list[dict]:
    if limit <= 0:
        return []
    from datasets import load_dataset

    stream = load_dataset("m-a-p/CodeFeedback-Filtered-Instruction", split="train", streaming=True)
    stream = stream.shuffle(seed=seed, buffer_size=10000)
    records, seen = [], set()
    code_pattern = re.compile(r"python|javascript|function|code|debug|test|algorithm|error", re.I)
    for row in stream:
        pair = extract_pair(row)
        if not pair:
            continue
        prompt, answer = pair
        if not (40 <= len(prompt) <= 1800 and 40 <= len(answer) <= 5000):
            continue
        if not code_pattern.search(prompt):
            continue
        digest = stable_id(re.sub(r"\s+", " ", prompt.lower()))
        if digest in seen:
            continue
        seen.add(digest)
        records.append({
            "source_id": f"codefeedback:{digest}",
            "language": "en",
            "kind": "english_replay",
            "messages": [{"role": "user", "content": prompt}, {"role": "assistant", "content": answer}],
            "variant": 0,
        })
        if len(records) >= limit:
            break
    if len(records) < limit:
        raise RuntimeError(f"only found {len(records)} eligible CodeFeedback rows; requested {limit}")
    return records


class Translator:
    def __init__(self, model_name: str, cache_path: Path):
        import torch
        from requests import RequestException
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self.torch = torch
        self.cache_path = cache_path
        self.cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        model_key = model_name.casefold()
        tokenizer_args = {"src_lang": "eng_Latn"} if "nllb" in model_key else {}
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        for attempt in range(1, 4):
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(model_name, **tokenizer_args)
                self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name, torch_dtype=dtype)
                break
            except (OSError, RequestException):
                if attempt == 3:
                    raise
                time.sleep(attempt * 5)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device).eval()
        self.generation_args = {}
        if "nllb" in model_key:
            self.generation_args["forced_bos_token_id"] = self.tokenizer.convert_tokens_to_ids("swh_Latn")
        elif "m2m100" in model_key:
            self.tokenizer.src_lang = "en"
            self.generation_args["forced_bos_token_id"] = self.tokenizer.get_lang_id("sw")

    def translate_many(self, texts: list[str], batch_size: int = 8) -> list[str]:
        pending = [text for text in texts if stable_id(text) not in self.cache]
        for start in range(0, len(pending), batch_size):
            batch = pending[start:start + batch_size]
            encoded = self.tokenizer(batch, return_tensors="pt", padding=True, truncation=True, max_length=384).to(self.device)
            with self.torch.inference_mode():
                output = self.model.generate(
                    **encoded,
                    **self.generation_args,
                    max_new_tokens=384,
                    num_beams=4,
                )
            translated = self.tokenizer.batch_decode(output, skip_special_tokens=True)
            for source, target in zip(batch, translated):
                self.cache[stable_id(source)] = target.strip()
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")
        return [self.cache[stable_id(text)] for text in texts]


def swahili_curriculum_records() -> list[dict]:
    records = []
    for row in CURRICULUM:
        localized = SWAHILI_CURRICULUM[row["id"]]
        records.extend(build_curriculum_lane(row, "sw", localized))
        mixed = {field: code_switch_swahili(value) for field, value in localized.items()}
        records.extend(build_curriculum_lane(row, "sw_mix", mixed))
    return records


def verify_mbpp(row: dict) -> bool:
    setup = row.get("test_setup_code") or ""
    tests = "\n".join(row.get("test_list") or [])
    source = f"{setup}\n{row['code']}\n{tests}\n"
    try:
        result = subprocess.run(["python3", "-c", source], capture_output=True, text=True, timeout=10, check=False)
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def clean_mbpp_prompt(text: str) -> str:
    """Remove scrape/Markdown residue without changing the task semantics."""
    text = re.sub(r">\s*indented block", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*#+\s*", "", text)
    return re.sub(r"\s+", " ", text).strip()


def mbpp_records(
    english_limit: int,
    swahili_limit: int,
    swahili_scaffold_limit: int,
    mixed_limit: int,
    translator: Translator | None,
    seed: int,
) -> list[dict]:
    from datasets import load_dataset

    rows = list(load_dataset("Muennighoff/mbpp", "full", split="test"))
    random.Random(seed).shuffle(rows)
    eligible = [
        row for row in rows
        if 20 <= len(clean_mbpp_prompt(row["text"])) <= 500 and verify_mbpp(row)
    ]
    needed = max(english_limit, swahili_limit, swahili_scaffold_limit, mixed_limit)
    if len(eligible) < needed:
        raise RuntimeError(f"only {len(eligible)} MBPP references passed their tests")
    selected = eligible[:needed]
    if swahili_limit and translator is None:
        raise ValueError("a Kiswahili translator is required when swahili_limit is non-zero")
    translations = (
        translator.translate_many([row["text"] for row in selected[:swahili_limit]])
        if translator is not None
        else []
    )
    records = []
    for index, row in enumerate(selected[:english_limit]):
        tests = "\n".join(row.get("test_list") or [])
        prompt = clean_mbpp_prompt(row["text"])
        records.append({
            "source_id": f"mbpp:{row['task_id']}",
            "language": "en",
            "kind": "verified_generation",
            "messages": [
                {"role": "user", "content": prompt + " Return correct Python code and concise checks."},
                {"role": "assistant", "content": f"```python\n{row['code'].strip()}\n```\n\nChecks:\n```python\n{tests}\n```"},
            ],
            "variant": 0,
        })
    for index, (row, translated) in enumerate(zip(selected[:swahili_limit], translations)):
        records.append({
            "source_id": f"mbpp:{row['task_id']}",
            "language": "sw",
            "kind": "verified_generation",
            "messages": [
                {"role": "system", "content": CODEFELLOW_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": translated
                    + "\nJibu kwa Kiswahili. Toa kizuizi kimoja tu cha msimbo wa Python "
                    "chenye utekelezaji kamili. Baada ya kizuizi, ongeza sentensi moja "
                    "fupi ya Kiswahili inayoeleza mbinu. Usijumuishe majaribio.",
                },
                {
                    "role": "assistant",
                    "content": (
                        f"```python\n{row['code'].strip()}\n```\n\n"
                        + SWAHILI_FORMAT_EXPLANATIONS[index % len(SWAHILI_FORMAT_EXPLANATIONS)]
                    ),
                },
            ],
            "variant": 1,
        })
    for index, row in enumerate(selected[:swahili_scaffold_limit]):
        english_requirement = clean_mbpp_prompt(row["text"])
        records.append({
            "source_id": f"mbpp:{row['task_id']}",
            "language": "sw",
            "kind": "verified_generation",
            "messages": [
                {"role": "system", "content": CODEFELLOW_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Fuata masharti haya kwa makini. Technical requirement imehifadhiwa English "
                        "ili maana ya programming na identifiers zisibadilike:\n"
                        + english_requirement
                        + "\nJibu kwa Kiswahili. Toa fenced Python code block moja tu yenye "
                        "implementation kamili. Baada ya block, ongeza sentensi moja fupi ya "
                        "Kiswahili. Usijumuishe tests, examples au output ya ziada."
                    ),
                },
                {
                    "role": "assistant",
                    "content": (
                        f"```python\n{row['code'].strip()}\n```\n\n"
                        + SWAHILI_FORMAT_EXPLANATIONS[index % len(SWAHILI_FORMAT_EXPLANATIONS)]
                    ),
                },
            ],
            "variant": 3,
        })
    for index, row in enumerate(selected[:mixed_limit]):
        english_requirement = clean_mbpp_prompt(row["text"])
        records.append({
            "source_id": f"mbpp:{row['task_id']}",
            "language": "sw_mix",
            "kind": "verified_generation",
            "messages": [
                {"role": "system", "content": CODEFELLOW_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Kamilisha programming requirement hii; technical terms zimeachwa English "
                        "kama mwanafunzi angezitumia:\n"
                        + english_requirement
                        + "\nToa fenced Python code block moja yenye implementation kamili. Usijumuishe tests."
                    ),
                },
                {
                    "role": "assistant",
                    "content": (
                        f"```python\n{row['code'].strip()}\n```\n\n"
                        + MIXED_FORMAT_EXPLANATIONS[index % len(MIXED_FORMAT_EXPLANATIONS)]
                    ),
                },
            ],
            "variant": 2,
        })
    return records


def split_records(records: list[dict]) -> tuple[list[dict], list[dict]]:
    train, validation = [], []
    for record in records:
        bucket = int(hashlib.sha256(record["source_id"].encode()).hexdigest()[:8], 16) % 20
        (validation if bucket == 0 else train).append(record)
    return train, validation


def write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    cache_path = args.translation_cache or args.output_dir / "translation-cache.json"
    records = curriculum_records()
    records.extend(mixed_tutorial_records())
    records.extend(codefeedback_records(args.codefeedback_limit, args.seed))
    translator = Translator(args.translation_model, cache_path) if args.swahili_mbpp_limit else None
    records.extend(swahili_curriculum_records())
    records.extend(
        mbpp_records(
            args.mbpp_limit,
            args.swahili_mbpp_limit,
            args.swahili_scaffold_limit,
            args.mixed_mbpp_limit,
            translator,
            args.seed,
        )
    )
    if args.locale_repeat < 1:
        raise ValueError("locale-repeat must be at least 1")
    localized = [record for record in records if record["language"] in {"sw", "sw_mix"}]
    for repeat in range(2, args.locale_repeat + 1):
        records.extend({**record, "repeat": repeat} for record in localized)
    random.Random(args.seed).shuffle(records)
    train, validation = split_records(records)
    write_jsonl(args.output_dir / "train.jsonl", train)
    write_jsonl(args.output_dir / "validation.jsonl", validation)
    manifest = {
        "seed": args.seed,
        "locale_repeat": args.locale_repeat,
        "total": len(records),
        "train": len(train),
        "validation": len(validation),
        "languages": Counter(record["language"] for record in records),
        "kinds": Counter(record["kind"] for record in records),
        "sources": {
            "m-a-p/CodeFeedback-Filtered-Instruction": "Apache-2.0; English replay",
            "Muennighoff/mbpp": "CC-BY-4.0; reference solutions executed locally",
            "CodeFellow curriculum": "project-authored; every full solution executed locally",
            **(
                {args.translation_model: "English-to-Kiswahili prompt translation for optional pure-Swahili MBPP lane"}
                if translator is not None
                else {}
            ),
        },
        "evaluation_exclusions": ["evals/cases.py", "evals/kiswahili/tasks.json", "metadata.json test_prompts"],
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=dict), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2, default=dict))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
