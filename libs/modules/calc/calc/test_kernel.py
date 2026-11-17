# libs/modules/calc/calc/test_kernel.py
from decimal import Decimal

import pytest

from calc.kernel import (
    EntryState,
    ScoreEntry,
    ScoringInputError,
    display_value,
    entry_from_result,
    exempt_entry,
    grade_entry,
    normalize_grade,
    weighted_mean,
)
from calc.kernel import (
    ResultStatus as S,
)


def scored(key: str, weight: str, value: str) -> ScoreEntry:
    return ScoreEntry(key, weight, EntryState.SCORED, Decimal(value))  # type: ignore[arg-type]


# --- PRD §5 and §11.4 acceptance --------------------------------------------
def test_prd_reference_scenario():
    midterm, project = "90", "80"

    lo1 = weighted_mean(
        [grade_entry("midterm", "60", midterm, "100"), grade_entry("project", "40", project, "100")]
    )
    lo2 = weighted_mean(
        [
            grade_entry("midterm", "40", midterm, "100"),
            grade_entry("project", "100", project, "100"),
        ]
    )
    po1 = weighted_mean([entry_from_result("lo1", "2", lo1), entry_from_result("lo2", "1", lo2)])
    po2 = weighted_mean([entry_from_result("lo2", "1", lo2)])

    assert [lo1.display(), lo2.display(), po1.display(), po2.display()] == [
        "86.0",
        "82.9",
        "85.0",
        "82.9",
    ]
    # PO1 must use 82.857..., not the displayed 82.9.
    assert Decimal("84.952") < po1.value < Decimal("84.953")


def test_prd_cumulative_example():
    r = weighted_mean([scored("c1", "5", "85"), scored("c2", "3", "90")])
    assert r.value == Decimal("86.875")
    assert r.display() == "86.9"


def test_no_intermediate_quantization():
    # True mean is exactly 10.05 -> "10.1". Rounding each value first would give 10.0.
    r = weighted_mean(
        [scored("a", "1", "10.04"), scored("b", "1", "10.04"), scored("c", "1", "10.07")]
    )
    assert r.value == Decimal("10.05")
    assert r.display() == "10.1"


# --- Distinct states ------------------------------------------------------------
def test_zero_grade_participates():
    r = weighted_mean([grade_entry("a", "1", "100", "100"), grade_entry("b", "1", "0", "100")])
    assert r.status is S.OK and r.display() == "50.0"


def test_all_states_are_distinct():
    ok = grade_entry("a", "1", "5", "10")
    statuses = {
        "ok": weighted_mean([ok]).status,
        "incomplete": weighted_mean([ok, grade_entry("b", "1", None, "10")]).status,
        "unmapped_empty": weighted_mean([]).status,
        "unmapped_zero_weight": weighted_mean([grade_entry("a", "0", "5", "10")]).status,
        "not_assessed": weighted_mean([grade_entry("a", "1", "0", "0")]).status,
        "all_exempt": weighted_mean([exempt_entry("a", "1", "medical")]).status,
    }
    assert statuses["unmapped_empty"] is statuses["unmapped_zero_weight"] is S.UNMAPPED
    assert (
        len(
            {
                statuses[k]
                for k in ("ok", "incomplete", "unmapped_empty", "not_assessed", "all_exempt")
            }
        )
        == 5
    )


def test_null_results_never_become_zero():
    for r in (
        weighted_mean([]),
        weighted_mean([grade_entry("a", "1", "0", "0")]),
        weighted_mean([exempt_entry("a", "1", "x")]),
        weighted_mean([grade_entry("a", "1", None, "10")]),
    ):
        assert r.value is None and r.display() is None


def test_exempt_removed_from_denominator_and_recorded():
    r = weighted_mean([grade_entry("a", "1", "80", "100"), exempt_entry("b", "9", "medical")])
    assert r.display() == "80.0"
    assert r.total_weight == Decimal(1)
    assert r.exemptions == (("b", "medical"),)


def test_missing_blocks_even_with_other_scores():
    r = weighted_mean([grade_entry("a", "1", "80", "100"), grade_entry("b", "1", None, "100")])
    assert r.status is S.INCOMPLETE and r.value is None and r.missing == ("b",)


def test_missing_with_zero_weight_is_ignored():
    r = weighted_mean([grade_entry("a", "1", "80", "100"), grade_entry("b", "0", None, "100")])
    assert r.status is S.OK


# --- Level chaining -------------------------------------------------------------
def test_chaining_incomplete_propagates():
    lo = weighted_mean([grade_entry("a", "1", None, "10")])
    assert weighted_mean([entry_from_result("lo1", "1", lo)]).status is S.INCOMPLETE


def test_chaining_all_exempt_becomes_exempt_and_keeps_reason():
    lo = weighted_mean([exempt_entry("a", "1", "medical")])
    po = weighted_mean([scored("lo2", "1", "70"), entry_from_result("lo1", "1", lo)])
    assert po.display() == "70.0"
    assert po.exemptions == (("lo1", "a: medical"),)


def test_chaining_unmapped_is_excluded():
    lo = weighted_mean([])
    po = weighted_mean([scored("lo2", "1", "70"), entry_from_result("lo1", "1", lo)])
    assert po.display() == "70.0" and po.total_weight == Decimal(1)


# --- Input validation -----------------------------------------------------------
@pytest.mark.parametrize(
    "earned,possible",
    [
        (0.5, "1"),
        (True, "10"),
        ("NaN", "1"),
        ("Infinity", "1"),
        ("1e2", "10"),
        ("1_0", "20"),
        (" 5", "10"),
        (Decimal("NaN"), "10"),
        (Decimal("Infinity"), "10"),
        ("-1", "10"),
        ("11", "10"),
        ("1", "0"),
        ("1", "-5"),
        ("٩٠", "100"),
    ],
)
def test_invalid_grades_rejected(earned, possible):
    with pytest.raises(ScoringInputError):
        normalize_grade(earned, possible)


def test_zero_over_zero_is_null_not_error():
    assert normalize_grade("0", "0") is None


@pytest.mark.parametrize("weight", ["-1", 0.5, "NaN", True])
def test_invalid_weights_rejected(weight):
    with pytest.raises(ScoringInputError):
        grade_entry("a", weight, "5", "10")


def test_invalid_entries_rejected():
    with pytest.raises(ScoringInputError):
        ScoreEntry("a", "1", EntryState.EXEMPT)  # reason required
    with pytest.raises(ScoringInputError):
        ScoreEntry("a", "1", EntryState.EXEMPT, None, "   ")
    with pytest.raises(ScoringInputError):
        ScoreEntry("a", "1", EntryState.SCORED, Decimal("100.1"))  # type: ignore[arg-type]
    with pytest.raises(ScoringInputError):
        ScoreEntry("a", "1", EntryState.SCORED)
    with pytest.raises(ScoringInputError):
        ScoreEntry("", "1", EntryState.MISSING)


def test_duplicate_keys_rejected():
    with pytest.raises(ScoringInputError):
        weighted_mean([scored("a", "1", "50"), scored("a", "1", "60")])


# --- Rounding policy ------------------------------------------------------------
@pytest.mark.parametrize(
    "v,expected",
    [
        ("0.25", "0.3"),
        ("0.05", "0.1"),
        ("0.04", "0.0"),
        ("84.95", "85.0"),
        ("86.875", "86.9"),
        ("100", "100.0"),
    ],
)
def test_display_rounding_half_up(v, expected):
    assert display_value(Decimal(v)) == expected


# --- Determinism ----------------------------------------------------------------
def test_input_order_does_not_change_bytes():
    a = grade_entry("a", "3", "7", "9")
    b = grade_entry("b", "2", "1", "3")
    c = grade_entry("c", "7", "5", "11")
    assert weighted_mean([a, b, c]).canonical_json() == weighted_mean([c, a, b]).canonical_json()


def test_canonical_json_is_pinned():
    r = weighted_mean([grade_entry("a", "1", "45", "50")])
    assert r.canonical_json() == (
        '{"contributions":[{"key":"a","value":"90","weight":"1"}],"exemptions":[],'
        '"kernel_version":"1","missing":[],"status":"OK","total_weight":"1","value":"90"}'
    )
