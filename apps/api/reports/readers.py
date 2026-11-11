"""The seam between exports and published results.

Publication, calculation and analytics are separate stories (CALC-03, ANA-01). Exports read
published data only through this interface, so those stories can plug in a real reader
without changing authorization, rendering or audit code.
"""

from typing import Protocol
from uuid import UUID

from .domain import Report


class PublicationReader(Protocol):
    """Reads immutable, published data. Must never return unpublished or draft data."""

    def student_report(self, *, publication_id: UUID, student) -> Report | None:
        """The given student's own report, or None if it does not exist or is not published."""

    def cohort_report(self, *, publication_id: UUID, program_id: UUID) -> Report | None:
        """A program cohort report, or None if it does not exist or is not published."""


class UnavailablePublicationReader:
    """Default until publications exist: every publication is reported as not found."""

    def student_report(self, *, publication_id, student):
        return None

    def cohort_report(self, *, publication_id, program_id):
        return None
