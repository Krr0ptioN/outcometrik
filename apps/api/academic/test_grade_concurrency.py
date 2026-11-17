"""Grade transaction and release serialization regressions."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier, Event

import pytest
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, transaction

from academic.models import Grade, GradeBatch
from academic.services.grades import GradeBatchService, GradeService, GradeVersionConflict
from academic.tests import enter, release

pytest_plugins = ("academic.tests",)


@pytest.mark.django_db
def test_release_with_grades_bumps_revisions_once(gb):
    enter(gb)
    gb["program"].refresh_from_db()
    gb["offering"].refresh_from_db()
    before = gb["program"].input_revision, gb["offering"].input_revision

    release(gb)
    release(gb)
    gb["program"].refresh_from_db()
    gb["offering"].refresh_from_db()
    assert (gb["program"].input_revision, gb["offering"].input_revision) == (
        before[0] + 1,
        before[1] + 1,
    )


@pytest.mark.django_db
def test_creation_after_release_requires_reason_and_bumps_both_revisions(gb):
    release(gb)
    gb["program"].refresh_from_db()
    gb["offering"].refresh_from_db()
    before = gb["program"].input_revision, gb["offering"].input_revision

    with pytest.raises(ValidationError, match="reason"):
        enter(gb)
    assert not Grade.objects.exists()

    grade = enter(gb, state="exempt", points=None, reason="Approved exemption")
    gb["program"].refresh_from_db()
    gb["offering"].refresh_from_db()
    assert (gb["program"].input_revision, gb["offering"].input_revision) == (
        before[0] + 1,
        before[1] + 1,
    )
    assert grade.state == "exempt" and grade.points_earned is None
    assert grade.history.get().reason == "Approved exemption"


@pytest.mark.skipif(
    connection.vendor != "postgresql", reason="Row-lock concurrency requires PostgreSQL"
)
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_creation_waits_for_release_and_rechecks_reason(gb):
    attempted = Event()

    def create_grade():
        close_old_connections()
        try:
            attempted.set()
            with pytest.raises(ValidationError, match="reason"):
                enter(gb)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            GradeBatch.objects.select_for_update().get(pk=gb["batch"].pk)
            future = pool.submit(create_grade)
            assert attempted.wait(timeout=5)
            GradeBatchService(actor=gb["teacher"]).release(batch=gb["batch"])
        future.result(timeout=10)

    assert not Grade.objects.exists()


@pytest.mark.skipif(
    connection.vendor != "postgresql", reason="Row-lock concurrency requires PostgreSQL"
)
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_simultaneous_corrections_conflict_instead_of_overwrite(gb):
    grade = enter(gb)
    barrier = Barrier(2, timeout=5)

    def correct(points):
        close_old_connections()
        try:
            barrier.wait()
            try:
                GradeService(actor=gb["teacher"]).correct(
                    grade=grade, expected_version=1, state="scored", points_earned=points
                )
                return "updated"
            except GradeVersionConflict:
                return "conflict"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(correct, Decimal(value)) for value in ("7", "9")]
        assert sorted(f.result(timeout=10) for f in futures) == ["conflict", "updated"]
    grade.refresh_from_db()
    assert grade.version == 2
    assert grade.history.count() == 2
