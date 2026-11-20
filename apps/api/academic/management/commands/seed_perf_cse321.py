"""Deterministic CSE321-scale benchmark seed (PERF-01).

Synthetic by design: one program, one institution (code PERF), one cohort of students taking
every offering of every term. CSE321 section 01 is offered each term, plus extra courses per term.
Each CSE321-01..N offering has an approved syllabus, LOs, mappings, released grades and history.
CSE321 section 02 in the last term has enrolments and approved assessments but no grades; it is
the CSV import target.

Determinism: all benchmark-relevant row ids come from a seeded RNG, so the same parameters
yield the same rows (ids and values). Use a dedicated, empty database: rows are never deleted.
"""

import datetime as dt
import json
import random
import sys
import uuid
from decimal import Decimal
from pathlib import Path

import django
from access.models import InstitutionMembership, RoleAssignment
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from academic import policy
from academic.models import (
    AcademicTerm,
    Assessment,
    AssessmentLOMapping,
    Course,
    CourseOffering,
    CoursePOContribution,
    Department,
    Enrollment,
    Grade,
    GradeBatch,
    GradeHistory,
    Institution,
    InstructorAssignment,
    LearningOutcome,
    LOPOMapping,
    Program,
    ProgramCourse,
    ProgramMembership,
    ProgramOutcome,
    ProgramOutcomeSet,
    Syllabus,
    SyllabusAssessment,
)
from academic.perf import SEED_VERSION

User = get_user_model()
KINDS = [k for k, _ in SyllabusAssessment.Kind.choices]
EXEMPT_RATIO = 0.03
WITHDRAWN_RATIO = 0.02
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1", "")


class Command(BaseCommand):
    help = "Seed a deterministic CSE321-scale dataset for PERF-01 measurements."

    def add_arguments(self, parser):
        parser.add_argument("--students", type=int, default=150, help="Students per cohort")
        parser.add_argument("--scale", type=int, default=1, help="Multiplier applied to --students")
        parser.add_argument("--terms", type=int, default=4)
        parser.add_argument("--courses-per-term", type=int, default=3)
        parser.add_argument("--los", type=int, default=6, help="Learning outcomes per syllabus")
        parser.add_argument("--assessments", type=int, default=12, help="Assessments per syllabus")
        parser.add_argument("--pos", type=int, default=11, help="Program outcomes")
        parser.add_argument("--rng-seed", type=int, default=321)
        parser.add_argument("--publish", action="store_true", help="Run + publish all calculations")
        parser.add_argument("--allow-remote", action="store_true")
        parser.add_argument(
            "--meta-file",
            default=str(settings.BASE_DIR.parent.parent / "docs" / "perf" / "seed-meta.json"),
        )

    def handle(self, *args, **opts):
        db = settings.DATABASES["default"]
        if db.get("HOST", "") not in LOCAL_HOSTS and not opts["allow_remote"]:
            raise CommandError("Refusing to seed a non-local database without --allow-remote.")
        params = {
            "students": opts["students"] * opts["scale"],
            "terms": opts["terms"],
            "courses_per_term": opts["courses_per_term"],
            "los": opts["los"],
            "assessments": opts["assessments"],
            "pos": opts["pos"],
            "rng_seed": opts["rng_seed"],
        }
        self._validate(params, opts["scale"])
        if Institution.objects.filter(code="PERF").exists():
            raise CommandError(
                "Institution PERF already exists. Seed rows are never deleted: "
                "recreate the benchmark database and re-run."
            )

        rng = random.Random(params["rng_seed"])
        started = timezone.now()
        with transaction.atomic():
            ctx = self._seed(params, rng)
        self._analyze()
        if opts["publish"]:
            self._publish(ctx)
            self._analyze()

        meta = {
            "seed_version": SEED_VERSION,
            "params": params,
            "published": opts["publish"],
            "seeded_at": started.isoformat(),
            "python": sys.version.split()[0],
            "django": django.get_version(),
            "institution_id": str(ctx["institution"].pk),
            "program_id": str(ctx["program"].pk),
        }
        path = Path(opts["meta_file"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Seed {SEED_VERSION} complete; meta -> {path}"))

    @staticmethod
    def _validate(p, scale):
        if scale < 1 or p["students"] < 1 or p["terms"] < 1 or p["courses_per_term"] < 1:
            raise CommandError("students, scale, terms and courses-per-term must be >= 1.")
        if p["pos"] < 2 or p["los"] < 1 or p["assessments"] < p["los"]:
            raise CommandError("Need pos >= 2, los >= 1 and assessments >= los.")

    # ------------------------------------------------------------------ seeding
    def _seed(self, p, rng):
        def uid():
            return uuid.UUID(int=rng.getrandbits(128), version=4)

        now = timezone.now()
        inst = Institution.objects.create(id=uid(), code="PERF", name="Performance Benchmark")
        dept = Department.objects.create(
            id=uid(), institution=inst, code="CSE", name="Computer Eng."
        )
        program = Program.objects.create(
            id=uid(), department=dept, code="CSE", title="Computer Engineering (benchmark)"
        )

        terms = []
        for t in range(p["terms"]):
            year, fall = 2025 + (t + 1) // 2, t % 2 == 0
            terms.append(
                AcademicTerm.objects.create(
                    id=uid(),
                    institution=inst,
                    year=year,
                    season="fall" if fall else "spring",
                    starts_at=dt.date(year, 9, 15) if fall else dt.date(year, 2, 10),
                    ends_at=dt.date(year + 1, 1, 20) if fall else dt.date(year, 6, 25),
                )
            )

        # Users: one coordinator, one instructor, N students (unusable passwords).
        unusable = make_password(None)
        names = ["perf.coordinator", "perf.instructor"] + [
            f"perf.student.{i:05d}" for i in range(1, p["students"] + 1)
        ]
        User.objects.bulk_create(
            [User(username=n, email=f"{n}@example.test", password=unusable) for n in names],
            batch_size=1000,
        )
        users = list(User.objects.filter(username__in=names).order_by("username"))
        by_name = {u.username: u for u in users}
        coord, instructor = by_name["perf.coordinator"], by_name["perf.instructor"]
        students = [by_name[n] for n in names[2:]]
        InstitutionMembership.objects.bulk_create(
            [InstitutionMembership(user=u, institution_id=inst.pk) for u in users], batch_size=1000
        )
        RoleAssignment.objects.create(
            id=uid(), user=coord, scope_id=program.pk, role_id="program-coordinator"
        )
        ProgramMembership.objects.bulk_create(
            [
                ProgramMembership(
                    id=uid(),
                    program=program,
                    user=s,
                    student_number=f"PERF-{i:05d}",
                    admitted_term=terms[0],
                    status=ProgramMembership.Status.ACTIVE,
                )
                for i, s in enumerate(students, start=1)
            ],
            batch_size=1000,
        )

        # Active PO set: created as draft, then activated with a queryset update because an
        # active set is immutable by design.
        po_set = ProgramOutcomeSet.objects.create(
            id=uid(), program=program, version=1, source_reference="perf seed"
        )
        pos = ProgramOutcome.objects.bulk_create(
            [
                ProgramOutcome(
                    id=uid(),
                    outcome_set=po_set,
                    code=f"PO{i}",
                    label=f"Program outcome {i}",
                    description=f"Benchmark program outcome {i}.",
                    source_url="https://example.test/perf",
                    ordering=i,
                )
                for i in range(1, p["pos"] + 1)
            ]
        )
        ProgramOutcomeSet.objects.filter(pk=po_set.pk).update(
            status=ProgramOutcomeSet.Status.ACTIVE,
            effective_date=dt.date(2024, 1, 1),
            activated_at=now,
            activated_by=coord,
        )

        courses: dict[str, Course] = {}

        def course(code):
            if code not in courses:
                c = Course.objects.create(
                    id=uid(),
                    home_department=dept,
                    code=code,
                    title=f"{code} (benchmark)",
                    ects=6,
                    credits=3,
                )
                ProgramCourse.objects.create(
                    id=uid(),
                    program=program,
                    course=c,
                    effective_from=dt.date(2021, 9, 1),
                    status=ProgramCourse.Status.APPROVED,
                )
                courses[code] = c
            return courses[code]

        main_offerings = []
        for t, term in enumerate(terms):
            codes = ["CSE321"] + [f"CSE4{t + 1}{k}" for k in range(1, p["courses_per_term"])]
            for code in codes:
                offering = CourseOffering.objects.create(
                    id=uid(), program=program, course=course(code), term=term, section="01"
                )
                InstructorAssignment.objects.create(id=uid(), offering=offering, user=instructor)
                RoleAssignment.objects.create(
                    id=uid(), user=instructor, scope_id=offering.pk, role_id="instructor"
                )
                self._seed_syllabus(p, rng, uid, offering, coord, pos, now)
                enrollments = self._seed_enrollments(rng, uid, offering, students, roles=True)
                batch = GradeBatch.objects.create(
                    id=uid(),
                    offering=offering,
                    name="Seed batch",
                    released_at=now,
                    released_by=coord,
                )
                self._seed_grades(rng, uid, offering, enrollments, batch, coord)
                main_offerings.append(offering)

        # CSV import target: CSE321-02 in the last term, enrolled students, no grades/syllabus.
        target = CourseOffering.objects.create(
            id=uid(), program=program, course=courses["CSE321"], term=terms[-1], section="02"
        )
        Assessment.objects.bulk_create(
            [
                Assessment(
                    id=uid(),
                    offering=target,
                    title=f"IMP-A{j:02d}",
                    points_possible=Decimal("100.00"),
                    status=Assessment.Status.APPROVED,
                )
                for j in range(1, p["assessments"] + 1)
            ]
        )
        self._seed_enrollments(rng, uid, target, students, roles=False, withdraw=False)
        self.stdout.write(f"Seeded {len(main_offerings)} graded offerings + 1 import target.")
        return {
            "institution": inst,
            "program": program,
            "coord": coord,
            "offerings": main_offerings,
        }

    def _seed_syllabus(self, p, rng, uid, offering, coord, pos, now):
        syllabus = Syllabus.objects.create(
            id=uid(),
            offering=offering,
            version=1,
            status=Syllabus.Status.APPROVED,
            approved_by=coord,
            approved_at=now,
            po_set_version=1,
            mapping_revision=1,
        )
        los = LearningOutcome.objects.bulk_create(
            [
                LearningOutcome(
                    id=uid(), syllabus=syllabus, code=f"LO{j}", description=f"Outcome {j}", order=j
                )
                for j in range(1, p["los"] + 1)
            ]
        )
        # Assessment code == gradebook Assessment title: calculations link them by exact title.
        sas = SyllabusAssessment.objects.bulk_create(
            [
                SyllabusAssessment(
                    id=uid(),
                    syllabus=syllabus,
                    code=f"A{j:02d}",
                    kind=KINDS[j % len(KINDS)],
                    order=j,
                    max_points=Decimal("100.00"),
                )
                for j in range(1, p["assessments"] + 1)
            ]
        )
        Assessment.objects.bulk_create(
            [
                Assessment(
                    id=uid(),
                    offering=offering,
                    title=sa.code,
                    points_possible=Decimal("100.00"),
                    status=Assessment.Status.APPROVED,
                )
                for sa in sas
            ]
        )
        n_lo, n_po = len(los), len(pos)
        a_lo = []
        for j, sa in enumerate(sas):
            targets = {j % n_lo, (j + 1) % n_lo}
            for k in sorted(targets):
                a_lo.append(
                    AssessmentLOMapping(
                        id=uid(),
                        syllabus=syllabus,
                        assessment=sa,
                        learning_outcome=los[k],
                        weight=Decimal(rng.randint(1, 4) * 10),
                    )
                )
        AssessmentLOMapping.objects.bulk_create(a_lo)
        lo_po, touched = [], set()
        for j, lo in enumerate(los):
            for k in sorted({j % n_po, (j + 1) % n_po}):
                touched.add(k)
                lo_po.append(
                    LOPOMapping(
                        id=uid(),
                        syllabus=syllabus,
                        learning_outcome=lo,
                        program_outcome=pos[k],
                        weight=rng.randint(1, 5),
                    )
                )
        LOPOMapping.objects.bulk_create(lo_po)
        CoursePOContribution.objects.bulk_create(
            [
                CoursePOContribution(
                    id=uid(), syllabus=syllabus, program_outcome=pos[k], weight=rng.randint(1, 5)
                )
                for k in sorted(touched)
            ]
        )

    @staticmethod
    def _seed_enrollments(rng, uid, offering, students, *, roles, withdraw=True):
        rows = []
        for s in students:
            withdrawn = withdraw and rng.random() < WITHDRAWN_RATIO
            status = Enrollment.Status.WITHDRAWN if withdrawn else Enrollment.Status.ENROLLED
            rows.append(
                Enrollment(
                    id=uid(),
                    offering=offering,
                    student=s,
                    status=status,
                    attempt_number=1,
                    eligible_for_outcomes=policy.is_eligible(status),
                    eligibility_policy_version=policy.POLICY_VERSION,
                )
            )
        Enrollment.objects.bulk_create(rows, batch_size=2000)
        if roles:
            RoleAssignment.objects.bulk_create(
                [
                    RoleAssignment(
                        id=uid(), user=e.student, scope_id=offering.pk, role_id="student"
                    )
                    for e in rows
                    if e.status == Enrollment.Status.ENROLLED
                ],
                batch_size=2000,
            )
        return rows

    @staticmethod
    def _seed_grades(rng, uid, offering, enrollments, batch, coord):
        assessments = list(Assessment.objects.filter(offering=offering).order_by("title"))
        grades, history = [], []
        for enr in enrollments:
            if enr.status != Enrollment.Status.ENROLLED:
                continue
            for asmt in assessments:
                exempt = rng.random() < EXEMPT_RATIO
                state = Grade.State.EXEMPT if exempt else Grade.State.SCORED
                points = None if exempt else Decimal(rng.randint(3500, 10000)).scaleb(-2)
                grade = Grade(
                    id=uid(),
                    offering=offering,
                    enrollment=enr,
                    assessment=asmt,
                    batch=batch,
                    state=state,
                    points_earned=points,
                    points_possible=asmt.points_possible,
                    version=1,
                )
                grades.append(grade)
                history.append(
                    GradeHistory(
                        id=uid(),
                        grade=grade,
                        version=1,
                        old_state="",
                        new_state=state,
                        new_points_earned=points,
                        reason="documented exemption" if exempt else "perf seed",
                        changed_by=coord,
                    )
                )
        Grade.objects.bulk_create(grades, batch_size=2000)
        GradeHistory.objects.bulk_create(history, batch_size=2000)

    # ------------------------------------------------------------- post-steps
    def _publish(self, ctx):
        from academic.models import Publication
        from academic.services.calculations import CalculationService
        from academic.services.publications import PublicationService

        coord, program = ctx["coord"], ctx["program"]
        calc = CalculationService()
        pubs = PublicationService(calculation_service=calc, actor=coord)

        def publish_run(run, label):
            if not run.is_complete_for_publication:
                raise CommandError(f"Run for {label} is not complete for publication.")
            for audience in (Publication.Audience.FACULTY, Publication.Audience.STUDENT):
                pubs.publish(
                    actor=coord,
                    run=run,
                    expected_series_version=0,
                    expected_input_hash=run.input_hash,
                    audience=audience,
                    idempotency_key=f"perf-{label}-{audience}",
                )

        for offering in ctx["offerings"]:
            run, _ = calc.run_offering(offering=offering, actor=coord)
            publish_run(run, str(offering.pk))
        run, _ = calc.run_program(program=program, actor=coord)
        publish_run(run, f"program-{program.pk}")
        self.stdout.write("Calculated and published all offerings and the program series.")

    @staticmethod
    def _analyze():
        """Fresh planner statistics so EXPLAIN reflects the seeded data, not an empty catalog."""
        if connection.vendor != "postgresql":
            return
        with connection.cursor() as cur:
            cur.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = current_schema() "
                "AND (tablename LIKE 'academic\\_%' OR tablename LIKE 'access\\_%')"
            )
            for (table,) in cur.fetchall():
                cur.execute(f'ANALYZE "{table}"')
