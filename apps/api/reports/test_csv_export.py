import csv
import io
import re
from decimal import Decimal

import pytest

from .conftest import NOW, make_report
from .csv_export import escape_cell, render_csv
from .domain import OutcomeRow, ResultState, format_score

FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r", "\n")


def parse(data: bytes):
    text = data.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(text)))


def render(report, *, evidence=False):
    return render_csv(report, include_evidence=evidence, generated_at=NOW)


@pytest.mark.parametrize("prefix", FORMULA_STARTS)
def test_cells_starting_with_formula_characters_are_escaped(prefix):
    assert escape_cell(f"{prefix}HYPERLINK(1)") == f"'{prefix}HYPERLINK(1)"


def test_ordinary_text_is_left_alone():
    assert escape_cell("Engineering knowledge") == "Engineering knowledge"
    assert escape_cell("") == ""
    assert escape_cell("a=b") == "a=b"


def test_hostile_text_never_reaches_a_cell_as_a_formula():
    hostile = ('=HYPERLINK("http://evil","x")', "+1+1", "-2+3", "@SUM(A1)", "\t=1", "\r=1")
    rows = tuple(
        OutcomeRow(f"PO{i}", text, Decimal(50), ResultState.MEASURED, 1, 1)
        for i, text in enumerate(hostile, start=1)
    )
    report = make_report("cohort", [], rows=rows)
    for cell in (c for row in parse(render(report)) for c in row):
        assert not cell.startswith(FORMULA_STARTS), cell
    titles = [row[1] for row in parse(render(report)) if row and re.fullmatch(r"PO\d+", row[0])]
    assert titles[0] == '\'=HYPERLINK("http://evil","x")'


def test_zero_missing_and_other_states_stay_distinct():
    states = (
        ("PO1", Decimal(0), ResultState.MEASURED),
        ("PO2", None, ResultState.NOT_ASSESSED),
        ("PO3", None, ResultState.INCOMPLETE),
        ("PO4", None, ResultState.EXEMPT),
        ("PO5", None, ResultState.UNMAPPED),
    )
    rows = tuple(OutcomeRow(code, "t", value, state, 0, 1) for code, value, state in states)
    table = {r[0]: r[2:4] for r in parse(render(make_report("cohort", [], rows=rows))) if r}
    assert table["PO1"] == ["0.0", "Measured"]
    assert table["PO2"] == ["", "Not assessed"]
    assert table["PO3"] == ["", "Incomplete"]
    assert table["PO4"] == ["", "Exempt"]
    assert table["PO5"] == ["", "Unmapped"]


def test_scores_round_half_up_to_one_decimal_from_full_precision():
    # PRD §5 reference scenario and the §11.4 course-weight example.
    assert format_score(Decimal(86)) == "86.0"
    assert format_score(Decimal("82.857142857142857")) == "82.9"
    assert format_score(Decimal("84.952380952380952")) == "85.0"
    assert format_score(Decimal("86.875")) == "86.9"
    assert format_score(Decimal("0.05")) == "0.1"  # half rounds up, not to even
    assert format_score(Decimal("0.25")) == "0.3"
    assert format_score(None) == ""


def test_metadata_block_identifies_the_publication_and_policy():
    report = make_report("cohort", [])
    fields = {r[0]: r[1] for r in parse(render(report))[:14]}
    header = report.header
    assert fields["Publication ID"] == str(header.publication_id)
    assert fields["Run ID"] == str(header.run_id)
    assert fields["Program"] == "Computer Engineering"
    assert fields["Term"] == "2026 Fall"
    assert fields["PO-set version"] == "PO-set v2"
    assert fields["Calculation policy version"] == "policy-2026.1"
    assert fields["Scope"] == "Computer Engineering (program)"
    assert fields["Sample size"] == "2"
    assert fields["Coverage"] == "2 of 3 students measured"
    assert fields["Freshness"] == "Current"
    assert fields["Generated at"] == "2026-11-11T12:00:00+00:00"


def test_output_is_utf8_with_bom_and_crlf_and_keeps_non_ascii():
    report = make_report("cohort", [], title="Mühendislik bilgisi — Şahin İ")
    data = render(report)
    assert data.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in data and b"\n" not in data.replace(b"\r\n", b"")
    assert "Mühendislik bilgisi — Şahin İ" in data.decode("utf-8-sig")


def test_same_input_gives_identical_bytes():
    report = make_report("cohort", [])
    assert render(report, evidence=True) == render(report, evidence=True)


def test_evidence_table_only_when_requested_and_preserves_the_formula_path():
    report = make_report("cohort", [])
    assert "Formula" not in render(report).decode("utf-8-sig")
    rows = parse(render(report, evidence=True))
    start = next(i for i, r in enumerate(rows) if r[:2] == ["PO", "Formula"])
    evidence = rows[start + 1 :]
    assert len(evidence) == 2  # one row per input
    assert evidence[0][:4] == ["PO1", "sum(weight x LO) / sum(weight)", "254.857142857", "3"]
    assert evidence[0][4:] == ["LO1", "syllabus-r3", "2", "86", "Measured"]
    assert evidence[1][6:8] == ["1", "82.857142857"]  # unrounded intermediate value
