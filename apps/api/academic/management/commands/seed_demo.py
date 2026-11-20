"""Deterministic, idempotent demo seed command for Acibadem University CSE (UI-05)."""

from __future__ import annotations

import datetime as dt
import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any

from access.models import (
    AuditEvent,
    Capability,
    InstitutionMembership,
    Role,
    RoleAssignment,
    Scope,
)
from access.services import assign
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from academic.models import (
    AcademicTerm,
    Assessment,
    Course,
    CourseOffering,
    Department,
    Enrollment,
    Grade,
    GradeBatch,
    Institution,
    InstructorAssignment,
    Program,
    ProgramCourse,
    ProgramMembership,
    ProgramOutcome,
    ProgramOutcomeSet,
    Publication,
    Syllabus,
    SyllabusAssessment,
)
from academic.services import (
    CalculationService,
    EnrollmentService,
    GradeBatchService,
    GradeService,
    ProgramOutcomeSetService,
    PublicationService,
    SyllabusService,
)

User = get_user_model()

PO_SEED_FILE = Path(__file__).resolve().parents[2] / "seed_data" / "program_outcomes.json"

SYNTHETIC_FIRST_NAMES = (
    "Ahmet",
    "Ayşe",
    "Burak",
    "Ceren",
    "Defne",
    "Emir",
    "Fatma",
    "Gökhan",
    "Hakan",
    "İpek",
    "Kaan",
    "Leyla",
    "Melis",
    "Nehir",
    "Oğuz",
    "Pelin",
    "Rüzgar",
    "Seda",
    "Tarık",
    "Ufuk",
)

SYNTHETIC_LAST_NAMES = (
    "Akın",
    "Bulut",
    "Coşkun",
    "Doğan",
    "Erdoğan",
    "Güneş",
    "Işık",
    "Kılıç",
    "Koç",
    "Kurt",
    "Öztürk",
    "Polat",
    "Şahin",
    "Taş",
    "Uçar",
    "Vural",
    "Yalçın",
    "Yıldırım",
    "Yüksel",
    "Zengin",
)

# 40 deterministic synthetic cohort students spanning all 4 attainment bands (<50, 50-69.9, 70-84.9, 85-100).
SYNTHETIC_SCORE_BANDS: tuple[tuple[int, int], ...] = (
    # Band 85-100 (11 students)
    (96, 94),
    (93, 91),
    (92, 88),
    (90, 92),
    (89, 87),
    (88, 91),
    (87, 89),
    (86, 88),
    (94, 85),
    (91, 86),
    (88, 86),
    # Band 70-84.9 (15 students)
    (84, 82),
    (82, 80),
    (81, 79),
    (80, 78),
    (79, 81),
    (78, 76),
    (77, 79),
    (76, 75),
    (75, 78),
    (74, 76),
    (73, 74),
    (72, 75),
    (71, 73),
    (70, 74),
    (83, 77),
    # Band 50-69.9 (9 students)
    (68, 66),
    (66, 64),
    (64, 62),
    (62, 65),
    (60, 58),
    (58, 61),
    (56, 54),
    (54, 57),
    (52, 55),
    # Band <50 (5 students)
    (48, 46),
    (45, 42),
    (41, 39),
    (38, 44),
    (34, 36),
)


def _grant_role(user: Any, scope_id: Any, role_slug: str) -> RoleAssignment:
    return RoleAssignment.objects.get_or_create(
        user=user,
        scope_id=scope_id,
        role_id=role_slug,
        revoked_at__isnull=True,
    )[0]


def _ensure_user(
    *,
    username: str,
    email: str,
    first_name: str,
    last_name: str,
    password: str,
    is_staff: bool = False,
    is_superuser: bool = False,
) -> Any:
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "is_active": True,
            "is_staff": is_staff,
            "is_superuser": is_superuser,
        },
    )
    changed_fields: list[str] = []
    for attr, expected in (
        ("email", email),
        ("first_name", first_name),
        ("last_name", last_name),
        ("is_active", True),
        ("is_staff", is_staff),
        ("is_superuser", is_superuser),
    ):
        if getattr(user, attr) != expected:
            setattr(user, attr, expected)
            changed_fields.append(attr)
    if created or not user.check_password(password):
        user.set_password(password)
        changed_fields.append("password")
    if changed_fields:
        user.save(update_fields=changed_fields)
    return user


def _ensure_audit_event(
    *,
    seed_key: str,
    actor: Any,
    scope: Scope,
    action: str,
    metadata: dict[str, Any],
    subject: Any = None,
) -> AuditEvent:
    existing = AuditEvent.objects.filter(
        action=action,
        scope=scope,
        metadata__seed_key=seed_key,
    ).first()
    if existing is not None:
        return existing
    return AuditEvent.objects.create(
        actor=actor,
        subject=subject,
        scope=scope,
        action=action,
        metadata={"seed_key": seed_key, **metadata},
    )


def _ensure_po_set(
    *,
    program: Program,
    version: int,
    effective_date: dt.date,
    source_reference: str,
    outcomes_data: list[dict[str, str]],
    actor: Any,
) -> ProgramOutcomeSet:
    po_set = ProgramOutcomeSet.objects.filter(program=program, version=version).first()
    if po_set is None:
        po_set = ProgramOutcomeSet.objects.create(
            program=program,
            version=version,
            source_reference=source_reference,
        )
        for index, item in enumerate(outcomes_data, start=1):
            ProgramOutcome.objects.create(
                outcome_set=po_set,
                code=item["code"],
                label=item["label"],
                description=item["description"],
                source_url=item["source_url"],
                ordering=index,
            )
    if po_set.status != ProgramOutcomeSet.Status.ACTIVE:
        po_set = ProgramOutcomeSetService(actor=actor).activate(
            instance=po_set,
            effective_date=effective_date,
            authorize=False,
        )
    return po_set


def _ensure_enrollment(
    *,
    offering: CourseOffering,
    student: Any,
    actor: Any,
    status: str = Enrollment.Status.ENROLLED,
    withdraw_reason: str = "",
) -> Enrollment:
    _grant_role(student, offering.pk, "student")
    enr = Enrollment.objects.filter(offering=offering, student=student).first()
    if enr is None:
        enr = EnrollmentService().create(
            offering=offering,
            student=student,
            status=Enrollment.Status.ENROLLED,
            actor=actor,
        )
    if status != enr.status:
        enr = EnrollmentService().update_status(
            enrollment=enr,
            status=status,
            reason=withdraw_reason or "Enrollment status updated",
            actor=actor,
        )
    return enr


def _ensure_grade(
    *,
    enrollment: Enrollment,
    assessment: Assessment,
    batch: GradeBatch,
    state: str,
    points_earned: Decimal | None,
    actor: Any,
    reason: str = "",
) -> Grade:
    existing = Grade.objects.filter(enrollment=enrollment, assessment=assessment).first()
    if existing is not None:
        return existing
    effective_reason = reason or ("Demo seed grade" if batch.released_at is not None else "")
    return GradeService().create(
        enrollment=enrollment,
        assessment=assessment,
        batch=batch,
        state=state,
        points_earned=points_earned,
        reason=effective_reason,
        actor=actor,
    )


def _backfill_preexisting_enrollments(
    *,
    offering: CourseOffering,
    assessments: list[Assessment],
    batch: GradeBatch,
    actor: Any,
    default_score: Decimal = Decimal("80.00"),
) -> None:
    """Ensure any pre-existing eligible enrollments (e.g. from seed_acibadem) have grades."""
    for enr in offering.enrollments.filter(eligible_for_outcomes=True):
        for asmt in assessments:
            _ensure_grade(
                enrollment=enr,
                assessment=asmt,
                batch=batch,
                state=Grade.State.SCORED,
                points_earned=min(default_score, asmt.points_possible),
                actor=actor,
                reason="Demo seed baseline grade",
            )


def _ensure_approved_syllabus(
    *,
    offering: CourseOffering,
    po_set: ProgramOutcomeSet,
    actor: Any,
    learning_outcomes: list[tuple[str, str]],
    assessments: list[tuple[str, str, Decimal]],
    assessment_lo_weights: list[tuple[str, str, Decimal]],
    lo_po_weights: list[tuple[str, str, int]],
    course_po_weights: list[tuple[str, int]],
) -> Syllabus:
    existing = offering.syllabi.filter(version=1).first()
    if existing is not None:
        return existing

    syl_svc = SyllabusService()
    syl = syl_svc.create(offering=offering, po_set_version=po_set.version)
    po_by_code = {po.code: po for po in po_set.outcomes.all()}

    lo_by_code = {}
    for order, (code, description) in enumerate(learning_outcomes, start=1):
        lo_by_code[code] = syl_svc.add_learning_outcome(
            syllabus=syl, code=code, description=description, order=order
        )

    sa_by_code = {}
    for order, (code, kind, max_points) in enumerate(assessments, start=1):
        sa_by_code[code] = syl_svc.add_assessment(
            syllabus=syl,
            code=code,
            kind=kind,
            order=order,
            max_points=max_points,
            is_required=True,
            is_active=True,
        )

    syl = syl_svc.replace_assessment_lo_matrix(
        syllabus=syl,
        expected_revision=syl.mapping_revision,
        mappings=[
            {
                "assessment": sa_by_code[a_code].pk,
                "learning_outcome": lo_by_code[lo_code].pk,
                "weight": weight,
            }
            for a_code, lo_code, weight in assessment_lo_weights
        ],
    )
    syl = syl_svc.replace_lo_po_matrix(
        syllabus=syl,
        expected_revision=syl.mapping_revision,
        mappings=[
            {
                "learning_outcome": lo_by_code[lo_code].pk,
                "program_outcome": po_by_code[po_code].pk,
                "weight": weight,
            }
            for lo_code, po_code, weight in lo_po_weights
        ],
    )
    for po_code, weight in course_po_weights:
        syl_svc.set_po_contribution(
            syllabus=syl,
            program_outcome=po_by_code[po_code],
            weight=weight,
        )
    return syl_svc.approve(syllabus=syl, actor=actor)


def _ensure_published(
    *,
    program: Program,
    offering: CourseOffering | None,
    term: AcademicTerm,
    audience: str,
    idempotency_key: str,
    actor: Any,
) -> Publication:
    lookup = Publication.objects.filter(
        program=program,
        audience=audience,
        idempotency_key=idempotency_key,
    )
    if offering is None:
        lookup = lookup.filter(offering__isnull=True)
    else:
        lookup = lookup.filter(offering=offering)
    existing = lookup.first()
    if existing is not None:
        return existing

    calc_svc = CalculationService()
    if offering is None:
        run, _ = calc_svc.run_program(program=program, actor=actor)
    else:
        run, _ = calc_svc.run_offering(offering=offering, actor=actor)

    series_qs = Publication.objects.filter(program=program, audience=audience)
    if offering is None:
        series_qs = series_qs.filter(offering__isnull=True)
    else:
        series_qs = series_qs.filter(offering=offering)
    latest = series_qs.order_by("-series_version").first()
    expected_series_version = latest.series_version if latest is not None else 0

    pub, _ = PublicationService().publish(
        actor=actor,
        run=run,
        expected_series_version=expected_series_version,
        expected_input_hash=run.input_hash,
        audience=audience,
        idempotency_key=idempotency_key,
        term=term,
    )
    return pub


class Command(BaseCommand):
    help = (
        "Seed a deterministic, idempotent Acibadem University CSE demo dataset "
        "covering PRD §5/§11.4 calculations, M:N programs/courses, edge cases, "
        "direct capability grants, versioned PO sets, publications, and audit events."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            type=str,
            default="",
            help="Override demo account password (defaults to DEMO_SEED_PASSWORD env var).",
        )

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        if not settings.DEBUG or (
            db["ENGINE"] != "django.db.backends.sqlite3"
            and db.get("HOST") not in ("localhost", "127.0.0.1", "::1")
        ):
            raise CommandError("Demo seed requires DEBUG and a local database.")

        password = options["password"].strip() or os.environ.get("DEMO_SEED_PASSWORD", "").strip()
        if not password:
            raise CommandError(
                "Set DEMO_SEED_PASSWORD in .env (or supply the --password option) to run seed_demo."
            )

        po_payload = json.loads(PO_SEED_FILE.read_text(encoding="utf-8"))
        outcomes_v2 = po_payload["outcomes"]
        outcomes_v1 = [
            {
                **item,
                "description": f"Legacy v1 curriculum outcome: {item['label']}.",
            }
            for item in outcomes_v2
        ]

        # Ensure standard roles/capabilities exist (created by access migrations).
        if not Role.objects.filter(pk="administrator").exists():
            raise CommandError("Access roles are missing; run migrate before seed_demo.")

        self.stdout.write(self.style.NOTICE("=== Seeding deterministic Outcometrik demo data ==="))

        with transaction.atomic():
            # 1. Institution, Department, Programs (M:N demo: CSE & SWE)
            inst, _ = Institution.objects.get_or_create(
                code="ACU",
                defaults={"name": "Acıbadem Mehmet Ali Aydınlar University"},
            )
            cse_dept, _ = Department.objects.get_or_create(
                institution=inst,
                code="CSE",
                defaults={"name": "Department of Computer Engineering"},
            )
            cse_program, _ = Program.objects.get_or_create(
                department=cse_dept,
                code="CSE",
                defaults={
                    "title": "B.Sc. Computer Engineering",
                    "status": Program.Status.ACTIVE,
                },
            )
            swe_program, _ = Program.objects.get_or_create(
                department=cse_dept,
                code="SWE",
                defaults={
                    "title": "B.Sc. Software Engineering",
                    "status": Program.Status.ACTIVE,
                },
            )

            # 2. Academic Terms
            term_2025_fall, _ = AcademicTerm.objects.get_or_create(
                institution=inst,
                year=2025,
                season=AcademicTerm.Season.FALL,
                defaults={
                    "starts_at": dt.date(2025, 9, 15),
                    "ends_at": dt.date(2026, 1, 20),
                },
            )
            term_2026_spring, _ = AcademicTerm.objects.get_or_create(
                institution=inst,
                year=2026,
                season=AcademicTerm.Season.SPRING,
                defaults={
                    "starts_at": dt.date(2026, 2, 9),
                    "ends_at": dt.date(2026, 6, 19),
                },
            )
            term_2026_fall, _ = AcademicTerm.objects.get_or_create(
                institution=inst,
                year=2026,
                season=AcademicTerm.Season.FALL,
                defaults={
                    "starts_at": dt.date(2026, 9, 14),
                    "ends_at": dt.date(2027, 1, 22),
                },
            )

            # 3. Courses & M:N ProgramCourse links
            course_specs = [
                ("CSE311", "Software Engineering", 6, 4, (cse_program, swe_program)),
                ("CSE321", "Database Systems", 6, 4, (cse_program, swe_program)),
                ("CSE214", "Data Structures and Algorithms", 6, 4, (cse_program, swe_program)),
                ("CSE301", "Computer Architecture", 5, 3, (cse_program,)),
                ("SWE310", "Software Verification and Validation", 5, 3, (swe_program,)),
            ]
            courses: dict[str, Course] = {}
            for code, title, ects, credits, linked_programs in course_specs:
                course, _ = Course.objects.get_or_create(
                    home_department=cse_dept,
                    code=code,
                    defaults={
                        "title": title,
                        "ects": ects,
                        "credits": credits,
                        "active": True,
                    },
                )
                courses[code] = course
                for prog in linked_programs:
                    ProgramCourse.objects.get_or_create(
                        program=prog,
                        course=course,
                        defaults={
                            "effective_from": dt.date(2024, 9, 1),
                            "status": ProgramCourse.Status.APPROVED,
                        },
                    )

            # 4. Staff Users & Scoped Roles
            admin_user = _ensure_user(
                username="admin@acibadem.edu.tr",
                email="admin@acibadem.edu.tr",
                first_name="System",
                last_name="Administrator",
                password=password,
                is_staff=True,
                is_superuser=True,
            )
            coord_user = _ensure_user(
                username="emre.karahan@acibadem.edu.tr",
                email="emre.karahan@acibadem.edu.tr",
                first_name="Emre",
                last_name="Karahan",
                password=password,
            )
            instructor_user = _ensure_user(
                username="selin.kaya@acibadem.edu.tr",
                email="selin.kaya@acibadem.edu.tr",
                first_name="Selin",
                last_name="Kaya",
                password=password,
            )

            for staff_user in (admin_user, coord_user, instructor_user):
                InstitutionMembership.objects.get_or_create(user=staff_user, institution_id=inst.pk)

            _grant_role(admin_user, inst.pk, "administrator")
            _grant_role(coord_user, cse_program.pk, "program-coordinator")
            _grant_role(coord_user, swe_program.pk, "program-coordinator")

            # 5. Named Students + 40 Synthetic Cohort Students (45 total)
            named_students_spec = [
                ("deniz.aydin@live.acibadem.edu.tr", "Deniz", "Aydın", "2023041018"),
                ("kerem.yilmaz@live.acibadem.edu.tr", "Kerem", "Yılmaz", "2023041019"),
                ("ece.demir@live.acibadem.edu.tr", "Ece", "Demir", "2023041020"),
                ("mert.celik@live.acibadem.edu.tr", "Mert", "Çelik", "2023041021"),
                ("zeynep.arslan@live.acibadem.edu.tr", "Zeynep", "Arslan", "2023041022"),
            ]
            named_students: dict[str, Any] = {}
            for email, first_name, last_name, student_number in named_students_spec:
                user = _ensure_user(
                    username=email,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    password=password,
                )
                InstitutionMembership.objects.get_or_create(user=user, institution_id=inst.pk)
                ProgramMembership.objects.get_or_create(
                    program=cse_program,
                    user=user,
                    defaults={
                        "student_number": student_number,
                        "admitted_term": term_2025_fall,
                        "status": ProgramMembership.Status.ACTIVE,
                    },
                )
                named_students[student_number] = user

            deniz = named_students["2023041018"]
            kerem = named_students["2023041019"]
            ece = named_students["2023041020"]
            mert = named_students["2023041021"]
            zeynep = named_students["2023041022"]

            # Also enroll Deniz in SWE program for M:N visibility if needed? No, keep Deniz cleanly in CSE.
            synthetic_students: list[tuple[Any, int, int]] = []
            for idx, (mid_score, proj_score) in enumerate(SYNTHETIC_SCORE_BANDS, start=1):
                first_name = SYNTHETIC_FIRST_NAMES[(idx - 1) % len(SYNTHETIC_FIRST_NAMES)]
                last_name = SYNTHETIC_LAST_NAMES[(idx - 1 + idx // 2) % len(SYNTHETIC_LAST_NAMES)]
                email = f"student{idx:02d}@live.acibadem.edu.tr"
                student_number = f"20230411{idx:02d}"
                user = _ensure_user(
                    username=email,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    password=password,
                )
                InstitutionMembership.objects.get_or_create(user=user, institution_id=inst.pk)
                ProgramMembership.objects.get_or_create(
                    program=cse_program,
                    user=user,
                    defaults={
                        "student_number": student_number,
                        "admitted_term": term_2025_fall,
                        "status": ProgramMembership.Status.ACTIVE,
                    },
                )
                if idx <= 10:
                    ProgramMembership.objects.get_or_create(
                        program=swe_program,
                        user=user,
                        defaults={
                            "student_number": f"20230421{idx:02d}",
                            "admitted_term": term_2025_fall,
                            "status": ProgramMembership.Status.ACTIVE,
                        },
                    )
                synthetic_students.append((user, mid_score, proj_score))

            # 6. Stage A: Historical PO-Set v1 + 2025-2026 Fall publication (for trend incompatibility testing)
            po_set_v1 = _ensure_po_set(
                program=cse_program,
                version=1,
                effective_date=dt.date(2024, 9, 1),
                source_reference="Acıbadem CSE PO-Set v1 (2024 historical archive)",
                outcomes_data=outcomes_v1,
                actor=coord_user,
            )
            _ensure_po_set(
                program=swe_program,
                version=1,
                effective_date=dt.date(2026, 1, 15),
                source_reference="Acıbadem SWE PO-Set v1 (2026 active)",
                outcomes_data=outcomes_v2,
                actor=coord_user,
            )

            off_hist_v1, _ = CourseOffering.objects.get_or_create(
                program=cse_program,
                course=courses["CSE301"],
                term=term_2025_fall,
                section="01",
                defaults={"status": CourseOffering.Status.ACTIVE},
            )
            InstructorAssignment.objects.get_or_create(
                offering=off_hist_v1,
                user=instructor_user,
                defaults={"assignment_role": InstructorAssignment.Role.INSTRUCTOR},
            )
            _grant_role(instructor_user, off_hist_v1.pk, "instructor")

            _ensure_approved_syllabus(
                offering=off_hist_v1,
                po_set=po_set_v1,
                actor=coord_user,
                learning_outcomes=[
                    ("LO1", "Analyze processor datapaths and memory hierarchies"),
                ],
                assessments=[
                    ("Exam", SyllabusAssessment.Kind.EXAM, Decimal("100.00")),
                ],
                assessment_lo_weights=[
                    ("Exam", "LO1", Decimal("100.00")),
                ],
                lo_po_weights=[
                    ("LO1", "PO1", 3),
                    ("LO1", "PO3", 3),
                ],
                course_po_weights=[
                    ("PO1", 4),
                    ("PO3", 4),
                ],
            )
            asmt_hist_v1, _ = Assessment.objects.get_or_create(
                offering=off_hist_v1,
                title="Exam",
                defaults={
                    "points_possible": Decimal("100.00"),
                    "status": Assessment.Status.APPROVED,
                },
            )
            batch_hist_v1 = GradeBatch.objects.filter(
                offering=off_hist_v1, name="Demo 2025 Fall Final Release"
            ).first()
            if batch_hist_v1 is None:
                batch_hist_v1 = GradeBatchService().create(
                    offering=off_hist_v1, name="Demo 2025 Fall Final Release"
                )
            for stu, score in [
                (deniz, Decimal("82.00")),
                (kerem, Decimal("68.00")),
                (ece, Decimal("84.00")),
                (mert, Decimal("75.00")),
            ] + [(u, Decimal(str(max(30, min(98, m - 3))))) for u, m, _ in synthetic_students]:
                enr = _ensure_enrollment(offering=off_hist_v1, student=stu, actor=coord_user)
                _ensure_grade(
                    enrollment=enr,
                    assessment=asmt_hist_v1,
                    batch=batch_hist_v1,
                    state=Grade.State.SCORED,
                    points_earned=score,
                    actor=instructor_user,
                )
            _backfill_preexisting_enrollments(
                offering=off_hist_v1,
                assessments=[asmt_hist_v1],
                batch=batch_hist_v1,
                actor=instructor_user,
            )
            if batch_hist_v1.released_at is None:
                GradeBatchService().release(batch=batch_hist_v1, actor=coord_user)

            # Publish PO-Set v1 historical snapshot BEFORE activating PO-Set v2.
            _ensure_published(
                program=cse_program,
                offering=None,
                term=term_2025_fall,
                audience=Publication.Audience.FACULTY,
                idempotency_key="demo-cse-2025-fall-po-v1-faculty",
                actor=coord_user,
            )

            # 7. Stage B: Activate PO-Set v2 (11 authoritative Acibadem POs) + 2025-2026 Spring publication
            v2_effective_date = max(
                dt.date(2026, 1, 15),
                (po_set_v1.effective_date or dt.date(2024, 9, 1)) + dt.timedelta(days=1),
            )
            po_set_v2 = _ensure_po_set(
                program=cse_program,
                version=2,
                effective_date=v2_effective_date,
                source_reference=po_payload["source_reference"],
                outcomes_data=outcomes_v2,
                actor=coord_user,
            )

            off_spring_301, _ = CourseOffering.objects.get_or_create(
                program=cse_program,
                course=courses["CSE301"],
                term=term_2026_spring,
                section="01",
                defaults={"status": CourseOffering.Status.ACTIVE},
            )
            InstructorAssignment.objects.get_or_create(
                offering=off_spring_301,
                user=instructor_user,
                defaults={"assignment_role": InstructorAssignment.Role.INSTRUCTOR},
            )
            _grant_role(instructor_user, off_spring_301.pk, "instructor")

            _ensure_approved_syllabus(
                offering=off_spring_301,
                po_set=po_set_v2,
                actor=coord_user,
                learning_outcomes=[
                    ("LO1", "Evaluate instruction set architectures and pipelining"),
                    ("LO2", "Design cache and virtual memory subsystems"),
                ],
                assessments=[
                    ("Midterm", SyllabusAssessment.Kind.EXAM, Decimal("100.00")),
                    ("Lab", SyllabusAssessment.Kind.LAB, Decimal("100.00")),
                ],
                assessment_lo_weights=[
                    ("Midterm", "LO1", Decimal("70.00")),
                    ("Lab", "LO1", Decimal("30.00")),
                    ("Lab", "LO2", Decimal("100.00")),
                ],
                lo_po_weights=[
                    ("LO1", "PO3", 4),
                    ("LO1", "PO5", 3),
                    ("LO2", "PO6", 3),
                    ("LO2", "PO8", 2),
                ],
                course_po_weights=[
                    ("PO3", 4),
                    ("PO5", 3),
                    ("PO6", 3),
                    ("PO8", 2),
                ],
            )
            asmt_sp_mid, _ = Assessment.objects.get_or_create(
                offering=off_spring_301,
                title="Midterm",
                defaults={
                    "points_possible": Decimal("100.00"),
                    "status": Assessment.Status.APPROVED,
                },
            )
            asmt_sp_lab, _ = Assessment.objects.get_or_create(
                offering=off_spring_301,
                title="Lab",
                defaults={
                    "points_possible": Decimal("100.00"),
                    "status": Assessment.Status.APPROVED,
                },
            )
            batch_sp = GradeBatch.objects.filter(
                offering=off_spring_301, name="Demo 2026 Spring Final Release"
            ).first()
            if batch_sp is None:
                batch_sp = GradeBatchService().create(
                    offering=off_spring_301, name="Demo 2026 Spring Final Release"
                )
            for stu, s_mid, s_lab in [
                (deniz, Decimal("84.00"), Decimal("88.00")),
                (kerem, Decimal("64.00"), Decimal("70.00")),
                (ece, Decimal("86.00"), Decimal("82.00")),
                (mert, Decimal("76.00"), Decimal("74.00")),
            ] + [
                (u, Decimal(str(max(30, min(98, m - 2)))), Decimal(str(max(30, min(98, p - 1)))))
                for u, m, p in synthetic_students
            ]:
                enr = _ensure_enrollment(offering=off_spring_301, student=stu, actor=coord_user)
                _ensure_grade(
                    enrollment=enr,
                    assessment=asmt_sp_mid,
                    batch=batch_sp,
                    state=Grade.State.SCORED,
                    points_earned=s_mid,
                    actor=instructor_user,
                )
                _ensure_grade(
                    enrollment=enr,
                    assessment=asmt_sp_lab,
                    batch=batch_sp,
                    state=Grade.State.SCORED,
                    points_earned=s_lab,
                    actor=instructor_user,
                )
            _backfill_preexisting_enrollments(
                offering=off_spring_301,
                assessments=[asmt_sp_mid, asmt_sp_lab],
                batch=batch_sp,
                actor=instructor_user,
            )
            if batch_sp.released_at is None:
                GradeBatchService().release(batch=batch_sp, actor=coord_user)

            # Publish 2025-2026 Spring historical snapshot on compatible PO-Set v2.
            _ensure_published(
                program=cse_program,
                offering=None,
                term=term_2026_spring,
                audience=Publication.Audience.FACULTY,
                idempotency_key="demo-cse-2026-spring-po-v2-faculty",
                actor=coord_user,
            )

            # 8. Stage C: Active 2026-2027 Fall Offerings & PRD §5 / §11.4 Reference Scenario
            off_311_01, _ = CourseOffering.objects.get_or_create(
                program=cse_program,
                course=courses["CSE311"],
                term=term_2026_fall,
                section="01",
                defaults={"status": CourseOffering.Status.ACTIVE},
            )
            off_311_02, _ = CourseOffering.objects.get_or_create(
                program=cse_program,
                course=courses["CSE311"],
                term=term_2026_fall,
                section="02",
                defaults={"status": CourseOffering.Status.ACTIVE},
            )
            off_321_01, _ = CourseOffering.objects.get_or_create(
                program=cse_program,
                course=courses["CSE321"],
                term=term_2026_fall,
                section="01",
                defaults={"status": CourseOffering.Status.ACTIVE},
            )
            off_214_01_cse, _ = CourseOffering.objects.get_or_create(
                program=cse_program,
                course=courses["CSE214"],
                term=term_2026_fall,
                section="01",
                defaults={"status": CourseOffering.Status.ACTIVE},
            )
            off_214_01_swe, _ = CourseOffering.objects.get_or_create(
                program=swe_program,
                course=courses["CSE214"],
                term=term_2026_fall,
                section="01",
                defaults={"status": CourseOffering.Status.ACTIVE},
            )

            # Instructor assignments (Emre Karahan overlaps Coordinator + Instructor on CSE 321-01)
            for off, faculty in (
                (off_311_01, instructor_user),
                (off_311_02, instructor_user),
                (off_214_01_cse, instructor_user),
                (off_214_01_swe, instructor_user),
                (off_321_01, coord_user),
            ):
                InstructorAssignment.objects.get_or_create(
                    offering=off,
                    user=faculty,
                    defaults={"assignment_role": InstructorAssignment.Role.INSTRUCTOR},
                )
                _grant_role(faculty, off.pk, "instructor")

            # Direct Capability Grants (AUTH-02): at least 2 active grants with AuditEvents
            assign(
                actor=admin_user,
                user=instructor_user,
                scope=Scope.objects.get(pk=off_311_01.pk),
                capability=Capability.objects.get(pk="grades.release"),
            )
            assign(
                actor=admin_user,
                user=instructor_user,
                scope=Scope.objects.get(pk=cse_program.pk),
                capability=Capability.objects.get(pk="outcomes.view"),
            )
            assign(
                actor=admin_user,
                user=instructor_user,
                scope=Scope.objects.get(pk=off_311_01.pk),
                capability=Capability.objects.get(pk="grades.export"),
            )

            # CSE 311-01 Syllabus v1 (exact PRD §5 scenario)
            syl_311_v1 = _ensure_approved_syllabus(
                offering=off_311_01,
                po_set=po_set_v2,
                actor=coord_user,
                learning_outcomes=[
                    ("LO1", "Analyze requirements and architect modular software systems"),
                    ("LO2", "Implement, verify, and deliver production-ready software"),
                ],
                assessments=[
                    ("Midterm", SyllabusAssessment.Kind.EXAM, Decimal("100.00")),
                    ("Project", SyllabusAssessment.Kind.PROJECT, Decimal("100.00")),
                ],
                assessment_lo_weights=[
                    ("Midterm", "LO1", Decimal("60.00")),
                    ("Project", "LO1", Decimal("40.00")),
                    ("Midterm", "LO2", Decimal("40.00")),
                    ("Project", "LO2", Decimal("100.00")),
                ],
                lo_po_weights=[
                    ("LO1", "PO1", 2),
                    ("LO2", "PO1", 1),
                    ("LO2", "PO2", 1),
                ],
                course_po_weights=[
                    ("PO1", 5),
                    ("PO2", 4),
                ],
            )

            # CSE 321-01 Syllabus v1 (exact PRD §11.4 Course->PO1 weight = 3)
            _ensure_approved_syllabus(
                offering=off_321_01,
                po_set=po_set_v2,
                actor=coord_user,
                learning_outcomes=[
                    ("LO1", "Design normalized relational schemas and query plans"),
                    ("LO2", "Ensure transactional integrity and concurrency control"),
                ],
                assessments=[
                    ("Midterm", SyllabusAssessment.Kind.EXAM, Decimal("100.00")),
                    ("Lab", SyllabusAssessment.Kind.LAB, Decimal("100.00")),
                ],
                assessment_lo_weights=[
                    ("Midterm", "LO1", Decimal("60.00")),
                    ("Lab", "LO1", Decimal("40.00")),
                    ("Lab", "LO2", Decimal("100.00")),
                ],
                lo_po_weights=[
                    ("LO1", "PO1", 3),
                    ("LO2", "PO4", 4),
                    ("LO2", "PO5", 3),
                ],
                course_po_weights=[
                    ("PO1", 3),
                    ("PO4", 4),
                    ("PO5", 3),
                ],
            )

            # CSE 214-01 (CSE) Syllabus v1 (contributes to PO3, PO7, PO9 — leaves PO10 & PO11 unassessed)
            _ensure_approved_syllabus(
                offering=off_214_01_cse,
                po_set=po_set_v2,
                actor=coord_user,
                learning_outcomes=[
                    ("LO1", "Analyze algorithmic complexity and tree/graph data structures"),
                    ("LO2", "Communicate algorithmic proofs and collaborative solutions"),
                ],
                assessments=[
                    ("Midterm", SyllabusAssessment.Kind.EXAM, Decimal("100.00")),
                    ("Homework", SyllabusAssessment.Kind.HOMEWORK, Decimal("100.00")),
                ],
                assessment_lo_weights=[
                    ("Midterm", "LO1", Decimal("60.00")),
                    ("Homework", "LO1", Decimal("40.00")),
                    ("Homework", "LO2", Decimal("100.00")),
                ],
                lo_po_weights=[
                    ("LO1", "PO3", 4),
                    ("LO2", "PO7", 3),
                    ("LO2", "PO9", 2),
                ],
                course_po_weights=[
                    ("PO3", 4),
                    ("PO7", 3),
                    ("PO9", 2),
                ],
            )

            # CSE 311-02 Draft Syllabus (for instructor multi-section workspace)
            if not off_311_02.syllabi.exists():
                syl_311_02 = SyllabusService().create(
                    offering=off_311_02, po_set_version=po_set_v2.version
                )
                SyllabusService().add_learning_outcome(
                    syllabus=syl_311_02,
                    code="LO1",
                    description="Analyze requirements and architect modular software systems",
                    order=1,
                )
                SyllabusService().add_assessment(
                    syllabus=syl_311_02,
                    code="Midterm",
                    kind=SyllabusAssessment.Kind.EXAM,
                    order=1,
                    max_points=Decimal("100.00"),
                    is_required=True,
                    is_active=True,
                )

            # Gradebook Assessments & Grades for CSE 311-01
            asmt_311_mid, _ = Assessment.objects.get_or_create(
                offering=off_311_01,
                title="Midterm",
                defaults={
                    "points_possible": Decimal("100.00"),
                    "status": Assessment.Status.APPROVED,
                },
            )
            asmt_311_proj, _ = Assessment.objects.get_or_create(
                offering=off_311_01,
                title="Project",
                defaults={
                    "points_possible": Decimal("100.00"),
                    "status": Assessment.Status.APPROVED,
                },
            )
            batch_311 = GradeBatch.objects.filter(
                offering=off_311_01, name="Demo CSE311 Midterm & Project Release"
            ).first()
            if batch_311 is None:
                batch_311 = GradeBatchService().create(
                    offering=off_311_01, name="Demo CSE311 Midterm & Project Release"
                )

            # Deniz Aydin: PRD §5 reference (90/100, 80/100)
            enr_deniz_311 = _ensure_enrollment(offering=off_311_01, student=deniz, actor=coord_user)
            _ensure_grade(
                enrollment=enr_deniz_311,
                assessment=asmt_311_mid,
                batch=batch_311,
                state=Grade.State.SCORED,
                points_earned=Decimal("90.00"),
                actor=instructor_user,
            )
            _ensure_grade(
                enrollment=enr_deniz_311,
                assessment=asmt_311_proj,
                batch=batch_311,
                state=Grade.State.SCORED,
                points_earned=Decimal("80.00"),
                actor=instructor_user,
            )

            # Kerem Yilmaz: explicit numeric 0.0 edge case
            enr_kerem_311 = _ensure_enrollment(offering=off_311_01, student=kerem, actor=coord_user)
            _ensure_grade(
                enrollment=enr_kerem_311,
                assessment=asmt_311_mid,
                batch=batch_311,
                state=Grade.State.SCORED,
                points_earned=Decimal("0.00"),
                actor=instructor_user,
                reason="Explicit zero score recorded",
            )
            _ensure_grade(
                enrollment=enr_kerem_311,
                assessment=asmt_311_proj,
                batch=batch_311,
                state=Grade.State.SCORED,
                points_earned=Decimal("65.00"),
                actor=instructor_user,
            )

            # Ece Demir: EXEMPT edge case (removed from denominator)
            enr_ece_311 = _ensure_enrollment(offering=off_311_01, student=ece, actor=coord_user)
            _ensure_grade(
                enrollment=enr_ece_311,
                assessment=asmt_311_mid,
                batch=batch_311,
                state=Grade.State.EXEMPT,
                points_earned=None,
                actor=instructor_user,
                reason="Approved medical exemption",
            )
            _ensure_grade(
                enrollment=enr_ece_311,
                assessment=asmt_311_proj,
                batch=batch_311,
                state=Grade.State.SCORED,
                points_earned=Decimal("88.00"),
                actor=instructor_user,
            )

            # Mert Celik: initially scored so 2026-2027 Fall Publication v1 can be published,
            # then corrected to blocking MISSING (ABSENT) post-publication in Stage D.
            enr_mert_311 = _ensure_enrollment(offering=off_311_01, student=mert, actor=coord_user)
            _ensure_grade(
                enrollment=enr_mert_311,
                assessment=asmt_311_mid,
                batch=batch_311,
                state=Grade.State.SCORED,
                points_earned=Decimal("74.00"),
                actor=instructor_user,
            )
            grade_mert_proj = _ensure_grade(
                enrollment=enr_mert_311,
                assessment=asmt_311_proj,
                batch=batch_311,
                state=Grade.State.SCORED,
                points_earned=Decimal("70.00"),
                actor=instructor_user,
            )

            # Zeynep Arslan: WITHDRAWN enrollment edge case
            _ensure_enrollment(
                offering=off_311_01,
                student=zeynep,
                actor=coord_user,
                status=Enrollment.Status.WITHDRAWN,
                withdraw_reason="Withdrew before add/drop deadline",
            )

            # 40 synthetic cohort students in CSE 311-01
            for stu, mid_score, proj_score in synthetic_students:
                enr = _ensure_enrollment(offering=off_311_01, student=stu, actor=coord_user)
                _ensure_grade(
                    enrollment=enr,
                    assessment=asmt_311_mid,
                    batch=batch_311,
                    state=Grade.State.SCORED,
                    points_earned=Decimal(f"{mid_score}.00"),
                    actor=instructor_user,
                )
                _ensure_grade(
                    enrollment=enr,
                    assessment=asmt_311_proj,
                    batch=batch_311,
                    state=Grade.State.SCORED,
                    points_earned=Decimal(f"{proj_score}.00"),
                    actor=instructor_user,
                )

            _backfill_preexisting_enrollments(
                offering=off_311_01,
                assessments=[asmt_311_mid, asmt_311_proj],
                batch=batch_311,
                actor=instructor_user,
            )
            if batch_311.released_at is None:
                GradeBatchService().release(batch=batch_311, actor=coord_user)

            # Gradebook Assessments & Grades for CSE 321-01
            # Deniz Aydin gets 90.04/100 (displays as 90.0) so unrounded cumulative PO1:
            # (5 * 84.95238095... + 3 * 90.04) / 8 = 86.860238... -> displays 86.9!
            asmt_321_mid, _ = Assessment.objects.get_or_create(
                offering=off_321_01,
                title="Midterm",
                defaults={
                    "points_possible": Decimal("100.00"),
                    "status": Assessment.Status.APPROVED,
                },
            )
            asmt_321_lab, _ = Assessment.objects.get_or_create(
                offering=off_321_01,
                title="Lab",
                defaults={
                    "points_possible": Decimal("100.00"),
                    "status": Assessment.Status.APPROVED,
                },
            )
            batch_321 = GradeBatch.objects.filter(
                offering=off_321_01, name="Demo CSE321 Midterm & Lab Release"
            ).first()
            if batch_321 is None:
                batch_321 = GradeBatchService().create(
                    offering=off_321_01, name="Demo CSE321 Midterm & Lab Release"
                )
            for stu, s_mid, s_lab in [
                (deniz, Decimal("90.04"), Decimal("90.04")),
                (kerem, Decimal("58.00"), Decimal("64.00")),
                (ece, Decimal("88.00"), Decimal("90.00")),
                (mert, Decimal("78.00"), Decimal("76.00")),
            ] + [
                (u, Decimal(str(max(30, min(98, m + 1)))), Decimal(str(max(30, min(98, p + 2)))))
                for u, m, p in synthetic_students
            ]:
                enr = _ensure_enrollment(offering=off_321_01, student=stu, actor=coord_user)
                _ensure_grade(
                    enrollment=enr,
                    assessment=asmt_321_mid,
                    batch=batch_321,
                    state=Grade.State.SCORED,
                    points_earned=s_mid,
                    actor=coord_user,
                )
                _ensure_grade(
                    enrollment=enr,
                    assessment=asmt_321_lab,
                    batch=batch_321,
                    state=Grade.State.SCORED,
                    points_earned=s_lab,
                    actor=coord_user,
                )
            _backfill_preexisting_enrollments(
                offering=off_321_01,
                assessments=[asmt_321_mid, asmt_321_lab],
                batch=batch_321,
                actor=coord_user,
            )
            if batch_321.released_at is None:
                GradeBatchService().release(batch=batch_321, actor=coord_user)

            # Gradebook Assessments & Grades for CSE 214-01 (CSE)
            asmt_214_mid, _ = Assessment.objects.get_or_create(
                offering=off_214_01_cse,
                title="Midterm",
                defaults={
                    "points_possible": Decimal("100.00"),
                    "status": Assessment.Status.APPROVED,
                },
            )
            asmt_214_hw, _ = Assessment.objects.get_or_create(
                offering=off_214_01_cse,
                title="Homework",
                defaults={
                    "points_possible": Decimal("100.00"),
                    "status": Assessment.Status.APPROVED,
                },
            )
            batch_214 = GradeBatch.objects.filter(
                offering=off_214_01_cse, name="Demo CSE214 Midterm & Homework Release"
            ).first()
            if batch_214 is None:
                batch_214 = GradeBatchService().create(
                    offering=off_214_01_cse, name="Demo CSE214 Midterm & Homework Release"
                )
            for stu, s_mid, s_hw in [
                (deniz, Decimal("88.00"), Decimal("84.00")),
                (kerem, Decimal("62.00"), Decimal("66.00")),
                (ece, Decimal("85.00"), Decimal("89.00")),
                (mert, Decimal("72.00"), Decimal("75.00")),
            ] + [
                (u, Decimal(str(max(30, min(98, m)))), Decimal(str(max(30, min(98, p)))))
                for u, m, p in synthetic_students
            ]:
                enr = _ensure_enrollment(offering=off_214_01_cse, student=stu, actor=coord_user)
                _ensure_grade(
                    enrollment=enr,
                    assessment=asmt_214_mid,
                    batch=batch_214,
                    state=Grade.State.SCORED,
                    points_earned=s_mid,
                    actor=instructor_user,
                )
                _ensure_grade(
                    enrollment=enr,
                    assessment=asmt_214_hw,
                    batch=batch_214,
                    state=Grade.State.SCORED,
                    points_earned=s_hw,
                    actor=instructor_user,
                )
            _backfill_preexisting_enrollments(
                offering=off_214_01_cse,
                assessments=[asmt_214_mid, asmt_214_hw],
                batch=batch_214,
                actor=instructor_user,
            )
            if batch_214.released_at is None:
                GradeBatchService().release(batch=batch_214, actor=coord_user)

            # 9. Publish Immutable 2026-2027 Fall Snapshots (Offering + Program, Faculty + Student)
            _ensure_published(
                program=cse_program,
                offering=off_311_01,
                term=term_2026_fall,
                audience=Publication.Audience.FACULTY,
                idempotency_key="demo-cse311-01-2026-fall-v1-faculty",
                actor=coord_user,
            )
            _ensure_published(
                program=cse_program,
                offering=off_311_01,
                term=term_2026_fall,
                audience=Publication.Audience.STUDENT,
                idempotency_key="demo-cse311-01-2026-fall-v1-student",
                actor=coord_user,
            )
            _ensure_published(
                program=cse_program,
                offering=None,
                term=term_2026_fall,
                audience=Publication.Audience.FACULTY,
                idempotency_key="demo-cse-2026-fall-po-v2-faculty",
                actor=coord_user,
            )
            _ensure_published(
                program=cse_program,
                offering=None,
                term=term_2026_fall,
                audience=Publication.Audience.STUDENT,
                idempotency_key="demo-cse-2026-fall-po-v2-student",
                actor=coord_user,
            )

            # 10. Stage D: Post-Publication Pending Syllabus v2 Draft, Blocking ABSENT Grade Correction, and Audit Events
            off_311_scope = Scope.objects.get(pk=off_311_01.pk)

            # Pending v2 Draft on CSE 311-01 awaiting Coordinator approval
            syl_311_v2 = off_311_01.syllabi.filter(version=2).first()
            if syl_311_v2 is None:
                syl_311_v2 = SyllabusService().revise(syllabus=syl_311_v1)
            _ensure_audit_event(
                seed_key="demo-cse311-01-syllabus-v2-submitted",
                actor=instructor_user,
                scope=off_311_scope,
                action="syllabus.submitted",
                metadata={
                    "offering_code": "CSE311-01",
                    "syllabus_id": str(syl_311_v2.pk),
                    "syllabus_version": syl_311_v2.version,
                    "status": "draft",
                },
            )

            # Post-publication grade correction: Mert Celik Project -> MISSING (blocking ABSENT)
            grade_mert_proj.refresh_from_db()
            if grade_mert_proj.state != Grade.State.MISSING:
                grade_mert_proj = GradeService().correct(
                    grade=grade_mert_proj,
                    expected_version=grade_mert_proj.version,
                    state=Grade.State.MISSING,
                    points_earned=None,
                    reason="Student absent from final project demo — post-publication audit correction",
                    actor=instructor_user,
                )
            _ensure_audit_event(
                seed_key="demo-cse311-01-mert-absent-correction",
                actor=instructor_user,
                subject=mert,
                scope=off_311_scope,
                action="grade.corrected",
                metadata={
                    "offering_code": "CSE311-01",
                    "grade_id": str(grade_mert_proj.pk),
                    "assessment": "Project",
                    "old_state": Grade.State.SCORED,
                    "new_state": Grade.State.MISSING,
                    "reason": "Student absent from final project demo — post-publication audit correction",
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Deterministic demo seed complete (ACU / CSE + SWE, 45 students, "
                "PO-Set v1 & v2, PRD §5/§11.4 reference scores, edge cases, publications, and audit events)."
            )
        )
