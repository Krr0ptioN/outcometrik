import json
from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from academic.models import Program, ProgramOutcome, ProgramOutcomeSet
from academic.services.outcomes import activate_set

DEFAULT_FILE = Path(__file__).resolve().parents[2] / "seed_data" / "program_outcomes.json"
EXPECTED_CODES = [f"PO{i}" for i in range(1, 12)]


class Command(BaseCommand):
    help = "Seed the pilot PO1..PO11 outcome set (v1, active) for one program."

    def add_arguments(self, parser):
        parser.add_argument("--program", required=True, help="Program code")
        parser.add_argument("--effective-date", required=True, help="YYYY-MM-DD")
        parser.add_argument("--actor", required=True, help="Username of the activating user")
        parser.add_argument("--file", default=str(DEFAULT_FILE))

    @transaction.atomic
    def handle(self, *args, **opts):
        data = json.loads(Path(opts["file"]).read_text(encoding="utf-8"))
        outcomes = data["outcomes"]
        if [o["code"] for o in outcomes] != EXPECTED_CODES:
            raise CommandError("Seed file must contain exactly PO1..PO11, in order.")
        values = [data["source_reference"]] + [
            o[f] for o in outcomes for f in ("label", "description", "source_url")
        ]
        if any(not v.strip() or v.strip() == "TODO" for v in values):
            raise CommandError("Seed file still has empty or TODO values.")

        try:
            program = Program.objects.get(code=opts["program"])
        except (Program.DoesNotExist, Program.MultipleObjectsReturned) as exc:
            raise CommandError("Program code not found or not unique.") from exc
        user_model = get_user_model()
        try:
            actor = user_model.objects.get(**{user_model.USERNAME_FIELD: opts["actor"]})
        except user_model.DoesNotExist as exc:
            raise CommandError("Actor not found.") from exc

        if program.outcome_sets.exists():
            self.stdout.write("Program already has outcome sets; nothing to do.")
            return

        outcome_set = ProgramOutcomeSet.objects.create(
            program=program, version=1, source_reference=data["source_reference"]
        )
        for index, outcome in enumerate(outcomes, start=1):
            ProgramOutcome.objects.create(
                outcome_set=outcome_set,
                code=outcome["code"],
                label=outcome["label"],
                description=outcome["description"],
                source_url=outcome["source_url"],
                ordering=index,
            )
        activate_set(outcome_set, actor, date.fromisoformat(opts["effective_date"]))
        self.stdout.write(f"Seeded and activated PO set v1 for {program.code}.")
