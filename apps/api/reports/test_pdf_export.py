from decimal import Decimal

from .conftest import NOW, make_report
from .domain import OutcomeRow, ResultState
from .pdf_export import render_pdf


def render(report, *, evidence=False):
    return render_pdf(report, include_evidence=evidence, generated_at=NOW)


def test_produces_a_pdf_document():
    data = render(make_report("cohort", []))
    assert data.startswith(b"%PDF-") and data.rstrip().endswith(b"%%EOF")


def test_same_input_gives_identical_bytes():
    report = make_report("cohort", [])
    assert render(report, evidence=True) == render(report, evidence=True)


def test_evidence_section_adds_content():
    report = make_report("cohort", [])
    assert len(render(report, evidence=True)) > len(render(report))


def test_handles_turkish_text_markup_characters_and_many_rows():
    rows = tuple(
        OutcomeRow(
            f"PO{i}", "Mühendislik <b>&</b> Şahin İ ğ", Decimal(1), ResultState.MEASURED, 1, 1
        )
        for i in range(1, 120)
    )
    data = render(make_report("student", [], rows=rows))
    assert data.startswith(b"%PDF-")
