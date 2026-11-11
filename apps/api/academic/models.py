import uuid

from access.models import AppendOnlyQuerySet
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import ProtectedError

from . import policy


class TimestampedModel(models.Model):
    """Abstract base: UUID primary key, timestamps, and no silent hard deletes."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        raise ProtectedError(f"{type(self).__name__} records are archived, never deleted.", {self})


class Institution(TimestampedModel):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=255)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from .access_scopes import sync_scope

        sync_scope(self)

    def __str__(self) -> str:
        return self.code


class Department(TimestampedModel):
    institution = models.ForeignKey(
        Institution, on_delete=models.PROTECT, related_name="departments"
    )
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "code"], name="uniq_department_institution_code"
            )
        ]

    def __str__(self) -> str:
        return self.code


class Program(TimestampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="programs")
    code = models.CharField(max_length=32)
    title = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    # Bumped whenever an eligible offering/enrollment changes calculation inputs.
    input_revision = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["department", "code"], name="uniq_program_department_code"
            )
        ]

    def __str__(self) -> str:
        return self.code

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from .access_scopes import sync_scope

        sync_scope(self)


class AcademicTerm(TimestampedModel):
    class Season(models.TextChoices):
        FALL = "fall", "Fall"
        SPRING = "spring", "Spring"
        SUMMER = "summer", "Summer"

    institution = models.ForeignKey(Institution, on_delete=models.PROTECT, related_name="terms")
    year = models.PositiveSmallIntegerField()
    season = models.CharField(max_length=16, choices=Season.choices)
    starts_at = models.DateField()
    ends_at = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "year", "season"],
                name="uniq_term_institution_year_season",
            ),
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")),
                name="term_ends_after_start",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.year}-{self.season}"


class Course(TimestampedModel):
    """Catalog identity of a course. Separate from any term-specific offering."""

    home_department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="courses"
    )
    code = models.CharField(max_length=32)
    title = models.CharField(max_length=255)
    ects = models.PositiveSmallIntegerField()
    credits = models.PositiveSmallIntegerField()
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["home_department", "code"], name="uniq_course_department_code"
            )
        ]

    def __str__(self) -> str:
        return self.code


class ProgramCourse(TimestampedModel):
    """Link that lets a course contribute to a program, even if another department owns it."""

    class Status(models.TextChoices):
        PROPOSED = "proposed", "Proposed"
        APPROVED = "approved", "Approved"
        INACTIVE = "inactive", "Inactive"

    program = models.ForeignKey(Program, on_delete=models.PROTECT, related_name="program_courses")
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="program_courses")
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PROPOSED)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["program", "course"], name="uniq_program_course_link"),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gte=models.F("effective_from")),
                name="program_course_valid_window",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.program_id}:{self.course_id}"


class CourseOffering(TimestampedModel):
    """A course run: one program + one course + one term + one section."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    program = models.ForeignKey(Program, on_delete=models.PROTECT, related_name="offerings")
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="offerings")
    term = models.ForeignKey(AcademicTerm, on_delete=models.PROTECT, related_name="offerings")
    section = models.CharField(max_length=16)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    input_revision = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["program", "course", "term", "section"],
                name="uniq_offering_program_course_term_section",
            )
        ]

    def __str__(self) -> str:
        return f"{self.course_id}-{self.section}"

    def validate_association(self) -> None:
        """An offering needs an active program and an approved program-course link."""
        if self.program.status != Program.Status.ACTIVE:
            raise ValidationError("The program is not active.")
        if self.term.institution_id != self.program.department.institution_id:
            raise ValidationError("The term belongs to a different institution than the program.")
        link = ProgramCourse.objects.filter(
            program_id=self.program_id, course_id=self.course_id
        ).first()
        if link is None:
            raise ValidationError("This course is not associated with this program.")
        if link.status != ProgramCourse.Status.APPROVED:
            raise ValidationError("The program-course association is not approved.")

    def clean(self) -> None:
        super().clean()
        if self._state.adding:
            self.validate_association()

    def save(self, *args, **kwargs):
        # Django does not call clean() on save(); enforce the rule for every new offering.
        if self._state.adding:
            self.validate_association()
        super().save(*args, **kwargs)
        from .access_scopes import sync_scope

        sync_scope(self)


class ProgramMembership(TimestampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        GRADUATED = "graduated", "Graduated"

    program = models.ForeignKey(Program, on_delete=models.PROTECT, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="program_memberships"
    )
    student_number = models.CharField(max_length=32)
    admitted_term = models.ForeignKey(
        AcademicTerm, null=True, blank=True, on_delete=models.PROTECT, related_name="admissions"
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["program", "user"], name="uniq_membership_program_user"
            ),
            models.UniqueConstraint(
                fields=["program", "student_number"], name="uniq_membership_program_student_number"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.program_id}:{self.student_number}"


class InstructorAssignment(TimestampedModel):
    class Role(models.TextChoices):
        INSTRUCTOR = "instructor", "Instructor"
        ASSISTANT = "assistant", "Assistant"

    offering = models.ForeignKey(
        CourseOffering, on_delete=models.PROTECT, related_name="instructor_assignments"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="instructor_assignments"
    )
    assignment_role = models.CharField(max_length=16, choices=Role.choices, default=Role.INSTRUCTOR)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["offering", "user"], name="uniq_instructor_offering_user"
            )
        ]

    def __str__(self) -> str:
        return f"{self.offering_id}:{self.user_id}"


class Enrollment(TimestampedModel):
    class Status(models.TextChoices):
        ENROLLED = "enrolled", "Enrolled"
        COMPLETED = "completed", "Completed"
        WITHDRAWN = "withdrawn", "Withdrawn"
        INCOMPLETE = "incomplete", "Incomplete"

    offering = models.ForeignKey(
        CourseOffering, on_delete=models.PROTECT, related_name="enrollments"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="academic_enrollments"
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ENROLLED)
    attempt_number = models.PositiveSmallIntegerField(default=1)
    # Recorded result of the eligibility policy, read by downstream calculations.
    eligible_for_outcomes = models.BooleanField(default=False, editable=False)
    eligibility_policy_version = models.CharField(max_length=32, blank=True, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["offering", "student"], name="uniq_enrollment_offering_student"
            ),
            models.CheckConstraint(
                condition=models.Q(attempt_number__gte=1), name="enrollment_attempt_positive"
            ),
        ]
        indexes = [
            models.Index(fields=["offering", "status", "student"], name="enr_roster_idx"),
            models.Index(fields=["student", "status", "offering"], name="enr_student_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.offering_id}:{self.student_id}"

    def validate_roster_rules(self) -> None:
        if self.offering.status != CourseOffering.Status.ACTIVE:
            raise ValidationError("The offering is not active.")
        is_member = ProgramMembership.objects.filter(
            program_id=self.offering.program_id,
            user_id=self.student_id,
            status=ProgramMembership.Status.ACTIVE,
        ).exists()
        if not is_member:
            raise ValidationError("The student is not an active member of the offering's program.")

    def apply_policy(self) -> None:
        self.eligible_for_outcomes = policy.is_eligible(self.status)
        self.eligibility_policy_version = policy.POLICY_VERSION

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.validate_roster_rules()
            self.apply_policy()
        super().save(*args, **kwargs)


class EnrollmentStatusEvent(TimestampedModel):
    """Append-only record of every status/eligibility decision for an enrollment."""

    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.PROTECT, related_name="status_events"
    )
    from_status = models.CharField(max_length=16, blank=True)
    to_status = models.CharField(max_length=16)
    eligible = models.BooleanField()
    policy_version = models.CharField(max_length=32)
    reason = models.CharField(max_length=255, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        ordering = ["created_at"]


class Assessment(TimestampedModel):
    """STUB. CUR-01 replaces this with the versioned syllabus assessment.

    Grades only depend on: offering, points_possible, approved status.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"

    offering = models.ForeignKey(
        CourseOffering, on_delete=models.PROTECT, related_name="assessments"
    )
    title = models.CharField(max_length=255)
    points_possible = models.DecimalField(max_digits=7, decimal_places=2)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(points_possible__gt=0),
                name="assessment_points_possible_positive",
            )
        ]

    def __str__(self) -> str:
        return self.title


class GradeBatch(TimestampedModel):
    """A set of grades released to students together. Unreleased = faculty-only."""

    offering = models.ForeignKey(
        CourseOffering, on_delete=models.PROTECT, related_name="grade_batches"
    )
    name = models.CharField(max_length=120)
    released_at = models.DateTimeField(null=True, blank=True, editable=False)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        editable=False,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["offering", "name"], name="uniq_grade_batch_name")
        ]

    def __str__(self) -> str:
        return f"{self.offering_id}:{self.name}"


class Grade(TimestampedModel):
    """Current value of one enrollment/assessment measurement. History is in GradeHistory."""

    class State(models.TextChoices):
        SCORED = "scored", "Scored"  # zero is a real scored value
        MISSING = "missing", "Missing"
        EXEMPT = "exempt", "Exempt"
        WITHDRAWN = "withdrawn", "Withdrawn"
        INCOMPLETE = "incomplete", "Incomplete"

    offering = models.ForeignKey(CourseOffering, on_delete=models.PROTECT, related_name="grades")
    enrollment = models.ForeignKey(Enrollment, on_delete=models.PROTECT, related_name="grades")
    assessment = models.ForeignKey(Assessment, on_delete=models.PROTECT, related_name="grades")
    batch = models.ForeignKey(GradeBatch, on_delete=models.PROTECT, related_name="grades")
    state = models.CharField(max_length=16, choices=State.choices)
    points_earned = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    # Snapshot of assessment.points_possible at write time.
    points_possible = models.DecimalField(max_digits=7, decimal_places=2)
    # Optimistic-lock counter. Equals the latest GradeHistory.version.
    version = models.PositiveIntegerField(default=1, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "assessment"], name="uniq_grade_enrollment_assessment"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(state="scored", points_earned__isnull=False)
                    | (~models.Q(state="scored") & models.Q(points_earned__isnull=True))
                ),
                name="grade_points_match_state",
            ),
            models.CheckConstraint(
                condition=models.Q(points_earned__isnull=True)
                | (
                    models.Q(points_earned__gte=0)
                    & models.Q(points_earned__lte=models.F("points_possible"))
                ),
                name="grade_points_in_range",
            ),
        ]
        indexes = [
            models.Index(fields=["offering", "batch"], name="grade_offering_batch_idx"),
            models.Index(fields=["enrollment"], name="grade_enrollment_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.enrollment_id}:{self.assessment_id}"


class GradeHistory(TimestampedModel):
    """Append-only. One row per change, including creation (old_state is blank)."""

    grade = models.ForeignKey(Grade, on_delete=models.PROTECT, related_name="history")
    version = models.PositiveIntegerField()
    old_state = models.CharField(max_length=16, blank=True)
    old_points_earned = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    new_state = models.CharField(max_length=16)
    new_points_earned = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    reason = models.CharField(max_length=255, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ["version"]
        constraints = [
            models.UniqueConstraint(fields=["grade", "version"], name="uniq_grade_history_version")
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Grade history is immutable.")
        return super().save(*args, **kwargs)
