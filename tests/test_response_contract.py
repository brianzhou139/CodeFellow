import unittest

from response_contract import normalize_code_response, normalize_explanation_response


class ResponseContractTests(unittest.TestCase):
    def test_python_wraps_code_and_removes_trailing_demo(self):
        raw = """def sum_even(values):
    return sum(value for value in values if value % 2 == 0)

values = [1, 2, 3]
print(sum_even(values))"""
        response, actions = normalize_code_response(raw, "python", "sw")
        self.assertIn("```python", response)
        self.assertNotIn("print(", response)
        self.assertIn("Msimbo huu hutumia", response)
        self.assertEqual(actions, ["wrapped_bare_code", "removed_trailing_demo"])

    def test_javascript_wraps_function_and_removes_console_demo(self):
        raw = """function sumEven(values) {
  return values.filter(value => value % 2 === 0).reduce((a, b) => a + b, 0);
}
console.log(sumEven([1, 2, 3]));"""
        response, actions = normalize_code_response(raw, "javascript", "sw_mix")
        self.assertIn("```javascript", response)
        self.assertNotIn("console.log", response)
        self.assertIn("Function hii", response)
        self.assertIn("removed_trailing_demo", actions)

    def test_existing_fence_is_not_changed(self):
        raw = "```python\ndef identity(value):\n    return value\n```\n\nAlready explained."
        response, actions = normalize_code_response(raw, "python", "en")
        self.assertEqual(response, raw)
        self.assertEqual(actions, [])

    def test_mixed_mode_adds_register_to_fenced_pure_code(self):
        raw = "```python\ndef identity(value):\n    return value\n```\n\nMsimbo huu ni salama."
        response, actions = normalize_code_response(raw, "python", "sw_mix")
        self.assertIn("Function hii", response)
        self.assertEqual(actions, ["added_mixed_register"])

    def test_fenced_python_demo_is_removed_and_swahili_is_added(self):
        raw = """```python
def double(value):
    return value * 2

print(double(3))
```

Done."""
        response, actions = normalize_code_response(raw, "python", "sw")
        self.assertNotIn("print(", response)
        self.assertIn("Msimbo huu", response)
        self.assertEqual(actions, ["removed_trailing_demo", "added_swahili_register"])

    def test_prose_is_not_misclassified_as_code(self):
        raw = "Hapa tunahitaji kueleza function kabla ya kuandika implementation."
        response, actions = normalize_code_response(raw, "python", "sw_mix")
        self.assertEqual(response, raw)
        self.assertEqual(actions, [])

    def test_mixed_explanation_preserves_swahili_and_adds_programming_register(self):
        raw = "Uchangamano huu huongezeka kwa mstari wakati ukubwa unaongezeka mara mbili."
        response, actions = normalize_explanation_response(raw, "sw_mix")
        self.assertTrue(response.startswith(raw))
        self.assertIn("function, input na output", response)
        self.assertEqual(actions, ["added_mixed_explanation_register"])

    def test_mixed_explanation_does_not_duplicate_existing_register(self):
        raw = "Function hii hupokea input na kurejesha output salama."
        response, actions = normalize_explanation_response(raw, "sw_mix")
        self.assertEqual(response, raw)
        self.assertEqual(actions, [])


if __name__ == "__main__":
    unittest.main()
