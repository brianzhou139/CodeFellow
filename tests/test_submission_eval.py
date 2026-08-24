from evals.submission.build_humaneval_screen import (
    close_paraphrase,
    function_contract,
    lock_localized_contract,
)
from evals.submission.run_format_eval import format_tasks, grade
from evals.submission.summarize_comparison import estimated_score


def test_format_screen_has_fifty_balanced_stable_tasks() -> None:
    tasks = format_tasks()
    assert len(tasks) == 50
    assert len({task["id"] for task in tasks}) == 50
    assert {task["contract"] for task in tasks} == {"exact_fence", "exact_json", "exact_bullets"}
    assert {task["language"] for task in tasks} == {"en", "sw", "sw_mix"}


def test_format_graders_accept_exact_contracts_and_reject_extras() -> None:
    fence, json_task, bullets = format_tasks()[0], format_tasks()[20], format_tasks()[35]
    fenced = f"```python\n{fence['expected']}\n```"
    assert grade(fence, fenced)[0]
    assert not grade(fence, fenced + "\nExtra")[0]
    assert grade(json_task, '{"task":"format_probe_21","status":"ready","offline":true}')[0]
    assert not grade(json_task, "```json\n{}\n```")[0]
    assert grade(bullets, "\n".join(bullets["expected"]))[0]
    assert not grade(bullets, "Heading\n" + "\n".join(bullets["expected"]))[0]


def test_estimated_adtc_score_uses_published_weights() -> None:
    score = estimated_score(80.0, 15.0, 3.5 * 1024)
    assert score["accuracy_component"] == 80.0
    assert score["performance_component"] == 100.0
    assert score["efficiency_component"] == 50.0
    assert score["estimated_total"] == 80.0


def test_humaneval_contract_removes_type_annotations_and_detects_duplicates() -> None:
    row = {
        "entry_point": "combine",
        "prompt": 'from typing import List\n\ndef combine(values: List[int], offset: int = 0) -> int:\n    """Return the sum plus offset."""\n',
        "canonical_solution": "    return sum(values) + offset",
        "test": "def check(candidate):\n    assert candidate([1, 2], 3) == 6",
    }
    requirement, reference, tests = function_contract(row)
    assert "combine(values, offset=0)" in requirement
    assert "List" not in requirement
    assert "return sum(values)" in reference
    assert "check(combine)" in tests
    assert close_paraphrase("Implement a function that sums a list", "Write a function to sum a list")


def test_localized_contract_restores_translated_public_name() -> None:
    english = (
        "Implement the Python function add(x, y). Preserve this exact function name and argument "
        "contract. Requirement: Add two integers."
    )
    translated = "Tekeleza kazi ya Python kuongeza(x, y). Mahitaji: Ongeza nambari mbili."
    locked = lock_localized_contract(english, translated)
    assert locked.startswith("Tekeleza Python function add(x, y).")
    assert "ongeza(x, y)" not in locked
    assert locked.endswith("Mahitaji: Ongeza nambari mbili.")
