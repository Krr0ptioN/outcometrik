from rest_framework import serializers

from . import policy
from .models import (
    AcademicTerm,
    Assessment,
    Course,
    CourseOffering,
    CoursePOContribution,
    Department,
    Enrollment,
    EnrollmentStatusEvent,
    Grade,
    GradeBatch,
    GradeHistory,
    Institution,
    InstructorAssignment,
    LearningOutcome,
    Program,
    ProgramCourse,
    ProgramMembership,
    ProgramOutcome,
    ProgramOutcomeSet,
    Syllabus,
    SyllabusAssessment,
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


class SyllabusAssessmentSerializer(AcademicSerializer):
    class Meta:
        model = SyllabusAssessment
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


class AssessmentSerializer(AcademicSerializer):
    class Meta:
        model = Assessment
        fields = ("id", "offering", "title", "points_possible", "status")
        read_only_fields = fields


class StrictWeightIntegerField(serializers.Field):
    """Integer field that rejects booleans, floats, decimals, and fractional strings."""

    def to_representation(self, value):
        return int(value)

    def to_internal_value(self, data):
        if isinstance(data, bool):
            raise serializers.ValidationError("A valid integer between 1 and 5 is required.")
        if isinstance(data, int):
            val = data
        elif isinstance(data, str):
            stripped = data.strip()
            if not stripped or not (
                stripped.isdigit() or (stripped.startswith("-") and stripped[1:].isdigit())
            ):
                raise serializers.ValidationError("A valid integer between 1 and 5 is required.")
            val = int(stripped)
        else:
            raise serializers.ValidationError("A valid integer between 1 and 5 is required.")

        if not policy.is_valid_course_po_weight(val):
            raise serializers.ValidationError(
                f"Course-to-PO contribution weight must be an integer between "
                f"{policy.MIN_COURSE_PO_WEIGHT} and {policy.MAX_COURSE_PO_WEIGHT}."
            )
        return val


class CoursePOContributionSerializer(AcademicSerializer):
    program_outcome_code = serializers.CharField(source="program_outcome.code", read_only=True)
    weight = StrictWeightIntegerField()
    governance_role = serializers.SerializerMethodField()
    governance_level = serializers.SerializerMethodField()

    class Meta:
        model = CoursePOContribution
        fields = [
            "id",
            "syllabus",
            "program_outcome",
            "program_outcome_code",
            "weight",
            "governance_role",
            "governance_level",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "syllabus",
            "program_outcome_code",
            "governance_role",
            "governance_level",
            "created_at",
            "updated_at",
        ]

    def get_governance_role(self, obj) -> str:
        return policy.COURSE_PO_WEIGHT_GOVERNANCE_ROLE

    def get_governance_level(self, obj) -> str:
        return policy.COURSE_PO_WEIGHT_DEFAULT_LEVEL


class SyllabusSerializer(AcademicSerializer):
    """A syllabus version with its draft-editable children."""

    learning_outcomes = LearningOutcomeSerializer(many=True, read_only=True)
    assessments = SyllabusAssessmentSerializer(many=True, read_only=True)
    po_contributions = CoursePOContributionSerializer(many=True, read_only=True)

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
            "po_contributions",
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


class ProgramOutcomeSerializer(AcademicSerializer):
    ordering = serializers.IntegerField(required=False)
    order = serializers.IntegerField(source="ordering", required=False)
    source_url = serializers.CharField(required=False, allow_blank=True)
    source_reference = serializers.CharField(source="source_url", required=False, allow_blank=True)

    class Meta:
        model = ProgramOutcome
        fields = [
            "id",
            "outcome_set",
            "code",
            "label",
            "description",
            "source_url",
            "source_reference",
            "ordering",
            "order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        validators = []

    def validate(self, attrs):
        if not self.partial:
            if "ordering" not in attrs:
                raise serializers.ValidationError({"ordering": "This field is required."})
            if "source_url" not in attrs or not attrs["source_url"].strip():
                raise serializers.ValidationError({"source_url": "This field is required."})
        return attrs


class ProgramOutcomeSetSerializer(AcademicSerializer):
    outcomes = ProgramOutcomeSerializer(many=True, read_only=True)
    active = serializers.BooleanField(read_only=True)

    class Meta:
        model = ProgramOutcomeSet
        fields = [
            "id",
            "program",
            "version",
            "status",
            "active",
            "effective_date",
            "source_reference",
            "activated_at",
            "activated_by",
            "outcomes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "version",
            "status",
            "active",
            "activated_at",
            "activated_by",
            "outcomes",
            "created_at",
            "updated_at",
        ]


class ProgramOutcomeSetActivateSerializer(serializers.Serializer):
    effective_date = serializers.DateField(required=False)


class GradeSerializer(serializers.ModelSerializer):
    assessment_title = serializers.CharField(source="assessment.title", read_only=True)
    batch_name = serializers.CharField(source="batch.name", read_only=True)

    class Meta:
        model = Grade
        fields = (
            "id",
            "offering",
            "enrollment",
            "assessment",
            "assessment_title",
            "batch",
            "batch_name",
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
