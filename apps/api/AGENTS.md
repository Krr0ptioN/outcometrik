# API coding style and architecture

These conventions apply to API applications and modules beneath `apps/api/`.
The repository root `AGENTS.md` and `docs/CODE_STYLE.md` still apply.

## Academic API structure

- Keep academic HTTP controllers in `academic/controllers/`, with a controller
  module for each resource or closely related endpoint: institutions,
  departments, programs, terms, courses, program courses, memberships,
  offerings, instructor assignments, enrollments, and workspaces.
- Keep academic domain services in `academic/services/`. Do not add new domain
  logic to a monolithic `services.py` file.
- Keep controllers thin. Controllers translate HTTP requests and responses,
  invoke serializers, and delegate querying and mutations to injected services.
  They must not decide authorization, scope visibility, lifecycle rules, or
  domain invariants.
- Services receive the acting user explicitly and own authorization, scoped
  querysets, domain rules, transactions, and writes. Do not infer an actor from
  global state or from serializer context inside a service.
- Inject request-scoped service instances through the academic service provider
  seam. Keep service classes replaceable in tests; do not construct services
  directly in individual controller actions.
- Serializers validate and represent the API contract. Put cross-field domain
  rules, immutable-identity rules, authorization, and state transitions in
  services or domain policy modules.
- Keep selectors/queryset scoping reusable and deny-by-default. Controllers
  must obtain records through service-scoped querysets before retrieving or
  mutating individual objects.
- Preserve existing routes and wire contracts when restructuring controllers
  or services. Add focused service tests for allowed and denied scopes, and API
  tests for HTTP behavior and serialization.

## Django conventions

- Prefer explicit service classes and typed method inputs over module-level
  business functions.
- Keep each transaction around the complete domain operation, including its
  audit events and related assignments.
- Use the access module's authorization and assignment services; do not write
  role or capability records directly from academic controllers.
- Do not add destructive delete endpoints for academic history. Use the
  existing lifecycle or archival rules.
- Run API tests, Ruff lint and formatting checks, Django system checks, and
  migration checks for backend changes. Report any environment-blocked checks.
