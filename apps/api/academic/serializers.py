from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from . import services
from .models import (
    AcademicTerm,
    Course,
    CourseOffering,
    Department,
    Enrollment,
    EnrollmentStatusEvent,
    Institution,
    InstructorAssignment,
    Program,
    ProgramCourse,
    ProgramMembership,
)


class AcademicSerializer(serializers.ModelSerializer):
    """Base: relations that define a record's identity cannot change after creation."""

    immutable_fields: tuple[str, ...] = ()

    def validate(self, attrs):
        if self.instance is not None:
            for name in self.immutable_fields:
                if name in attrs and attrs[name] != getattr(self.instance, name):
                    raise serializers.ValidationError({name: "This field cannot be changed."})
        return attrs


def _django_to_drf(exc: DjangoValidationError) -> serializers.ValidationError:
    return serializers.ValidationError({"non_field_errors": exc.messages})


class InstitutionSerializer(AcademicSerializer):
    class Meta:
        model = Institution
        fields = ["id", "code", "name", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class DepartmentSerializer(AcademicSerializer):
    immutable_fields = ("institution",)

    class Meta:
        model = Department
        fields = ["id", "institution", "code", "name", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProgramSerializer(AcademicSerializer):
    immutable_fields = ("department",)

    class Meta:
        model = Program
        fields = [
            "id",
            "department",
            "code",
            "title",
            "status",
            "input_revision",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "input_revision", "created_at", "updated_at"]


class AcademicTermSerializer(AcademicSerializer):
    immutable_fields = ("institution", "year", "season")

    class Meta:
        model = AcademicTerm
        fields = [
            "id",
            "institution",
            "year",
            "season",
            "starts_at",
            "ends_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        starts = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if starts and ends and ends <= starts:
            raise serializers.ValidationError({"ends_at": "Must be after starts_at."})
        return attrs


class CourseSerializer(AcademicSerializer):
    immutable_fields = ("home_department", "code")

    class Meta:
        model = Course
        fields = [
            "id",
            "home_department",
            "code",
            "title",
            "ects",
            "credits",
            "active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProgramCourseSerializer(AcademicSerializer):
    immutable_fields = ("program", "course")

    class Meta:
        model = ProgramCourse
        fields = [
            "id",
            "program",
            "course",
            "effective_from",
            "effective_to",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        start = attrs.get("effective_from", getattr(self.instance, "effective_from", None))
        end = attrs.get("effective_to", getattr(self.instance, "effective_to", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {"effective_to": "Must not be before effective_from."}
            )
        return attrs


class CourseOfferingSerializer(AcademicSerializer):
    immutable_fields = ("program", "course", "term")

    class Meta:
        model = CourseOffering
        fields = [
            "id",
            "program",
            "course",
            "term",
            "section",
            "status",
            "input_revision",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "input_revision", "created_at", "updated_at"]

    def create(self, validated_data):
        try:
            return services.create_offering(**validated_data)
        except DjangoValidationError as exc:
            raise _django_to_drf(exc) from exc


class ProgramMembershipSerializer(AcademicSerializer):
    immutable_fields = ("program", "user")

    class Meta:
        model = ProgramMembership
        fields = [
            "id",
            "program",
            "user",
            "student_number",
            "admitted_term",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class InstructorAssignmentSerializer(AcademicSerializer):
    immutable_fields = ("offering", "user")

    class Meta:
        model = InstructorAssignment
        fields = ["id", "offering", "user", "assignment_role", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class EnrollmentStatusEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = EnrollmentStatusEvent
        fields = [
            "from_status",
            "to_status",
            "eligible",
            "policy_version",
            "reason",
            "changed_by",
            "created_at",
        ]


class EnrollmentSerializer(AcademicSerializer):
    """Roster row. Status, attempt and eligibility are what downstream calculations read."""

    immutable_fields = ("offering", "student")

    class Meta:
        model = Enrollment
        fields = [
            "id",
            "offering",
            "student",
            "status",
            "attempt_number",
            "eligible_for_outcomes",
            "eligibility_policy_version",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "eligible_for_outcomes",
            "eligibility_policy_version",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        actor = self.context["request"].user
        try:
            return services.create_enrollment(actor=actor, **validated_data)
        except DjangoValidationError as exc:
            raise _django_to_drf(exc) from exc


class EnrollmentStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Enrollment.Status.choices)
    reason = serializers.CharField(max_length=255, allow_blank=True, default="")
