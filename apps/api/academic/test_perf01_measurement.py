import hashlib
import json
from io import StringIO

import pytest
from access.models import AuditEvent
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import transaction

from academic.models import Grade, Publication
from academic.perf import fmt_bytes, parse_plan, percentile, summarize, verdict
from academic.services.publications import PublicationService

SMALL = {"students": 6, "terms": 1, "courses_per_term": 1, "los": 2, "assessments": 4, "pos": 3}


def _seed(tmp_path, **extra):
    call_command(
        "seed_perf_cse321",
        meta_file=str(tmp_path / "meta.json"),
        stdout=StringIO(),
        **SMALL,
        **extra,
    )


def test_percentile_nearest_rank():
    data = list(range(1, 101))
    assert percentile(data, 50) == 50
    assert percentile(data, 95) == 95
    assert summarize([1.0, 2.0, 3.0])["p95_reliable"] is False
    with pytest.raises(ValueError):
        percentile([], 50)
    with pytest.raises(ValueError):
        percentile([1], 0)


def test_parse_plan_and_formatting():
    text = (
        "Seq Scan on academic_grade  (cost=0..1 rows=1)\n  Buffers: shared hit=12 read=3\n"
        "Planning Time: 0.120 ms\nExecution Time: 4.500 ms\n"
    )
    plan = parse_plan(text)
    assert plan["execution_ms"] == 4.5 and plan["planning_ms"] == 0.12
    assert plan["seq_scans"] == ["academic_grade"]
    assert (plan["shared_hit"], plan["shared_read"]) == (12, 3)
    assert fmt_bytes(2048) == "2.0 KiB"
    assert verdict(10, None) == "no target recorded"
    assert verdict(10, 5).startswith("MISS") and verdict(5, 10) == "PASS"


@pytest.mark.django_db
def test_seed_rejects_invalid_parameters(tmp_path):
    with pytest.raises(CommandError):
        call_command(
            "seed_perf_cse321", students=0, meta_file=str(tmp_path / "m.json"), stdout=StringIO()
        )
    with pytest.raises(CommandError):
        call_command(
            "seed_perf_cse321",
            students=3,
            los=5,
            assessments=2,
            meta_file=str(tmp_path / "m.json"),
            stdout=StringIO(),
        )


@pytest.mark.django_db
def test_seed_is_deterministic_and_refuses_reseed(tmp_path):
    fingerprints = []
    for _ in range(2):
        with transaction.atomic():
            _seed(tmp_path)
            rows = list(Grade.objects.order_by("id").values_list("id", "state", "points_earned"))
            fingerprints.append(hashlib.sha256(json.dumps(rows, default=str).encode()).hexdigest())
            transaction.set_rollback(True)
    assert fingerprints[0] == fingerprints[1]
    _seed(tmp_path)
    with pytest.raises(CommandError):
        _seed(tmp_path)


@pytest.mark.django_db
def test_published_seed_is_scoped_and_students_cannot_see_faculty_publications(tmp_path):
    _seed(tmp_path, publish=True)
    assert Publication.objects.count() == 4  # (1 offering + program) x (faculty, student)
    assert AuditEvent.objects.filter(action="outcomes.published").count() == 4
    from django.contrib.auth import get_user_model

    student = get_user_model().objects.get(username="perf.student.00001")
    visible = PublicationService(actor=student).get_queryset(actor=student)
    assert not visible.filter(audience=Publication.Audience.FACULTY).exists()
