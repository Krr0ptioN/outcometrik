"""PERF-01 measurement harness. Run after `seed_perf_cse321 --publish` on a dedicated database.

Order matters: published-state reads first, then scoring (which mutates grades and makes the
publications stale), then CSV import, then concurrency. Row counts/sizes are taken before and after.
"""

import csv
import io
import json
import os
import platform
import subprocess
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from unittest import mock

from access.models import AuditEvent, RoleAssignment, Scope
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, connections
from django.test.utils import CaptureQueriesContext

from academic import scoping, selectors
from academic.models import (
    Assessment,
    AssessmentLOMapping,
    CalculationRun,
    CourseOffering,
    CoursePOContribution,
    Enrollment,
    Grade,
    GradeBatch,
    GradeHistory,
    GradeImportRecord,
    Institution,
    LearningOutcome,
    LOPOMapping,
    OutcomeScore,
    Program,
    ProgramMembership,
    ProgramOutcome,
    Publication,
    Syllabus,
    SyllabusAssessment,
)
from academic.perf import SEED_VERSION, parse_plan, render_markdown, summarize
from academic.services import calculations as calc_module
from academic.services.analytics import CohortAnalyticsService
from academic.services.calculations import CalculationService
from academic.services.grade_import import MAX_CSV_ROWS, GradeImportService, compute_csv_checksum
from academic.services.publications import PublicationService

User = get_user_model()
STATS_MODELS = [
    Scope,
    RoleAssignment,
    AuditEvent,
    ProgramMembership,
    CourseOffering,
    Enrollment,
    Assessment,
    GradeBatch,
    Grade,
    GradeHistory,
    GradeImportRecord,
    Syllabus,
    LearningOutcome,
    SyllabusAssessment,
    AssessmentLOMapping,
    LOPOMapping,
    CoursePOContribution,
    ProgramOutcome,
    CalculationRun,
    OutcomeScore,
    Publication,
]
PG_SETTINGS = [
    "shared_buffers",
    "work_mem",
    "effective_cache_size",
    "maintenance_work_mem",
    "max_connections",
    "random_page_cost",
    "default_statistics_target",
    "track_io_timing",
    "log_lock_waits",
    "jit",
    "synchronous_commit",
]


def _ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000


@dataclass
class Spec:
    name: str
    family: str
    state: str  # draft | published | published (stale)
    filters: str
    run: Callable[[], object]
    plan: Callable[[], object] | None = None
    concurrent: bool = False


class PgSampler(threading.Thread):
    """Samples ungranted locks and backend count on its own connection while load runs."""

    def __init__(self, interval: float = 0.02):
        super().__init__(daemon=True)
        self.interval, self._halt = interval, threading.Event()
        self.samples = self.samples_waiting = self.max_waiting = self.max_backends = 0

    def run(self):
        try:
            with connection.cursor() as cur:
                while not self._halt.is_set():
                    cur.execute(
                        "SELECT (SELECT count(*) FROM pg_locks WHERE NOT granted), "
                        "(SELECT count(*) FROM pg_stat_activity WHERE datname = current_database())"
                    )
                    waiting, backends = cur.fetchone()
                    self.samples += 1
                    self.samples_waiting += 1 if waiting else 0
                    self.max_waiting = max(self.max_waiting, waiting)
                    self.max_backends = max(self.max_backends, backends)
                    time.sleep(self.interval)
        finally:
            connections.close_all()

    def stop(self) -> dict:
        self._halt.set()
        self.join(timeout=5)
        return {
            "lock_samples": self.samples,
            "samples_with_waiting_locks": self.samples_waiting,
            "max_waiting_locks": self.max_waiting,
            "max_backends_seen": self.max_backends,
        }


class Command(BaseCommand):
    help = "Measure query plans, latency, storage, scoring and import throughput (PERF-01)."

    def add_arguments(self, parser):
        parser.add_argument("--iterations", type=int, default=30)
        parser.add_argument("--warmup", type=int, default=3)
        parser.add_argument("--concurrency", type=int, default=8)
        parser.add_argument("--scoring-iterations", type=int, default=5)
        parser.add_argument("--machine-note", default="", help="Machine/PG deployment description")
        parser.add_argument("--targets-file", default="")
        parser.add_argument(
            "--output-dir", default=str(settings.BASE_DIR.parent.parent / "docs" / "perf")
        )

    # ----------------------------------------------------------------- main
    def handle(self, *args, **opts):
        if connection.vendor != "postgresql":
            raise CommandError("PERF-01 measurements require PostgreSQL.")
        from reports.services import ReportExportService

        out_dir = Path(opts["output_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        targets_path = Path(opts["targets_file"] or out_dir / "targets.json")
        targets = json.loads(targets_path.read_text()) if targets_path.exists() else {}

        ctx = self._load_context()
        results: dict = {"meta": self._environment(opts, out_dir), "latency": [], "plans": []}
        results["tables_before"] = self._table_stats()

        specs = self._build_specs(ctx, ReportExportService)
        self.stdout.write(f"Measuring {len(specs)} query families...")
        for spec in specs:
            results["latency"].append(
                self._bench(spec, iterations=opts["iterations"], warmup=opts["warmup"])
            )
        for spec in specs:
            if spec.concurrent and opts["concurrency"] > 1:
                results["latency"].append(
                    self._bench_concurrent(
                        spec, workers=opts["concurrency"], iterations=opts["iterations"]
                    )
                )
        results["plans"] = [self._capture_plan(s) for s in specs if s.plan]
        results["payload"] = self._payload(ctx)

        db_before = self._db_stats()
        results["scoring"] = self._bench_scoring(ctx, opts["scoring_iterations"])
        # Inputs changed: every publication of this offering is now stale.
        stale = Spec(
            "publication_is_stale_after_input_change",
            "publication",
            "published (stale)",
            "offering publication, 1 changed grade",
            lambda: ctx["pub_svc"].is_stale(publication=ctx["fac_off"]),
        )
        results["latency"].append(
            self._bench(stale, iterations=opts["iterations"], warmup=opts["warmup"])
        )
        results["import"] = self._bench_import(ctx)
        results["contention"] = self._bench_contention(ctx, opts["concurrency"])
        time.sleep(1.5)  # let pg_stat_database flush
        db_after = self._db_stats()
        results["contention"].update(self._delta(db_before, db_after))
        results["tables_after"] = self._table_stats()

        stem = "CSE321-results"
        (out_dir / f"{stem}.json").write_text(json.dumps(results, indent=2, default=str))
        (out_dir / f"{stem}.md").write_text(render_markdown(results, targets))
        self.stdout.write(self.style.SUCCESS(f"Wrote {out_dir / (stem + '.json')} and .md"))

    # -------------------------------------------------------------- context
    def _load_context(self) -> dict:
        try:
            inst = Institution.objects.get(code="PERF")
            program = Program.objects.get(department__institution=inst, code="CSE")
            coord = User.objects.get(username="perf.coordinator")
        except Exception as exc:
            raise CommandError("Run `seed_perf_cse321 --publish` on this database first.") from exc
        offerings = list(
            CourseOffering.objects.filter(program=program, course__code="CSE321", section="01")
            .select_related("term", "course")
            .order_by("term__starts_at")
        )
        latest = offerings[-1]
        target = CourseOffering.objects.get(program=program, course__code="CSE321", section="02")
        fac = Publication.Audience.FACULTY
        stu = Publication.Audience.STUDENT
        fac_off = Publication.objects.filter(offering=latest, audience=fac).first()
        stu_off = Publication.objects.filter(offering=latest, audience=stu).first()
        fac_prog = Publication.objects.filter(
            program=program, offering__isnull=True, audience=fac
        ).first()
        if not (fac_off and stu_off and fac_prog):
            raise CommandError("Publications missing: seed with --publish.")
        student = (
            Enrollment.objects.filter(offering=latest, eligible_for_outcomes=True)
            .select_related("student")
            .order_by("student_id")
            .first()
            .student
        )
        pub_svc = PublicationService(actor=coord)
        return {
            "program": program,
            "coord": coord,
            "student": student,
            "latest": latest,
            "target": target,
            "offerings": offerings,
            "fac_off": fac_off,
            "stu_off": stu_off,
            "fac_prog": fac_prog,
            "pub_svc": pub_svc,
            "student_pub_svc": PublicationService(actor=student),
            "analytics": CohortAnalyticsService(publication_service=pub_svc, actor=coord),
            "calc": CalculationService(),
            "trend_pubs": list(
                Publication.objects.filter(
                    program=program,
                    audience=fac,
                    offering__course__code="CSE321",
                    offering__section="01",
                )
            ),
        }

    # ---------------------------------------------------------------- specs
    def _build_specs(self, c, ReportExportService) -> list[Spec]:
        coord, student, latest = c["coord"], c["student"], c["latest"]
        program = c["program"]
        pub_svc, stu_svc = c["pub_svc"], c["student_pub_svc"]

        def gradebook():
            return (
                Grade.objects.filter(offering=latest)
                .select_related("enrollment__student", "assessment", "batch")
                .order_by("enrollment_id", "assessment_id")
            )

        def offering_qs(user):
            return scoping.scope_offerings(
                user, CourseOffering.objects.select_related("course", "term")
            )[:25]

        def enrollment_qs(user):
            return scoping.scope_enrollments(user, Enrollment.objects.all()).order_by("id")[:50]

        def cohort_scores():  # mirrors CohortAnalyticsService._filtered_po_scores (offering run)
            return (
                c["fac_off"]
                .run.scores.filter(level=OutcomeScore.Level.COURSE_PO)
                .select_related("offering", "program_outcome")
                .order_by("outcome_code", "id")
            )

        def export(user, pub, fmt, scope):
            kwargs = {"program_id": program.pk} if scope == "cohort" else {}
            return lambda: ReportExportService(actor=user).export(
                publication_id=pub.pk, format=fmt, scope=scope, **kwargs
            )

        S = Spec
        return [
            S(
                "crud_offerings_staff",
                "scoped_crud",
                "draft",
                "coordinator, page=25",
                lambda: list(offering_qs(coord)),
                lambda: offering_qs(coord),
            ),
            S(
                "crud_offerings_student",
                "scoped_crud",
                "draft",
                "student, page=25",
                lambda: list(offering_qs(student)),
                lambda: offering_qs(student),
            ),
            S(
                "crud_enrollments_student",
                "scoped_crud",
                "draft",
                "student, page=50",
                lambda: list(enrollment_qs(student)),
                lambda: enrollment_qs(student),
            ),
            S(
                "crud_roster_offering",
                "scoped_crud",
                "draft",
                "eligible roster, one offering",
                lambda: list(selectors.eligible_roster(latest)),
                lambda: selectors.eligible_roster(latest),
            ),
            S(
                "gradebook_full",
                "gradebook",
                "draft",
                "one offering, all grades",
                lambda: list(gradebook()),
                gradebook,
                concurrent=True,
            ),
            S(
                "gradebook_page_200",
                "gradebook",
                "draft",
                "one offering, page=200",
                lambda: list(gradebook()[:200]),
                lambda: gradebook()[:200],
            ),
            S(
                "evidence_student_drilldown",
                "evidence",
                "published",
                "student audience, own scores",
                lambda: list(stu_svc.list_scores(publication=c["stu_off"], actor=student)),
                lambda: stu_svc.list_scores(publication=c["stu_off"], actor=student),
            ),
            S(
                "evidence_staff_drilldown",
                "evidence",
                "published",
                "faculty audience, one student",
                lambda: list(pub_svc.list_scores(publication=c["fac_off"], student_id=student.pk)),
                lambda: pub_svc.list_scores(publication=c["fac_off"], student_id=student.pk),
            ),
            S(
                "publication_list_staff",
                "publication",
                "published",
                "coordinator, page=25",
                lambda: list(pub_svc.get_queryset(actor=coord)[:25]),
                lambda: pub_svc.get_queryset(actor=coord)[:25],
                concurrent=True,
            ),
            S(
                "publication_list_student",
                "publication",
                "published",
                "student, page=25",
                lambda: list(stu_svc.get_queryset(actor=student)[:25]),
                lambda: stu_svc.get_queryset(actor=student)[:25],
                concurrent=True,
            ),
            S(
                "publication_is_stale_offering",
                "publication",
                "published",
                "offering publication",
                lambda: pub_svc.is_stale(publication=c["fac_off"]),
                None,
                concurrent=True,
            ),
            S(
                "publication_is_stale_program",
                "publication",
                "published",
                "program publication",
                lambda: pub_svc.is_stale(publication=c["fac_prog"]),
            ),
            S(
                "analytics_cohort_offering",
                "analytics",
                "published",
                "offering publication",
                lambda: c["analytics"].cohort_summary(publication=c["fac_off"]),
                cohort_scores,
                concurrent=True,
            ),
            S(
                "analytics_cohort_program",
                "analytics",
                "published",
                "program publication",
                lambda: c["analytics"].cohort_summary(publication=c["fac_prog"]),
            ),
            S(
                "analytics_trends",
                "analytics",
                "published",
                f"{len(c['trend_pubs'])} term publications",
                lambda: c["analytics"].compare_trends(publications=c["trend_pubs"]),
            ),
            S(
                "export_cohort_csv",
                "export",
                "published",
                "cohort, csv",
                export(coord, c["fac_off"], "csv", "cohort"),
            ),
            S(
                "export_cohort_pdf",
                "export",
                "published",
                "cohort, pdf",
                export(coord, c["fac_off"], "pdf", "cohort"),
            ),
            S(
                "export_student_csv",
                "export",
                "published",
                "student, csv",
                export(student, c["stu_off"], "csv", "student"),
            ),
            S(
                "export_student_pdf",
                "export",
                "published",
                "student, pdf",
                export(student, c["stu_off"], "pdf", "student"),
            ),
        ]

    # --------------------------------------------------------------- bench
    def _bench(self, spec: Spec, *, iterations: int, warmup: int) -> dict:
        entry = {
            "name": spec.name,
            "family": spec.family,
            "state": spec.state,
            "filters": spec.filters,
            "concurrency": 1,
            "cache": f"warm: {warmup} warmup calls; first_ms is the first call in this process",
        }
        try:
            connection.queries_log.clear()
            with CaptureQueriesContext(connection) as queries:
                t0 = time.perf_counter()
                spec.run()
                first = _ms(t0)
        except Exception as exc:  # noqa: BLE001 - harness records any spec failure and continues
            entry["error"] = f"{type(exc).__name__}: {exc}"
            return entry
        entry.update(queries=len(queries), first_ms=round(first, 2))
        for _ in range(warmup):
            spec.run()
        samples = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            spec.run()
            samples.append(_ms(t0))
        entry.update(summarize(samples))
        return entry

    def _bench_concurrent(self, spec: Spec, *, workers: int, iterations: int) -> dict:
        def worker():
            out = []
            try:
                for _ in range(iterations):
                    t0 = time.perf_counter()
                    spec.run()
                    out.append(_ms(t0))
            finally:
                connections.close_all()
            return out

        sampler = PgSampler()
        sampler.start()
        t0 = time.perf_counter()
        try:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                samples = [
                    s for f in [pool.submit(worker) for _ in range(workers)] for s in f.result()
                ]
        except Exception as exc:  # noqa: BLE001 - harness records any spec failure and continues
            sampler.stop()
            return {
                "name": spec.name,
                "state": spec.state,
                "filters": spec.filters,
                "concurrency": workers,
                "error": f"{type(exc).__name__}: {exc}",
            }
        wall = _ms(t0)
        stats = sampler.stop()
        return {
            "name": spec.name,
            "family": spec.family,
            "state": spec.state,
            "filters": spec.filters,
            "concurrency": workers,
            "throughput_per_s": round(len(samples) / (wall / 1000), 1),
            "max_waiting_locks": stats["max_waiting_locks"],
            "max_backends_seen": stats["max_backends_seen"],
            **summarize(samples),
        }

    def _capture_plan(self, spec: Spec) -> dict:
        entry = {"name": spec.name, "state": spec.state}
        try:
            text = spec.plan().explain(analyze=True, buffers=True)
        except Exception as exc:  # noqa: BLE001 - harness records any plan failure and continues
            entry["error"] = f"{type(exc).__name__}: {exc}"
            return entry
        entry.update(parse_plan(text), text=text)
        return entry

    # ------------------------------------------------------------- scoring
    def _bench_scoring(self, c, iterations: int) -> dict:
        """Real recalculations: one grade changes per iteration so the input hash changes.

        Wall time includes manifest capture (under row locks), Decimal compute, OutcomeScore
        bulk insert with evidence JSON, and the run status update.
        """
        calc, latest, coord = c["calc"], c["latest"], c["coord"]
        rows = list(
            Grade.objects.filter(offering=latest, state=Grade.State.SCORED)
            .order_by("id")
            .values_list("pk", "points_earned")[:iterations]
        )
        timings: dict[str, list] = {"manifest": [], "compute": []}
        real_manifest = CalculationService.build_manifest_and_hash
        real_compute = calc_module._compute_from_manifest

        def timed_manifest(self, *a, **kw):
            t0 = time.perf_counter()
            try:
                return real_manifest(self, *a, **kw)
            finally:
                timings["manifest"].append(_ms(t0))

        def timed_compute(manifest):
            t0 = time.perf_counter()
            try:
                return real_compute(manifest)
            finally:
                timings["compute"].append(_ms(t0))

        totals, persist, created_flags, query_counts = [], [], [], []
        last_run = None
        with (
            mock.patch.object(CalculationService, "build_manifest_and_hash", timed_manifest),
            mock.patch.object(calc_module, "_compute_from_manifest", timed_compute),
        ):
            for pk, old in rows:
                Grade.objects.filter(pk=pk).update(points_earned=old - Decimal("0.01"))
                timings["manifest"].clear()
                timings["compute"].clear()
                connection.queries_log.clear()
                with CaptureQueriesContext(connection) as queries:
                    t0 = time.perf_counter()
                    run, created = calc.run_offering(offering=latest, actor=coord)
                    total = _ms(t0)
                totals.append(total)
                created_flags.append(created)
                query_counts.append(len(queries))
                m, k = sum(timings["manifest"]), sum(timings["compute"])
                persist.append(max(total - m - k, 0.0))
                last_run = run
        if not totals:
            return {"error": "no scored grades to mutate"}
        info = {
            "offering": f"CSE321-01 {latest.term}",
            "iterations": len(totals),
            "real_recalculations": sum(created_flags),
            "total_ms": summarize(totals),
            "manifest_capture_ms (last iter)": round(m, 2),
            "compute_ms (last iter)": round(k, 2),
            "persist_and_run_insert_ms (derived: total - manifest - compute)": summarize(persist),
            "queries_per_run": summarize([float(q) for q in query_counts])["p50"],
            "note": "Grades changed via queryset update (no version bump/history): benchmark DB only.",
        }
        if last_run is not None:
            info.update(self._run_payload(last_run))
        return info

    @staticmethod
    def _run_payload(run) -> dict:
        score_t, run_t = OutcomeScore._meta.db_table, CalculationRun._meta.db_table
        with connection.cursor() as cur:
            cur.execute(
                f"SELECT count(*), COALESCE(sum(pg_column_size(evidence)),0), "
                f"COALESCE(max(pg_column_size(evidence)),0) FROM {score_t} WHERE run_id = %s",
                [run.pk],
            )
            rows, ev_total, ev_max = cur.fetchone()
            cur.execute(
                f"SELECT pg_column_size(manifest), octet_length(manifest::text) FROM {run_t} WHERE id = %s",
                [run.pk],
            )
            stored, raw = cur.fetchone()
        return {
            "outcome_score_rows": rows,
            "evidence_bytes_total (stored)": ev_total,
            "evidence_bytes_max_row (stored)": ev_max,
            "manifest_bytes (stored/raw JSON)": f"{stored} / {raw}",
        }

    def _payload(self, c) -> dict:
        score_t = OutcomeScore._meta.db_table
        out = {}
        with connection.cursor() as cur:
            cur.execute(
                f"SELECT count(*), COALESCE(sum(pg_column_size(evidence)),0) FROM {score_t} "
                "WHERE run_id = %s AND student_id = %s",
                [c["stu_off"].run_id, c["student"].pk],
            )
            out["student drill-down rows / evidence bytes"] = " / ".join(map(str, cur.fetchone()))
        out["offering run (published)"] = self._run_payload(c["fac_off"].run)
        out["program run (published)"] = self._run_payload(c["fac_prog"].run)
        return out

    # -------------------------------------------------------------- import
    def _bench_import(self, c) -> dict:
        target, coord = c["target"], c["coord"]
        svc = GradeImportService(actor=coord)
        titles = list(
            Assessment.objects.filter(offering=target)
            .order_by("title")
            .values_list("title", flat=True)
        )
        numbers = dict(
            ProgramMembership.objects.filter(program=c["program"]).values_list(
                "user_id", "student_number"
            )
        )
        student_ids = list(
            Enrollment.objects.filter(offering=target, status=Enrollment.Status.ENROLLED)
            .order_by("student_id")
            .values_list("student_id", flat=True)
        )

        def make_csv(delta: Decimal) -> tuple[str, int]:
            buf = io.StringIO()
            w = csv.writer(buf, lineterminator="\n")
            w.writerow(["student_identifier", "assessment", "state", "points_earned", "reason"])
            n = 0
            for sid in student_ids:
                for i, title in enumerate(titles):
                    if n >= MAX_CSV_ROWS:
                        return buf.getvalue(), n
                    w.writerow(
                        [
                            numbers[sid],
                            title,
                            "scored",
                            str(Decimal(50 + (sid + i) % 40) + delta),
                            "",
                        ]
                    )
                    n += 1
            return buf.getvalue(), n

        batch_name = "perf-import-batch"
        report = {}
        csv_a, rows = make_csv(Decimal("0.00"))
        csv_b, _ = make_csv(Decimal("1.00"))

        def timed(label, fn):
            connection.queries_log.clear()
            with CaptureQueriesContext(connection) as q:
                t0 = time.perf_counter()
                result = fn()
                ms = _ms(t0)
            report[f"{label}_ms"] = round(ms, 1)
            report[f"{label}_rows_per_s"] = round(rows / (ms / 1000), 1)
            report[f"{label}_queries"] = len(q)
            return result

        try:
            timed(
                "dry_run",
                lambda: svc.dry_run(offering=target, csv_text=csv_a, batch_name=batch_name),
            )
            timed(
                "apply_create",
                lambda: svc.apply(
                    actor=coord,
                    offering=target,
                    csv_text=csv_a,
                    idempotency_key="perf-import-a",
                    file_checksum=compute_csv_checksum(csv_a),
                    batch_name=batch_name,
                ),
            )
            timed(
                "apply_update",
                lambda: svc.apply(
                    actor=coord,
                    offering=target,
                    csv_text=csv_b,
                    idempotency_key="perf-import-b",
                    file_checksum=compute_csv_checksum(csv_b),
                    batch_name=batch_name,
                ),
            )
            timed(
                "apply_replay",
                lambda: svc.apply(
                    actor=coord,
                    offering=target,
                    csv_text=csv_b,
                    idempotency_key="perf-import-b",
                    file_checksum=compute_csv_checksum(csv_b),
                    batch_name=batch_name,
                ),
            )
        except Exception as exc:  # noqa: BLE001 - harness records any import failure and continues
            report["error"] = f"{type(exc).__name__}: {exc}"
        report["csv_rows"] = rows
        report["csv_bytes"] = len(csv_a.encode())
        report["batch_released"] = "no (unreleased batch: no input-revision bump)"
        return report

    # ----------------------------------------------------------- contention
    def _bench_contention(self, c, workers: int) -> dict:
        """N concurrent identical offering runs: each takes FOR UPDATE locks during capture."""
        calc, latest, coord = c["calc"], c["latest"], c["coord"]

        def call():
            try:
                t0 = time.perf_counter()
                calc.run_offering(offering=latest, actor=coord)
                return _ms(t0)
            finally:
                connections.close_all()

        sampler = PgSampler()
        sampler.start()
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            samples = [f.result() for f in [pool.submit(call) for _ in range(workers * 3)]]
        wall = _ms(t0)
        out = {
            "scenario": f"{workers} workers x3 calls of run_offering, same offering, unchanged inputs",
            "wall_ms": round(wall, 1),
            "latency_ms": summarize(samples),
        }
        out.update(sampler.stop())
        return out

    # ----------------------------------------------------------- db helpers
    @staticmethod
    def _db_stats() -> dict:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT xact_commit, xact_rollback, blks_read, blks_hit, deadlocks, temp_files, temp_bytes "
                "FROM pg_stat_database WHERE datname = current_database()"
            )
            keys = (
                "commits",
                "rollbacks",
                "blks_read",
                "blks_hit",
                "deadlocks",
                "temp_files",
                "temp_bytes",
            )
            return dict(zip(keys, cur.fetchone(), strict=True))

    @staticmethod
    def _delta(before: dict, after: dict) -> dict:
        d = {f"db_{k}": after[k] - before[k] for k in before}
        total = d["db_blks_hit"] + d["db_blks_read"]
        d["db_cache_hit_ratio"] = round(d["db_blks_hit"] / total, 4) if total else None
        return d

    @staticmethod
    def _table_stats() -> list[dict]:
        out = []
        with connection.cursor() as cur:
            for model in STATS_MODELS:
                table = model._meta.db_table
                cur.execute(
                    "SELECT pg_relation_size(c.oid), "
                    "CASE WHEN c.reltoastrelid <> 0 THEN pg_total_relation_size(c.reltoastrelid) ELSE 0 END, "
                    "pg_indexes_size(c.oid), pg_total_relation_size(c.oid) "
                    "FROM pg_class c WHERE c.oid = %s::regclass",
                    [f'"{table}"'],
                )
                heap, toast, idx, total = cur.fetchone()
                out.append(
                    {
                        "table": table,
                        "rows": model.objects.count(),  # exact count(*), not reltuples
                        "heap_bytes": heap,
                        "toast_bytes": toast,
                        "index_bytes": idx,
                        "total_bytes": total,
                    }
                )
        return out

    @staticmethod
    def _environment(opts, out_dir: Path) -> dict:
        with connection.cursor() as cur:
            cur.execute("SHOW server_version")
            version = cur.fetchone()[0]
            cur.execute(
                "SELECT name, setting || COALESCE(unit, '') FROM pg_settings WHERE name = ANY(%s)",
                [PG_SETTINGS],
            )
            pg = dict(cur.fetchall())
        try:
            sha = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            sha = "unknown"
        seed_meta = out_dir / "seed-meta.json"
        return {
            "measured_at": __import__("datetime")
            .datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
            "seed_version": SEED_VERSION,
            "seed_meta": seed_meta.read_text().replace("\n", " ")
            if seed_meta.exists()
            else "missing",
            "git_commit": sha or "unknown",
            "postgres": version,
            "postgres_host": settings.DATABASES["default"].get("HOST") or "local socket",
            "client_machine": f"{platform.platform()}, {os.cpu_count()} CPUs",
            "machine_note": opts["machine_note"] or "NOT DOCUMENTED: pass --machine-note",
            "iterations": opts["iterations"],
            "warmup": opts["warmup"],
            "concurrency": opts["concurrency"],
            "pg_settings": pg,
        }
