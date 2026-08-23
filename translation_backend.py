#!/usr/bin/env python3
"""Local, terminology-aware translation for CodeFellow's Kiswahili lane.

General-purpose machine translation can silently invert small programming
requirements (for example, ``shufwa``/even becoming empty or odd).  The
preprocessor below code-switches only established technical phrases before
translation.  This keeps identifiers and ordinary Kiswahili prose intact while
making the semantic contract unambiguous to the translation model.
"""

from __future__ import annotations

import re
import textwrap


# Longest phrases must be substituted first.  This is deliberately a compact,
# domain-owned glossary rather than a general Kiswahili dictionary.  It covers
# concepts where a one-word mistranslation changes executable behaviour.
KISWAHILI_PROGRAMMING_GLOSSARY: tuple[tuple[str, str], ...] = (
    ("thamani tofauti ya pili kwa ukubwa", "second-largest distinct value"),
    ("kipengele kinachoweza kuwa ufunguo", "hashable item"),
    ("mfuatano mdogo mrefu zaidi", "longest substring"),
    ("herufi zisizo za kialfabeti au nambari", "non-alphanumeric characters"),
    ("nambari kamili zisizo hasi", "non-negative integers"),
    ("nambari kamili shufwa", "even integers"),
    ("nambari zote shufwa", "all even numbers"),
    ("nambari zote witiri", "all odd numbers"),
    ("nambari shufwa", "even numbers"),
    ("nambari witiri", "odd numbers"),
    ("thamani tofauti", "distinct values"),
    ("tukio la kwanza", "first occurrence"),
    ("bila herufi inayojirudia", "without repeated characters"),
    ("dirisha linalosogea", "sliding window"),
    ("chini ya mbili", "fewer than two"),
    ("orodha tupu", "empty list"),
    ("safu tupu", "empty array"),
    ("array tupu", "empty array"),
    ("mwanzo au mwisho", "leading or trailing"),
    ("hali ya msingi", "base case"),
    ("kesi ya msingi", "base case"),
    ("muda wa utekelezaji", "runtime"),
    ("uchangamano wa muda", "time complexity"),
)

PROTECTED_TECHNICAL_TOKEN_RE = re.compile(
    r"(?<!\w)(?:O\([^\s,;.]+\)|===|==|!==|!=|<=|>=|"
    r"TypeError|NoneType|JavaScript|Python|None)(?!\w)",
    re.IGNORECASE,
)
INTERFACE_RE = re.compile(r"(?<![.\w])([A-Za-z_$][\w$]*)\s*\(([^()\n]*)\)")
SOURCE_BLOCK_RE = re.compile(
    r"(?ms)^(?P<block>[ \t]*(?:def\s+[A-Za-z_]\w*\s*\([^\n]*\)\s*:|"
    r"(?:async\s+)?function\s+[A-Za-z_$][\w$]*\s*\([^\n]*\)\s*\{).*)$"
)
FENCED_MARKDOWN_RE = re.compile(r"(```.*?```)", re.DOTALL)
ENGLISH_HEADING_MAP = {
    "Observation": "Uchunguzi",
    "Next step": "Hatua inayofuata",
    "Checks": "Majaribio",
    "Why": "Sababu",
}


def prepare_kiswahili_requirement(text: str) -> tuple[str, list[dict[str, str]]]:
    """Code-switch semantic programming phrases before machine translation."""
    prepared = text
    substitutions: list[dict[str, str]] = []
    for kiswahili, english in KISWAHILI_PROGRAMMING_GLOSSARY:
        pattern = re.compile(r"(?<!\w)" + re.escape(kiswahili) + r"(?!\w)", re.IGNORECASE)
        prepared, count = pattern.subn(english, prepared)
        if count:
            substitutions.append({"source": kiswahili, "replacement": english})
    return prepared, substitutions


def restore_technical_tokens(source: str, translated: str) -> tuple[str, list[str]]:
    """Append exact programming notation that an MT model corrupted or dropped."""
    source_tokens = list(dict.fromkeys(match.group(0) for match in PROTECTED_TECHNICAL_TOKEN_RE.finditer(source)))
    missing = [token for token in source_tokens if token.casefold() not in translated.casefold()]
    if not missing:
        return translated, []
    suffix = "Istilahi za programming: " + ", ".join(missing) + "."
    return translated.rstrip() + "\n\n" + suffix, missing


def restore_programming_contract(source: str, translated: str) -> tuple[str, list[str]]:
    """Restore exact public interfaces and source code after natural-language MT."""
    additions: list[str] = []
    actions: list[str] = []
    source_block_match = SOURCE_BLOCK_RE.search(source)
    natural_language = source[: source_block_match.start()] if source_block_match else source

    interfaces = list(
        dict.fromkeys(
            f"{match.group(1)}({match.group(2).strip()})"
            for match in INTERFACE_RE.finditer(natural_language)
        )
    )
    missing_interfaces = [interface for interface in interfaces if interface not in translated]
    if missing_interfaces:
        additions.append(
            "Required interface (preserve this exact name and parameters): "
            + ", ".join(missing_interfaces)
            + "."
        )
        actions.append("restored_interface")

    if source_block_match:
        source_block = textwrap.dedent(source_block_match.group("block")).rstrip()
        additions.append(
            "Original source code to inspect and correct (preserve its public interface):\n"
            f"```\n{source_block}\n```"
        )
        actions.append("restored_source_code")

    if not additions:
        return translated, actions
    return translated.rstrip() + "\n\n" + "\n\n".join(additions), actions


class _TerminologyAwareTranslator:
    """Shared semantic-contract handling for interchangeable NLLB runtimes."""

    def translate_requirement(self, text: str) -> tuple[str, list[dict[str, str]]]:
        prepared, substitutions = prepare_kiswahili_requirement(text)
        translated = self.translate(prepared)
        translated, contract_actions = restore_programming_contract(text, translated)
        substitutions.extend(
            {"source": action, "replacement": "appended_exact_contract"}
            for action in contract_actions
        )
        return translated, substitutions

    def translate_to_swahili(self, text: str) -> str:
        translated = self.translate(text, source_lang="eng_Latn", target_lang="swh_Latn")
        restored, _ = restore_technical_tokens(text, translated)
        return restored

    def translate_markdown_to_swahili(self, text: str) -> str:
        """Translate prose paragraph-by-paragraph while preserving fenced code exactly."""
        rendered: list[str] = []
        for segment in FENCED_MARKDOWN_RE.split(text):
            if not segment:
                continue
            if segment.startswith("```"):
                rendered.append(segment)
                continue
            paragraphs = re.split(r"(\n\s*\n)", segment)
            for paragraph in paragraphs:
                if not paragraph.strip() or re.fullmatch(r"\n\s*\n", paragraph):
                    rendered.append(paragraph)
                    continue
                stripped = paragraph.strip()
                heading_match = re.fullmatch(
                    r"(?P<marks>#{0,6}\s*)?(?P<heading>Observation|Next step|Checks|Why):?",
                    stripped,
                    re.IGNORECASE,
                )
                if heading_match:
                    canonical = next(
                        heading
                        for heading in ENGLISH_HEADING_MAP
                        if heading.casefold() == heading_match.group("heading").casefold()
                    )
                    rendered.append(
                        (heading_match.group("marks") or "") + ENGLISH_HEADING_MAP[canonical]
                    )
                    continue
                translated = self.translate_to_swahili(stripped)
                leading = paragraph[: len(paragraph) - len(paragraph.lstrip())]
                trailing = paragraph[len(paragraph.rstrip()) :]
                rendered.append(leading + translated + trailing)
        return "".join(rendered).strip()


class NllbTranslator(_TerminologyAwareTranslator):
    """Translate Kiswahili requirements to English without a network service."""

    def __init__(self, model_name_or_path: str, device: str = "auto") -> None:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name_or_path, src_lang="swh_Latn", local_files_only=True
        )
        use_cuda = torch.cuda.is_available() if device == "auto" else device == "cuda"
        self.device = torch.device("cuda" if use_cuda else "cpu")
        dtype = torch.float16 if use_cuda else torch.float32
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            model_name_or_path,
            torch_dtype=dtype,
            local_files_only=True,
            low_cpu_mem_usage=True,
        ).to(self.device).eval()
        self.target_token_ids = {
            "eng_Latn": self.tokenizer.convert_tokens_to_ids("eng_Latn"),
            "swh_Latn": self.tokenizer.convert_tokens_to_ids("swh_Latn"),
        }

    def translate(
        self,
        text: str,
        source_lang: str = "swh_Latn",
        target_lang: str = "eng_Latn",
    ) -> str:
        self.tokenizer.src_lang = source_lang
        encoded = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=384,
        ).to(self.device)
        with self.torch.inference_mode():
            output = self.model.generate(
                **encoded,
                forced_bos_token_id=self.target_token_ids[target_lang],
                max_new_tokens=192,
                num_beams=4,
            )
        return self.tokenizer.batch_decode(output, skip_special_tokens=True)[0].strip()



class CTranslate2NllbTranslator(_TerminologyAwareTranslator):
    """CPU-int8 NLLB runtime for the 8 GB ADTC reference laptop."""

    def __init__(self, model_path: str, threads: int = 4) -> None:
        import ctranslate2
        import sentencepiece as spm

        self.sentencepiece = spm.SentencePieceProcessor()
        if not self.sentencepiece.load(f"{model_path}/sentencepiece.bpe.model"):
            raise RuntimeError("could not load the NLLB SentencePiece tokenizer")
        self.translator = ctranslate2.Translator(
            model_path,
            device="cpu",
            compute_type="int8",
            inter_threads=1,
            intra_threads=threads,
        )

    def translate(
        self,
        text: str,
        source_lang: str = "swh_Latn",
        target_lang: str = "eng_Latn",
    ) -> str:
        source_tokens = [source_lang, *self.sentencepiece.encode_as_pieces(text), "</s>"]
        result = self.translator.translate_batch(
            [source_tokens],
            target_prefix=[[target_lang]],
            beam_size=4,
            max_decoding_length=192,
        )[0]
        target_tokens = result.hypotheses[0]
        if target_tokens and target_tokens[0] == target_lang:
            target_tokens = target_tokens[1:]
        target_tokens = [token for token in target_tokens if token != "</s>"]
        return self.sentencepiece.decode(target_tokens).strip()
