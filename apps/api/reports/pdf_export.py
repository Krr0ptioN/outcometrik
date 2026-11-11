"""PDF rendering with ReportLab.

Uses the Bitstream Vera fonts bundled with ReportLab: they cover Turkish letters (ş, ğ, İ),
and need no system fonts. Output is deterministic for identical input (`invariant`).
"""

import io
import os
from datetime import UTC, datetime
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .domain import STATE_LABELS, Report, ResultState, format_exact, format_score

_FONT_DIR = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
_REGULAR, _BOLD = "Vera", "VeraBd"
_NO_VALUE = "—"  # em dash: a missing value, never a zero


def _register_fonts() -> None:
    registered = pdfmetrics.getRegisteredFontNames()
    for name, file in ((_REGULAR, "Vera.ttf"), (_BOLD, "VeraBd.ttf")):
        if name not in registered:
            pdfmetrics.registerFont(TTFont(name, os.path.join(_FONT_DIR, file)))


def _styles():
    base = ParagraphStyle("base", fontName=_REGULAR, fontSize=9, leading=12)
    return {
        "base": base,
        "bold": ParagraphStyle("bold", parent=base, fontName=_BOLD),
        "title": ParagraphStyle("title", parent=base, fontName=_BOLD, fontSize=16, leading=20),
        "h2": ParagraphStyle("h2", parent=base, fontName=_BOLD, fontSize=12, leading=16),
    }


# The bundled font has no Greek capital sigma (used in the PRD's formulas); spell it out
# instead of printing an empty box.
_UNSUPPORTED = {"\u03a3": "sum "}


def _p(text, style) -> Paragraph:
    text = str(text)
    for char, replacement in _UNSUPPORTED.items():
        text = text.replace(char, replacement)
    return Paragraph(escape(text), style)


def _table(data, widths, styles, *, header=True) -> Table:
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        commands.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")))
    table.setStyle(TableStyle(commands))
    return table


def _score(row) -> str:
    return format_score(row.value) if row.state == ResultState.MEASURED else _NO_VALUE


def render_pdf(report: Report, *, include_evidence: bool, generated_at: datetime) -> bytes:
    _register_fonts()
    s = _styles()
    header = report.header
    stamp = generated_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    out = io.BytesIO()

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(_REGULAR, 8)
        canvas.drawString(15 * mm, 10 * mm, f"Outcometrik · generated {stamp}")
        canvas.drawRightString(A4[0] - 15 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        out,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=18 * mm,
        title=f"Outcometrik {report.kind} outcome report",
        author="Outcometrik",
        invariant=1,
    )
    width = A4[0] - 30 * mm
    meta = [
        ("Publication ID", header.publication_id),
        ("Run ID", header.run_id),
        ("Program", header.program),
        ("Term", header.term),
        ("PO-set version", header.po_set_version),
        ("Calculation policy version", header.policy_version),
        ("Scope", header.scope_label),
        ("Population", header.population),
        ("Sample size", header.sample_size),
        ("Coverage", header.coverage),
        ("Freshness", "Stale" if header.stale else "Current"),
        ("Published at", header.published_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")),
        ("Generated at", stamp),
    ]
    story = [
        _p(f"Outcometrik {report.kind} outcome report", s["title"]),
        Spacer(1, 4 * mm),
        _table(
            [[_p(k, s["bold"]), _p(v, s["base"])] for k, v in meta],
            [58 * mm, width - 58 * mm],
            s,
            header=False,
        ),
        Spacer(1, 6 * mm),
        _p("Program outcomes", s["h2"]),
        Spacer(1, 2 * mm),
    ]
    results = [[_p(c, s["bold"]) for c in ("PO", "Title", "Score", "State", "n", "Population")]]
    for row in report.rows:
        results.append(
            [
                _p(row.code, s["base"]),
                _p(row.title, s["base"]),
                _p(_score(row), s["base"]),
                _p(STATE_LABELS[row.state], s["base"]),
                _p(row.sample_size, s["base"]),
                _p("" if row.population_size is None else row.population_size, s["base"]),
            ]
        )
    story.append(
        _table(results, [16 * mm, width - 100 * mm, 18 * mm, 28 * mm, 12 * mm, 26 * mm], s)
    )
    story.append(_p("A dash means no value: the result is not assessed, not zero.", s["base"]))
    if include_evidence:
        story += [Spacer(1, 6 * mm), _p("Evidence", s["h2"]), Spacer(1, 2 * mm)]
        for row in report.rows:
            evidence = row.evidence
            if evidence is None:
                continue
            story.append(
                _p(
                    f"{row.code} — {evidence.formula}. Numerator "
                    f"{format_exact(evidence.numerator) or _NO_VALUE}, denominator "
                    f"{format_exact(evidence.denominator) or _NO_VALUE}.",
                    s["bold"],
                )
            )
            if evidence.inputs:
                inputs = [
                    [_p(c, s["bold"]) for c in ("Input", "Revision", "Weight", "Value", "State")]
                ]
                for item in evidence.inputs:
                    inputs.append(
                        [
                            _p(item.label, s["base"]),
                            _p(item.source_revision, s["base"]),
                            _p(format_exact(item.weight), s["base"]),
                            _p(format_exact(item.value) or _NO_VALUE, s["base"]),
                            _p(STATE_LABELS[item.state], s["base"]),
                        ]
                    )
                story.append(
                    _table(inputs, [width - 110 * mm, 28 * mm, 20 * mm, 30 * mm, 32 * mm], s)
                )
            story.append(Spacer(1, 3 * mm))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return out.getvalue()
