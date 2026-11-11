from rest_framework import serializers

from .models import (
    AcademicTerm,
    Assessment,
    Course,
    CourseOffering,
    Department,
    Enrollment,
    EnrollmentStatusEvent,
    Institution,
    InstructorAssignment,
    LearningOutcome,
    Program,
    ProgramCourse,
    ProgramMembership,
    Syllabus,
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


class LearningOutcomeSerializer(AcademicSerializer):
    class Meta:
        model = LearningOutcome
        fields = ["id", "code", "description", "order", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class AssessmentSerializer(AcademicSerializer):
    class Meta:
        model = Assessment
        fields = [
            "id",
            "code",
            "kind",
            "order",
            "is_required",
            "is_active",
            "max_points",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_max_points(self, value):
        if value <= 0:
            raise serializers.ValidationError("Maximum points must be greater than zero.")
        return value


class SyllabusSerializer(AcademicSerializer):
    """A syllabus version with its draft-editable children."""

    learning_outcomes = LearningOutcomeSerializer(many=True, read_only=True)
    assessments = AssessmentSerializer(many=True, read_only=True)

    class Meta:
        model = Syllabus
        fields = [
            "id",
            "offering",
            "version",
            "status",
            "approved_by",
            "approved_at",
            "po_set_version",
            "learning_outcomes",
            "assessments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "version",
            "status",
            "approved_by",
            "approved_at",
            "created_at",
            "updated_at",
        ]


class SyllabusCreateSerializer(serializers.Serializer):
    offering = serializers.PrimaryKeyRelatedField(queryset=CourseOffering.objects.all())
    po_set_version = serializers.IntegerField(required=False, allow_null=True, min_value=1)
