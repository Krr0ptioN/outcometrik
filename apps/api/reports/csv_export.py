"""CSV rendering, with protection against spreadsheet formula injection."""

import csv
import io
from datetime import UTC, datetime
from decimal import Decimal

from .domain import STATE_LABELS, Report, format_exact, format_score

# Spreadsheet apps run cells that start with these as formulas (OWASP "CSV injection").
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


def escape_cell(value: str) -> str:
    """Neutralise text a spreadsheet would execute by prefixing a single quote."""
    if value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal | int):
        return str(value)  # numbers are produced by our own formatters, never user text
    return escape_cell(str(value))


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds")


def render_csv(report: Report, *, include_evidence: bool, generated_at: datetime) -> bytes:
    """UTF-8 with a BOM (so Excel reads non-ASCII names), CRLF line ends.

    Layout: a field/value metadata block, a blank line, the results table and, when the
    reader is authorized for evidence, a blank line and a long-format evidence table.
    A missing result has a blank Score and an explicit State; only a measured 0 is "0.0".
    """
    header = report.header
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")

    def write(*cells):
        writer.writerow([_cell(c) for c in cells])

    write("Report", f"Outcometrik {report.kind} outcome report")
    write("Publication ID", header.publication_id)
    write("Run ID", header.run_id)
    write("Program", header.program)
    write("Term", header.term)
    write("PO-set version", header.po_set_version)
    write("Calculation policy version", header.policy_version)
    write("Scope", header.scope_label)
    write("Population", header.population)
    write("Sample size", header.sample_size)
    write("Coverage", header.coverage)
    write("Freshness", "Stale" if header.stale else "Current")
    write("Published at", _iso(header.published_at))
    write("Generated at", _iso(generated_at))
    write()
    write("PO", "Title", "Score", "State", "Sample size", "Population size")
    for row in report.rows:
        write(
            row.code,
            row.title,
            format_score(row.value),
            STATE_LABELS[row.state],
            row.sample_size,
            row.population_size,
        )
    if include_evidence:
        write()
        write(
            "PO",
            "Formula",
            "Numerator",
            "Denominator",
            "Input",
            "Source revision",
            "Weight",
            "Input value",
            "Input state",
        )
        for row in report.rows:
            evidence = row.evidence
            if evidence is None:
                continue
            shared = (
                row.code,
                evidence.formula,
                format_exact(evidence.numerator),
                format_exact(evidence.denominator),
            )
            for item in evidence.inputs or (None,):
                if item is None:
                    write(*shared, "", "", "", "", "")
                    continue
                write(
                    *shared,
                    item.label,
                    item.source_revision,
                    format_exact(item.weight),
                    format_exact(item.value),
                    STATE_LABELS[item.state],
                )
    return out.getvalue().encode("utf-8-sig")
