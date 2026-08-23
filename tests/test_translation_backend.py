import unittest

from translation_backend import (
    _TerminologyAwareTranslator,
    prepare_kiswahili_requirement,
    restore_programming_contract,
    restore_technical_tokens,
)


class FakeTranslator(_TerminologyAwareTranslator):
    def translate(self, text, source_lang="swh_Latn", target_lang="eng_Latn"):
        return "SW:" + text


class TranslationBackendTests(unittest.TestCase):
    def test_glossary_protects_executable_semantics(self):
        source = (
            "Rejesha thamani tofauti ya pili kwa ukubwa, au None ikiwa kuna "
            "thamani tofauti chini ya mbili."
        )
        prepared, substitutions = prepare_kiswahili_requirement(source)
        self.assertIn("second-largest distinct value", prepared)
        self.assertIn("fewer than two", prepared)
        self.assertGreaterEqual(len(substitutions), 2)

    def test_glossary_protects_even_numbers(self):
        prepared, _ = prepare_kiswahili_requirement(
            "Rejesha jumla ya nambari kamili shufwa katika orodha tupu."
        )
        self.assertIn("even integers", prepared)
        self.assertIn("empty list", prepared)

    def test_glossary_protects_hashability_and_occurrence(self):
        prepared, _ = prepare_kiswahili_requirement(
            "Rejesha tukio la kwanza la kila kipengele kinachoweza kuwa ufunguo."
        )
        self.assertIn("first occurrence", prepared)
        self.assertIn("hashable item", prepared)

    def test_restore_exact_complexity_notation(self):
        restored, missing = restore_technical_tokens(
            "Compare O(n) and O(n^2).",
            "Linganisha O ((n) na O ((n^2).",
        )
        self.assertIn("O(n), O(n^2)", restored)
        self.assertEqual(missing, ["O(n)", "O(n^2)"])

    def test_restore_public_interface_dropped_by_translation(self):
        restored, actions = restore_programming_contract(
            "Tekeleza second_largest(numbers). Rejesha thamani.",
            "Return the second-largest value.",
        )
        self.assertIn("second_largest(numbers)", restored)
        self.assertEqual(actions, ["restored_interface"])

    def test_restore_indented_source_without_translating_it(self):
        source = """Rekebisha function hii:

        def identity(value):
            return value + 0"""
        restored, actions = restore_programming_contract(source, "Fix this function.")
        self.assertIn("def identity(value):\n    return value + 0", restored)
        self.assertIn("restored_source_code", actions)

    def test_markdown_translation_preserves_fenced_code_and_maps_headings(self):
        source = "Observation\n\nA short explanation.\n\n```python\ndef f():\n    return 1\n```"
        rendered = FakeTranslator().translate_markdown_to_swahili(source)
        self.assertTrue(rendered.startswith("Uchunguzi"))
        self.assertIn("SW:A short explanation.", rendered)
        self.assertIn("```python\ndef f():\n    return 1\n```", rendered)


if __name__ == "__main__":
    unittest.main()
