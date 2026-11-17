from decimal import Decimal

import pytest
from access.models import DirectCapabilityGrant
from django.contrib.auth import get_user_model
from django.utils import timezone

from academic.models import Assessment, GradeBatch
from academic.services.assessments import AssessmentService
from academic.services.grades import GradeBatchService, GradeService
from academic.tests import enter, make_offering

pytestmark = pytest.mark.django_db
pytest_plugins = ("academic.tests",)


def test_gradebook_visibility_respects_offering_grants_and_assessment_status(gb):
    other = make_offering(gb, section="02")
    other_assessment = Assessment.objects.create(
        offering=other,
        title="Other",
        points_possible=Decimal(10),
        status=Assessment.Status.APPROVED,
    )
    draft = Assessment.objects.create(
        offering=gb["offering"],
        title="Draft",
        points_possible=Decimal(10),
        status=Assessment.Status.DRAFT,
    )
    other_batch = GradeBatch.objects.create(offering=other, name="Other")
    grade = enter(gb)
    teacher = gb["teacher"]

    assert list(GradeService(actor=teacher).get_queryset()) == [grade]
    assert list(GradeBatchService(actor=teacher).get_queryset()) == [gb["batch"]]
    assert list(AssessmentService(actor=teacher).get_queryset()) == [gb["assessment"]]

    grant = DirectCapabilityGrant.objects.create(
        user=teacher, scope_id=other.pk, capability_id="grades.edit"
    )
    assert set(GradeBatchService(actor=teacher).get_queryset()) == {gb["batch"], other_batch}
    assert set(AssessmentService(actor=teacher).get_queryset()) == {
        gb["assessment"],
        other_assessment,
    }
    assert draft not in AssessmentService(actor=teacher).get_queryset()

    grant.revoked_at = timezone.now()
    grant.save()
    assert list(GradeBatchService(actor=teacher).get_queryset()) == [gb["batch"]]
    assert list(AssessmentService(actor=teacher).get_queryset()) == [gb["assessment"]]

    teacher.is_active = False
    teacher.save()
    assert not GradeService(actor=teacher).get_queryset().exists()
    assert not GradeBatchService(actor=teacher).get_queryset().exists()
    assert not AssessmentService(actor=teacher).get_queryset().exists()


def test_inherited_access_and_student_visibility_are_distinct(gb):
    grade = enter(gb)
    assert list(GradeService(actor=gb["admin"]).get_queryset()) == [grade]
    assert list(GradeBatchService(actor=gb["admin"]).get_queryset()) == [gb["batch"]]
    assert list(AssessmentService(actor=gb["admin"]).get_queryset()) == [gb["assessment"]]
    assert not GradeService(actor=gb["student"]).get_queryset().exists()
    assert not GradeBatchService(actor=gb["student"]).get_queryset().exists()
    assert not AssessmentService(actor=gb["student"]).get_queryset().exists()

    stranger = get_user_model().objects.create_user("stranger")
    assert not GradeService(actor=stranger).get_queryset().exists()
    assert not GradeBatchService(actor=stranger).get_queryset().exists()
    assert not AssessmentService(actor=stranger).get_queryset().exists()
