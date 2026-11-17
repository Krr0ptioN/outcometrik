import datetime as dt
import json
import logging
import os
import secrets
from decimal import Decimal
from pathlib import Path

from access.models import InstitutionMembership, RoleAssignment
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from academic import policy
from academic.models import (
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
from academic.seed_data.crawler import crawl_acibadem_courses

logger = logging.getLogger(__name__)
User = get_user_model()

DEPARTMENTS = [
    ("CSE", "Department of Computer Engineering"),
    ("MATH", "Department of Mathematics"),
    ("PHYS", "Department of Physics"),
    ("BME", "Department of Biomedical Engineering"),
    ("MBG", "Department of Molecular Biology and Genetics"),
    ("LANG", "Department of Foreign Languages"),
    ("TURK", "Department of Turkish Language"),
    ("HIST", "Department of History"),
    ("GEN", "General Education and University Electives"),
]

PREFIX_TO_DEPT = {
    "CSE": "CSE",
    "MAT": "MATH",
    "MTH": "MATH",
    "PHY": "PHYS",
    "BME": "BME",
    "MBG": "MBG",
    "ENG": "LANG",
    "TUR": "TURK",
    "ATA": "HIST",
    "OHS": "GEN",
    "ADS": "GEN",
    "ACU": "GEN",
}

ADMIN_ACCOUNTS = [
    {
        "username": "demo.admin",
        "email": "admin@example.test",
        "first_name": "Acıbadem",
        "last_name": "Administrator",
        "role": "administrator",
        "is_superuser": True,
        "is_staff": True,
        "description": "Institution superuser and administrator",
    },
    {
        "username": "demo.institution.admin",
        "email": "institution.admin@example.test",
        "first_name": "System",
        "last_name": "Administrator",
        "role": "administrator",
        "is_superuser": False,
        "is_staff": True,
        "description": "Standard institution administrator for e2e and dashboard operations",
    },
]

COORDINATOR_ACCOUNTS = [
    {
        "username": "demo.coordinator",
        "email": "coordinator@example.test",
        "first_name": "Demo",
        "last_name": "Coordinator",
        "role": "program-coordinator",
        "title": "Prof. Dr.",
        "description": "Synthetic Computer Engineering Program Coordinator",
    }
]

INSTRUCTOR_ACCOUNTS = [
    {
        "username": "demo.instructor.cs",
        "email": "instructor.cs@example.test",
        "first_name": "CS",
        "last_name": "Faculty",
        "role": "instructor",
        "description": "Computer Science Instructor for Software & Data Systems",
    },
    {
        "username": "demo.deniz.kaya",
        "email": "deniz.kaya@example.test",
        "first_name": "Deniz",
        "last_name": "Kaya",
        "role": "instructor",
        "description": "Associate Professor for Introductory Programming",
    },
    {
        "username": "demo.kemal.yilmaz",
        "email": "kemal.yilmaz@example.test",
        "first_name": "Kemal",
        "last_name": "Yılmaz",
        "role": "instructor",
        "description": "Assistant Professor for Algorithms & Applied Mathematics",
    },
    {
        "username": "demo.zeynep.demir",
        "email": "zeynep.demir@example.test",
        "first_name": "Zeynep",
        "last_name": "Demir",
        "role": "instructor",
        "description": "Lecturer for Computer Architecture",
    },
    {
        "username": "demo.grace.instructor",
        "email": "grace.instructor@example.test",
        "first_name": "Grace",
        "last_name": "Instructor",
        "role": "instructor",
        "description": "Visiting Instructor",
    },
]

STUDENT_ACCOUNTS = [
    {
        "username": "demo.ada.student",
        "email": "ada.student@example.test",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "student_number": "DEMO2023-001",
        "cohort": 2023,
        "description": "Year 3 Computer Engineering student",
    },
    {
        "username": "demo.alan.student",
        "email": "alan.student@example.test",
        "first_name": "Alan",
        "last_name": "Turing",
        "student_number": "DEMO2023-002",
        "cohort": 2023,
        "description": "Year 3 Computer Engineering student",
    },
    {
        "username": "demo.grace.student",
        "email": "grace.student@example.test",
        "first_name": "Grace",
        "last_name": "Hopper",
        "student_number": "DEMO2023-003",
        "cohort": 2023,
        "description": "Year 3 Computer Engineering student",
    },
    {
        "username": "demo.baris.student",
        "email": "baris.student@example.test",
        "first_name": "Barış",
        "last_name": "Özcan",
        "student_number": "DEMO2023-004",
        "cohort": 2023,
        "description": "Year 3 Computer Engineering student",
    },
    {
        "username": "demo.can.student",
        "email": "can.student@example.test",
        "first_name": "Can",
        "last_name": "Yıldız",
        "student_number": "DEMO2024-001",
        "cohort": 2024,
        "description": "Year 2 Computer Engineering student",
    },
    {
        "username": "demo.elif.student",
        "email": "elif.student@example.test",
        "first_name": "Elif",
        "last_name": "Kaya",
        "student_number": "DEMO2024-002",
        "cohort": 2024,
        "description": "Year 2 Computer Engineering student",
    },
    {
        "username": "demo.mert.student",
        "email": "mert.student@example.test",
        "first_name": "Mert",
        "last_name": "Aksoy",
        "student_number": "DEMO2024-003",
        "cohort": 2024,
        "description": "Year 2 Computer Engineering student",
    },
    {
        "username": "demo.selin.student",
        "email": "selin.student@example.test",
        "first_name": "Selin",
        "last_name": "Özkan",
        "student_number": "DEMO2025-001",
        "cohort": 2025,
        "description": "Year 1 Computer Engineering student",
    },
    {
        "username": "demo.emre.student",
        "email": "emre.student@example.test",
        "first_name": "Emre",
        "last_name": "Çelik",
        "student_number": "DEMO2025-002",
        "cohort": 2025,
        "description": "Year 1 Computer Engineering student",
    },
    {
        "username": "demo.irem.student",
        "email": "irem.student@example.test",
        "first_name": "İrem",
        "last_name": "Avcı",
        "student_number": "DEMO2025-003",
        "cohort": 2025,
        "description": "Year 1 Computer Engineering student",
    },
]


def grant_role(user, scope_id, role_slug):
    return RoleAssignment.objects.get_or_create(
        user=user,
        scope_id=scope_id,
        role_id=role_slug,
        revoked_at__isnull=True,
    )[0]


class Command(BaseCommand):
    help = "Seed database with Acibadem University academic data, courses, users, and credentials."

    def add_arguments(self, parser):
        parser.add_argument(
            "--crawl",
            action="store_true",
            help="Re-crawl live course catalog from Acibadem Bologna portal before seeding",
        )
        parser.add_argument(
            "--credentials-file",
            type=str,
            default=str(settings.BASE_DIR.parent.parent / "seeded_creentials.json"),
            help="Path to output credentials JSON file",
        )
        parser.add_argument(
            "--administrator",
            help="Grant an existing active user administrator access to the demo institution",
        )

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        if not settings.DEBUG or (
            db["ENGINE"] != "django.db.backends.sqlite3"
            and db.get("HOST") not in ("localhost", "127.0.0.1", "::1")
        ):
            raise CommandError("Demo seed requires DEBUG and a local database.")
        administrator = None
        if options["administrator"]:
            administrator = User.objects.filter(
                username=options["administrator"], is_active=True
            ).first()
            if administrator is None:
                raise CommandError("The requested administrator must be an existing active user.")
        target_file = Path(options["credentials_file"]).resolve()
        if target_file.exists():
            try:
                previous = json.loads(target_file.read_text(encoding="utf-8"))
                passwords = {
                    item["username"]: item["password"]
                    for group in previous.get("accounts", {}).values()
                    for item in group
                }
            except (OSError, ValueError, KeyError, TypeError) as exc:
                raise CommandError("Cannot read existing demo credentials file.") from exc
        else:
            passwords = {}
        for account in (
            ADMIN_ACCOUNTS + COORDINATOR_ACCOUNTS + INSTRUCTOR_ACCOUNTS + STUDENT_ACCOUNTS
        ):
            account["password"] = passwords.get(account["username"]) or secrets.token_urlsafe(18)

        self.stdout.write(self.style.NOTICE("=== Starting Acibadem University Database Seed ==="))
        should_crawl = options["crawl"]

        # 1. Crawl or load courses
        courses_json_path = (
            Path(__file__).resolve().parent.parent.parent / "seed_data" / "acibadem_courses.json"
        )
        if should_crawl or not courses_json_path.exists():
            self.stdout.write(
                self.style.WARNING("Crawling courses from Acibadem Bologna portal...")
            )
            courses_data = crawl_acibadem_courses(courses_json_path)
        else:
            self.stdout.write(f"Loading cached courses from {courses_json_path}")
            with open(courses_json_path, encoding="utf-8") as f:
                courses_data = json.load(f)

        self.stdout.write(f"Loaded {len(courses_data)} unique courses.")

        with transaction.atomic():
            # 2. Institution
            inst, _ = Institution.objects.get_or_create(
                code="ACU",
                defaults={"name": "Acıbadem Mehmet Ali Aydınlar University"},
            )
            self.stdout.write(f"Institution: {inst.name} (Code: {inst.code}, ID: {inst.pk})")

            # 3. Departments
            dept_map = {}
            for d_code, d_name in DEPARTMENTS:
                dept, _ = Department.objects.get_or_create(
                    institution=inst,
                    code=d_code,
                    defaults={"name": d_name},
                )
                dept_map[d_code] = dept
            self.stdout.write(f"Initialized {len(dept_map)} departments.")

            # 4. Program
            cse_dept = dept_map["CSE"]
            program, _ = Program.objects.get_or_create(
                department=cse_dept,
                code="CSE",
                defaults={
                    "title": "Computer Engineering Undergraduate Program",
                    "status": Program.Status.ACTIVE,
                },
            )
            self.stdout.write(f"Program: {program.title} (Code: {program.code}, ID: {program.pk})")

            # 5. Academic Terms
            terms = {}
            term_specs = [
                (2025, "fall", dt.date(2025, 9, 15), dt.date(2026, 1, 20)),
                (2026, "spring", dt.date(2026, 2, 10), dt.date(2026, 6, 25)),
                (2026, "fall", dt.date(2026, 9, 15), dt.date(2027, 1, 20)),
                (2027, "spring", dt.date(2027, 2, 10), dt.date(2027, 6, 25)),
            ]
            for year, season, starts_at, ends_at in term_specs:
                term, _ = AcademicTerm.objects.get_or_create(
                    institution=inst,
                    year=year,
                    season=season,
                    defaults={"starts_at": starts_at, "ends_at": ends_at},
                )
                terms[f"{year}-{season}"] = term
            active_term = terms["2026-fall"]
            self.stdout.write(f"Active Academic Term: {active_term}")

            # 6. Courses and ProgramCourse links
            added_courses = 0
            course_objs = {}
            for item in courses_data:
                code = item["code"]
                # Determine department prefix
                prefix = ""
                for char in code:
                    if char.isalpha():
                        prefix += char
                    else:
                        break
                dept_code = PREFIX_TO_DEPT.get(prefix, "CSE")
                dept = dept_map.get(dept_code, cse_dept)

                course, _ = Course.objects.get_or_create(
                    home_department=dept,
                    code=code,
                    defaults={
                        "title": item["title"],
                        "ects": item["ects"],
                        "credits": item["credits"],
                        "active": True,
                    },
                )
                course_objs[code] = course

                # Link course to Computer Engineering program
                ProgramCourse.objects.get_or_create(
                    program=program,
                    course=course,
                    defaults={
                        "effective_from": dt.date(2021, 9, 1),
                        "status": ProgramCourse.Status.APPROVED,
                    },
                )
                added_courses += 1

            self.stdout.write(f"Seeded {added_courses} courses and program-course links.")

            # 7. Users, Memberships, and Roles
            # Admins
            admin_users = []
            for a in ADMIN_ACCOUNTS:
                u = self._demo_user(
                    a, is_staff=a.get("is_staff", False), is_superuser=a.get("is_superuser", False)
                )

                InstitutionMembership.objects.get_or_create(user=u, institution_id=inst.pk)
                grant_role(u, inst.pk, "administrator")
                admin_users.append(u)
            if administrator is not None:
                InstitutionMembership.objects.get_or_create(
                    user=administrator, institution_id=inst.pk
                )
                grant_role(administrator, inst.pk, "administrator")
            self.stdout.write(f"Created/updated {len(admin_users)} admin accounts.")

            # Coordinator
            coord_users = []
            for c in COORDINATOR_ACCOUNTS:
                u = self._demo_user(c)

                InstitutionMembership.objects.get_or_create(user=u, institution_id=inst.pk)
                grant_role(u, program.pk, "program-coordinator")
                coord_users.append(u)
            coord_user = coord_users[0]
            self.stdout.write(f"Created/updated coordinator: {coord_user.username}")

            # Instructors
            instructor_users = {}
            for inst_acc in INSTRUCTOR_ACCOUNTS:
                u = self._demo_user(inst_acc)

                InstitutionMembership.objects.get_or_create(user=u, institution_id=inst.pk)
                instructor_users[u.username] = u
            self.stdout.write(f"Created/updated {len(instructor_users)} instructor accounts.")

            # Students
            student_users = {}
            for s in STUDENT_ACCOUNTS:
                u = self._demo_user(s)

                InstitutionMembership.objects.get_or_create(user=u, institution_id=inst.pk)
                admitted = terms.get(f"{s['cohort']}-fall", active_term)
                ProgramMembership.objects.get_or_create(
                    program=program,
                    user=u,
                    defaults={
                        "student_number": s["student_number"],
                        "admitted_term": admitted,
                        "status": ProgramMembership.Status.ACTIVE,
                    },
                )
                student_users[u.username] = u
            self.stdout.write(f"Created/updated {len(student_users)} student accounts.")

            # 8. Course Offerings for active term (2026 Fall)
            offering_configs = [
                ("CSE101", "01", instructor_users["demo.deniz.kaya"]),
                ("MAT111", "01", instructor_users["demo.kemal.yilmaz"]),
                ("CSE201", "01", instructor_users["demo.kemal.yilmaz"]),
                ("CSE301", "01", instructor_users["demo.zeynep.demir"]),
                ("CSE311", "01", instructor_users["demo.instructor.cs"]),
                ("CSE321", "01", coord_user),
                ("CSE331", "01", instructor_users["demo.instructor.cs"]),
            ]

            offerings = {}
            for c_code, sec, faculty in offering_configs:
                if c_code not in course_objs:
                    continue
                c_obj = course_objs[c_code]
                offering, _ = CourseOffering.objects.get_or_create(
                    program=program,
                    course=c_obj,
                    term=active_term,
                    section=sec,
                    defaults={"status": CourseOffering.Status.ACTIVE},
                )
                InstructorAssignment.objects.get_or_create(
                    offering=offering,
                    user=faculty,
                    defaults={"assignment_role": InstructorAssignment.Role.INSTRUCTOR},
                )
                grant_role(faculty, offering.pk, "instructor")
                offerings[c_code] = offering

            self.stdout.write(f"Created {len(offerings)} offerings with instructor assignments.")

            # 9. Student Enrollments
            y1_students = [
                student_users[s["username"]] for s in STUDENT_ACCOUNTS if s["cohort"] == 2025
            ]
            y2_students = [
                student_users[s["username"]] for s in STUDENT_ACCOUNTS if s["cohort"] == 2024
            ]
            y3_students = [
                student_users[s["username"]] for s in STUDENT_ACCOUNTS if s["cohort"] == 2023
            ]

            enrollment_groups = [
                ("CSE101", y1_students),
                ("MAT111", y1_students),
                ("CSE201", y2_students),
                ("CSE301", y3_students),
                ("CSE311", y3_students),
                ("CSE321", y3_students),
                ("CSE331", y3_students),
            ]

            enrollments = {}
            for c_code, stu_list in enrollment_groups:
                offering = offerings.get(c_code)
                if not offering:
                    continue
                enrollments[c_code] = []
                for stu in stu_list:
                    enr, enr_created = Enrollment.objects.get_or_create(
                        offering=offering,
                        student=stu,
                        defaults={
                            "status": Enrollment.Status.ENROLLED,
                            "attempt_number": 1,
                            "eligible_for_outcomes": True,
                            "eligibility_policy_version": policy.POLICY_VERSION,
                        },
                    )
                    grant_role(stu, offering.pk, "student")
                    if enr_created:
                        EnrollmentStatusEvent.objects.create(
                            enrollment=enr,
                            from_status="",
                            to_status=Enrollment.Status.ENROLLED,
                            eligible=True,
                            policy_version=policy.POLICY_VERSION,
                            reason="Initial curriculum enrollment",
                        )
                    enrollments[c_code].append(enr)

            self.stdout.write("Created student enrollments and outcome eligibility events.")

            # 10. Assessments, GradeBatches, and Grades for CSE311 (Software) and CSE321 (Data Systems)
            # CSE311:
            off_311 = offerings.get("CSE311")
            if off_311:
                faculty_311 = instructor_users["demo.instructor.cs"]
                a1, _ = Assessment.objects.get_or_create(
                    offering=off_311,
                    title="Midterm Examination",
                    defaults={
                        "points_possible": Decimal("100.00"),
                        "status": Assessment.Status.APPROVED,
                    },
                )
                a2, _ = Assessment.objects.get_or_create(
                    offering=off_311,
                    title="Course Design Project",
                    defaults={
                        "points_possible": Decimal("100.00"),
                        "status": Assessment.Status.APPROVED,
                    },
                )
                Assessment.objects.get_or_create(
                    offering=off_311,
                    title="Final Examination",
                    defaults={
                        "points_possible": Decimal("100.00"),
                        "status": Assessment.Status.APPROVED,
                    },
                )

                batch_311, _ = GradeBatch.objects.get_or_create(
                    offering=off_311,
                    name="Midterm & Project Release",
                    defaults={"released_at": timezone.now(), "released_by": faculty_311},
                )

                sample_scores = {
                    "demo.ada.student": (Decimal("96.00"), Decimal("98.00")),
                    "demo.alan.student": (Decimal("92.00"), Decimal("94.00")),
                    "demo.grace.student": (Decimal("95.00"), Decimal("91.00")),
                    "demo.baris.student": (Decimal("86.00"), Decimal("88.00")),
                }
                for enr in enrollments.get("CSE311", []):
                    username = enr.student.username
                    if username in sample_scores:
                        s1, s2 = sample_scores[username]
                        # Midterm grade
                        if not Grade.objects.filter(enrollment=enr, assessment=a1).exists():
                            g1 = Grade.objects.create(
                                offering=off_311,
                                enrollment=enr,
                                assessment=a1,
                                batch=batch_311,
                                state=Grade.State.SCORED,
                                points_earned=s1,
                                points_possible=Decimal("100.00"),
                                version=1,
                            )
                            GradeHistory.objects.create(
                                grade=g1,
                                version=1,
                                old_state="",
                                old_points_earned=None,
                                new_state=Grade.State.SCORED,
                                new_points_earned=s1,
                                reason="Midterm official grading",
                                changed_by=faculty_311,
                            )
                        # Project grade
                        if not Grade.objects.filter(enrollment=enr, assessment=a2).exists():
                            g2 = Grade.objects.create(
                                offering=off_311,
                                enrollment=enr,
                                assessment=a2,
                                batch=batch_311,
                                state=Grade.State.SCORED,
                                points_earned=s2,
                                points_possible=Decimal("100.00"),
                                version=1,
                            )
                            GradeHistory.objects.create(
                                grade=g2,
                                version=1,
                                old_state="",
                                old_points_earned=None,
                                new_state=Grade.State.SCORED,
                                new_points_earned=s2,
                                reason="Project demonstration score",
                                changed_by=faculty_311,
                            )

            # CSE321:
            off_321 = offerings.get("CSE321")
            if off_321:
                faculty_321 = coord_user
                b1, _ = Assessment.objects.get_or_create(
                    offering=off_321,
                    title="Relational Algebra Quiz",
                    defaults={
                        "points_possible": Decimal("50.00"),
                        "status": Assessment.Status.APPROVED,
                    },
                )
                b2, _ = Assessment.objects.get_or_create(
                    offering=off_321,
                    title="Midterm Examination",
                    defaults={
                        "points_possible": Decimal("100.00"),
                        "status": Assessment.Status.APPROVED,
                    },
                )
                batch_321, _ = GradeBatch.objects.get_or_create(
                    offering=off_321,
                    name="Midterm & Quiz Batch",
                    defaults={"released_at": timezone.now(), "released_by": faculty_321},
                )
                sample_scores_321 = {
                    "demo.ada.student": (Decimal("48.00"), Decimal("95.00")),
                    "demo.alan.student": (Decimal("46.00"), Decimal("90.00")),
                    "demo.grace.student": (Decimal("50.00"), Decimal("98.00")),
                    "demo.baris.student": (Decimal("42.00"), Decimal("84.00")),
                }
                for enr in enrollments.get("CSE321", []):
                    username = enr.student.username
                    if username in sample_scores_321:
                        q_pts, m_pts = sample_scores_321[username]
                        if not Grade.objects.filter(enrollment=enr, assessment=b1).exists():
                            g1 = Grade.objects.create(
                                offering=off_321,
                                enrollment=enr,
                                assessment=b1,
                                batch=batch_321,
                                state=Grade.State.SCORED,
                                points_earned=q_pts,
                                points_possible=Decimal("50.00"),
                                version=1,
                            )
                            GradeHistory.objects.create(
                                grade=g1,
                                version=1,
                                old_state="",
                                old_points_earned=None,
                                new_state=Grade.State.SCORED,
                                new_points_earned=q_pts,
                                reason="Quiz scoring",
                                changed_by=faculty_321,
                            )
                        if not Grade.objects.filter(enrollment=enr, assessment=b2).exists():
                            g2 = Grade.objects.create(
                                offering=off_321,
                                enrollment=enr,
                                assessment=b2,
                                batch=batch_321,
                                state=Grade.State.SCORED,
                                points_earned=m_pts,
                                points_possible=Decimal("100.00"),
                                version=1,
                            )
                            GradeHistory.objects.create(
                                grade=g2,
                                version=1,
                                old_state="",
                                old_points_earned=None,
                                new_state=Grade.State.SCORED,
                                new_points_earned=m_pts,
                                reason="Midterm official grading",
                                changed_by=faculty_321,
                            )

            self.stdout.write("Seeded assessments, grade batches, and grade histories.")

        # 11. Build and export seeded credentials
        credentials_data = {
            "institution": {
                "code": inst.code,
                "name": inst.name,
                "scope_id": str(inst.pk),
            },
            "program": {
                "code": program.code,
                "title": program.title,
                "scope_id": str(program.pk),
            },
            "terms": [
                {"term": f"{y}-{s}", "starts_at": str(st), "ends_at": str(et)}
                for y, s, st, et in term_specs
            ],
            "accounts": {
                "administrators": [
                    {
                        "username": a["username"],
                        "password": a["password"],
                        "role": a["role"],
                        "email": a["email"],
                        "description": a["description"],
                    }
                    for a in ADMIN_ACCOUNTS
                ],
                "coordinators": [
                    {
                        "username": c["username"],
                        "password": c["password"],
                        "role": c["role"],
                        "email": c["email"],
                        "title": c.get("title", ""),
                        "description": c["description"],
                    }
                    for c in COORDINATOR_ACCOUNTS
                ],
                "instructors": [
                    {
                        "username": i["username"],
                        "password": i["password"],
                        "role": i["role"],
                        "email": i["email"],
                        "description": i["description"],
                    }
                    for i in INSTRUCTOR_ACCOUNTS
                ],
                "students": [
                    {
                        "username": s["username"],
                        "password": s["password"],
                        "student_number": s["student_number"],
                        "cohort": s["cohort"],
                        "role": "student",
                        "email": s["email"],
                        "description": s["description"],
                    }
                    for s in STUDENT_ACCOUNTS
                ],
            },
            "offerings_sample": [
                {
                    "course_code": c_code,
                    "section": sec,
                    "term": "2026-fall",
                    "instructor": faculty.username,
                }
                for c_code, sec, faculty in offering_configs
            ],
        }

        target_file.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(target_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(credentials_data, output, indent=2, ensure_ascii=False)
        self.stdout.write(self.style.SUCCESS(f"Saved seeded credentials to: {target_file}"))

    @staticmethod
    def _demo_user(account, *, is_staff=False, is_superuser=False):
        existing = User.objects.filter(username=account["username"]).first()
        if existing:
            if (
                not existing.check_password(account["password"])
                or existing.email != account["email"]
            ):
                raise CommandError(
                    f"Existing user {account['username']} does not match demo credentials; refusing to modify it."
                )
            return existing
        return User.objects.create_user(
            username=account["username"],
            password=account["password"],
            email=account["email"],
            first_name=account["first_name"],
            last_name=account["last_name"],
            is_staff=is_staff,
            is_superuser=is_superuser,
        )
