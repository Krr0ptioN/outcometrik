from rest_framework import serializers

from .models import (
    AcademicTerm,
    Assessment,
    Course,
    CourseOffering,
    Department,
    Enrollment,
    EnrollmentStatusEvent,
    Grade,
    GradeBatch,
    GradeHistory,
    Institution,
    InstructorAssignment,
    Program,
    ProgramCourse,
    ProgramMembership,
)


class AcademicSerializer(serializers.ModelSerializer):
    """Base wire serializers; domain invariants are owned by academic services."""


class InstitutionSerializer(AcademicSerializer):
    class Meta:
        model = Institution
        fields = ["id", "code", "name", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class DepartmentSerializer(AcademicSerializer):
    class Meta:
        model = Department
        fields = ["id", "institution", "code", "name", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProgramSerializer(AcademicSerializer):
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


class CourseSerializer(AcademicSerializer):
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


class CourseOfferingSerializer(AcademicSerializer):
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


class ProgramMembershipSerializer(AcademicSerializer):
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


class EnrollmentStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Enrollment.Status.choices)
    reason = serializers.CharField(max_length=255, allow_blank=True, default="")


class GradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grade
        fields = (
            "id",
            "offering",
            "enrollment",
            "assessment",
            "batch",
            "state",
            "points_earned",
            "points_possible",
            "version",
            "updated_at",
        )
        read_only_fields = fields


class GradeWriteSerializer(serializers.Serializer):
    enrollment = serializers.PrimaryKeyRelatedField(queryset=Enrollment.objects.all())
    assessment = serializers.PrimaryKeyRelatedField(queryset=Assessment.objects.all())
    batch = serializers.PrimaryKeyRelatedField(queryset=GradeBatch.objects.all())
    state = serializers.ChoiceField(choices=Grade.State.choices)
    points_earned = serializers.DecimalField(
        max_digits=7, decimal_places=2, required=False, allow_null=True
    )
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class GradeUpdateSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    state = serializers.ChoiceField(choices=Grade.State.choices)
    points_earned = serializers.DecimalField(
        max_digits=7, decimal_places=2, required=False, allow_null=True
    )
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class GradeHistorySerializer(serializers.ModelSerializer):
    changed_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = GradeHistory
        fields = (
            "version",
            "old_state",
            "old_points_earned",
            "new_state",
            "new_points_earned",
            "reason",
            "changed_by",
            "created_at",
        )
        read_only_fields = fields


class GradeBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradeBatch
        fields = ("id", "offering", "name", "released_at", "created_at")
        read_only_fields = ("id", "released_at", "created_at")
