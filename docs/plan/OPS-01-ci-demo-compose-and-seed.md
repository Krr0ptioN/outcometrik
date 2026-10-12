# OPS-01 — CI, demo Compose setup, and deterministic seed data

**Blocked by:** BOOT-01.

## User story

As a contributor or evaluator, I can boot a realistic synthetic Outcometrik environment and run the quality gates, so the pilot can be demonstrated and reproduced safely.

## Rules

- The demo uses synthetic names, identifiers, grades, and mappings unless explicit institutional authorization exists.
- Seed data must include eleven POs, multiple courses/offerings, students, assessments, mappings, grades, calculations, and at least one publication.
- Seeding is deterministic and resettable; it must not overwrite non-demo data without an explicit isolated environment.
- CI runs formatting, lint, unit/integration tests, build, migrations, health checks, and relevant frontend checks.
- Compose services expose only required local ports and use environment-managed secrets.
- CI artifacts and logs must not contain raw grade rosters, credentials, or private student identifiers.
- Backup/restore and smoke workflows are documented as operational checks, not implied by local Compose alone.

## Acceptance criteria

- [ ] A clean checkout boots the demo stack with one documented command.
- [ ] The seeded scenario demonstrates the canonical score path and profile/report views.
- [ ] Resetting the demo reproduces identical IDs/data or documented deterministic equivalents.
- [ ] CI passes on a clean database and fails on migration/health/test errors.
- [ ] Logs and artifacts contain no sensitive demo leakage.
