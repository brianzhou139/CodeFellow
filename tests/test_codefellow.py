import tempfile
import unittest
from pathlib import Path
from unittest import mock

import codefellow


class CodeFellowTests(unittest.TestCase):
    def test_python_syntax_passes_without_creating_bytecode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "good.py"
            source = "def double(value):\n    return value * 2\n"
            path.write_text(source, encoding="utf-8")

            result = codefellow.local_diagnostic(path, source)

            self.assertIn("passed", result)
            self.assertFalse((Path(directory) / "__pycache__").exists())

    def test_python_syntax_error_has_location(self):
        path = Path("broken.py")
        result = codefellow.local_diagnostic(path, "def broken(:\n    pass\n")
        self.assertIn("failed", result)
        self.assertIn("line 1", result)

    def test_local_test_evidence_is_grounded_in_exit_code(self):
        completed = mock.Mock(returncode=1, stdout="one failed\n", stderr="detail\n")
        with mock.patch("codefellow.subprocess.run", return_value=completed) as run:
            result = codefellow.local_test_evidence(Path("sample.py"), "python3 -m pytest -q")
        self.assertIn("failed (exit 1)", result)
        self.assertIn("one failed", result)
        self.assertEqual(run.call_args.kwargs["cwd"], Path("sample.py").resolve().parent)
        self.assertFalse(run.call_args.kwargs["check"])

    def test_local_test_evidence_rejects_empty_command(self):
        self.assertIn("empty", codefellow.local_test_evidence(Path("sample.py"), "   "))

    def test_hint_prompt_does_not_request_complete_replacement(self):
        prompt = codefellow.build_prompt(
            Path("sample.py"), "print('hello')", "diagnostic passed", "Help", False
        )
        self.assertIn("GUIDED HINT", prompt)
        self.assertIn("Do not provide a complete replacement", prompt)

    def test_full_prompt_requests_tests(self):
        prompt = codefellow.build_prompt(
            Path("sample.py"), "print('hello')", "diagnostic passed", "Help", True
        )
        self.assertIn("FULL ANSWER", prompt)
        self.assertIn("smallest correct patch", prompt)
        self.assertIn("three concise tests", prompt)
        self.assertIn("Observation to one sentence", prompt)
        self.assertIn("silently simulate every example", prompt)
        self.assertIn("syntax check, not proof", prompt)
        self.assertIn("Observation, Next step, Checks, Why", prompt)
        self.assertIn("patch must differ", prompt)
        self.assertIn("fully restores it", prompt)

    def test_prompt_preserves_expected_outputs_and_boundaries(self):
        prompt = codefellow.build_prompt(
            Path("sample.js"), "function f(x) { return x; }", "syntax passed", "Help", True
        )
        self.assertIn("Treat stated expected\noutputs as constraints", prompt)
        self.assertIn("empty input, repeated\nvalues, type conversions", prompt)

    def test_swahili_code_switch_prompt_preserves_programming_terms(self):
        prompt = codefellow.build_prompt(
            Path("mfano.py"), "def hesabu():\n    return 1\n", "syntax passed", "Nisaidie", True, "sw-mix"
        )
        self.assertIn("function, variable, array, list, loop", prompt)
        self.assertIn("Usilazimishe tafsiri za technical terms", prompt)
        self.assertIn("Uchunguzi, Hatua inayofuata, Majaribio, Sababu", prompt)

    def test_resolve_executable_rejects_missing_runtime(self):
        with mock.patch("codefellow.shutil.which", return_value=None):
            with self.assertRaises(SystemExit):
                codefellow.resolve_executable("definitely-missing-llama-cli")

    def test_extracts_final_assistant_transcript_block(self):
        transcript = "User:\nFirst\n\nAssistant:\nOld\n\nAssistant:\nFinal answer\n"
        self.assertEqual(
            codefellow.extract_assistant_response(transcript), "Final answer"
        )

    def test_run_inference_uses_portable_non_reasoning_command(self):
        completed = mock.Mock(returncode=0, stderr="")
        with mock.patch("codefellow.subprocess.run", return_value=completed) as run:
            result = codefellow.run_inference("llama-cli", Path("model.gguf"), "prompt")
        command = run.call_args.args[0]
        self.assertNotIn("--reasoning", command)
        self.assertIn("--jinja", command)
        self.assertIn("--simple-io", command)
        self.assertEqual(result[0], 0)

    def test_run_inference_times_out_cleanly(self):
        with mock.patch(
            "codefellow.subprocess.run", side_effect=codefellow.subprocess.TimeoutExpired("llama-cli", 1)
        ):
            return_code, response, detail = codefellow.run_inference(
                "llama-cli", Path("model.gguf"), "prompt", timeout_seconds=1
            )
        self.assertEqual(return_code, 124)
        self.assertEqual(response, "")
        self.assertIn("1-second generation limit", detail)


if __name__ == "__main__":
    unittest.main()
