import re

import pytest

from training.build_parallel_dataset import (
    VerifiedTask,
    build_record,
    digest,
    expand_partition,
    mutation_score_python,
    swahili_task_explanation,
    task_specific_explanation,
    validate_python,
)
from training.merge_adapter import scale_loaded_adapter


def sample_task(index: int = 1) -> VerifiedTask:
    code = f"def identity_{index}(value):\n    return value"
    return VerifiedTask(
        parallel_id=f"sample:{index}",
        source="test",
        runtime="python",
        kind="code_generation",
        prompt_en="Return the supplied value.",
        prompt_sw="Rudisha thamani uliyopewa.",
        prompt_mix="Return value uliyopewa.",
        code=code,
        tests_sha256=digest("assert identity(1) == 1"),
        hidden_test_count=1,
        explanation_en="The function returns its input.",
        explanation_sw="Function hii inarejesha input yake.",
        explanation_mix="Function hii ina-return input yake.",
        translation_score=1.0,
        translation_anchors_verified=True,
        explanation_translation_score=1.0,
        explanation_anchors_verified=True,
        explanation_verification_method="project-authored localized curriculum",
        mutation_killed=0,
        mutation_total=0,
    )


def test_parallel_record_locks_identical_code():
    task = sample_task()
    rows = [build_record(task, language, 0) for language in ("en", "sw", "sw_mix")]
    assert {row["code_sha256"] for row in rows} == {digest(task.code)}
    extracted = [
        re.search(r"```python\n(.*?)```", row["messages"][-1]["content"], re.S).group(1).strip()
        for row in rows
    ]
    assert extracted == [task.code] * 3
    assert all(
        row["verification"]["explanation_translation_anchors_verified"]
        and row["verification"]["explanation_translation_semantic_score"] == 1.0
        for row in rows
    )


def test_task_specific_explanations_are_grounded_and_distinct():
    first = task_specific_explanation("Return the sum of all even integers.")
    second = task_specific_explanation("Return the longest unique substring length.")
    assert "sum of all even integers" in first
    assert "longest unique substring" in second
    assert first != second
    assert len(first) < 400 and len(second) < 400


def test_swahili_explanation_uses_authored_frame_and_teacher_content():
    explanation = swahili_task_explanation(
        "Pata jumla ya nambari shufwa. Technical terms zihifadhiwe: function, list."
    )
    assert explanation.startswith("Msimbo huu unatekeleza hitaji lifuatalo:")
    assert "jumla ya nambari shufwa" in explanation
    assert explanation.endswith("hautoi output ya ziada.")
    assert "Technical terms zihifadhiwe" not in explanation


def test_python_static_gate_rejects_no_effect_swap_typo():
    broken = """def sort_values(arr):
    arr[0], arr[1] == arr[1], arr[0]
    return arr
"""
    with pytest.raises(ValueError, match="no-effect"):
        validate_python(broken)


def test_mutation_gate_confirms_tests_distinguish_behavior():
    code = "def add(a, b):\n    return a + b"
    tests = "assert add(2, 3) == 5\nassert add(-1, 1) == 0"
    killed, total = mutation_score_python(code, tests)
    assert total >= 2
    assert killed == total


def test_partition_expansion_is_exact_65_20_15():
    rows = expand_partition([sample_task(index) for index in range(1, 6)], 100, 2026)
    assert len([row for row in rows if row["language"] == "en"]) == 65
    assert len([row for row in rows if row["language"] == "sw"]) == 20
    assert len([row for row in rows if row["language"] == "sw_mix"]) == 15
    for index in range(1, 6):
        assert {row["language"] for row in rows if row["parallel_id"] == f"sample:{index}"} == {
            "en", "sw", "sw_mix"
        }


def test_adapter_strength_scales_every_lora_entry():
    class Layer:
        scaling = {"default": 2.0}

    class Model:
        def __init__(self):
            self.layer = Layer()

        def named_modules(self):
            return [("", self), ("model.layers.4.self_attn.q_proj", self.layer)]

    model = Model()
    assert scale_loaded_adapter(model, 0.75) == (1, 1)
    assert model.layer.scaling["default"] == 1.5


def test_adapter_layer_selection_zeros_unselected_entries():
    class Layer:
        def __init__(self):
            self.scaling = {"default": 2.0}

    class Model:
        def __init__(self):
            self.lower = Layer()
            self.upper = Layer()

        def named_modules(self):
            return [
                ("", self),
                ("model.layers.4.self_attn.q_proj", self.lower),
                ("model.layers.31.self_attn.q_proj", self.upper),
            ]

    model = Model()
    assert scale_loaded_adapter(model, 0.5, layer_min=28, layer_max=35) == (1, 2)
    assert model.lower.scaling["default"] == 0.0
    assert model.upper.scaling["default"] == 1.0


def test_adapter_strength_rejects_unsafe_values():
    class Model:
        def named_modules(self):
            return []

    with pytest.raises(ValueError):
        scale_loaded_adapter(Model(), 0.0)
