# API coding style and architecture

These conventions apply to API applications and modules beneath `apps/api/`.
The repository root `AGENTS.md` and `docs/CODE_STYLE.md` still apply.

## Academic API structure & Wireup DI

- Keep academic HTTP controllers in `academic/controllers/`, organized by domain resource:
  `institutions`, `departments`, `terms`, `courses`, `programs`, `program_courses`,
  `program_memberships`, `offerings`, `instructor_assignments`, `enrollments`,
  `outcomes` (`po_sets`), `syllabi`, `assessments`, `grades`, and `workspaces`.
- Keep pure `@injectable` domain services in `academic/services/` (`structure`, `programs`,
  `offerings`, `enrollments`, `outcomes`, `syllabi`, `assessments`, `grades`, `workspaces`).
  Do not add new domain logic to a monolithic `services.py` file.
- Register every module containing `@injectable` providers or domain services in
  `WIREUP.injectables` inside `apps/api/config/settings.py` (with `auto_inject_views=False`
  and `wireup.integration.django.wireup_middleware` enabled in `MIDDLEWARE`).
- **Composition over inheritance**: do not introduce monolithic controller or service base
  classes (legacy `AcademicController` and `AcademicService` were removed in DC-01.10).
  Controllers compose DRF mixins (`mixins.CreateModelMixin`, `mixins.ListModelMixin`,
  `mixins.RetrieveModelMixin`, `mixins.UpdateModelMixin`, `viewsets.GenericViewSet`, or
  `APIView`) and shared `AcademicPagination` from `academic/controllers/base.py`.
- **Explicit constructor injection (`di-prefer-constructor-injection`)**:
  - Services declare collaborators (for example, `auth_service: AuthorizationService`) in
    their `__init__` constructor and accept an optional `actor: Any = None` keyword argument.
  - Controllers accept optional injected service instances in
    `__init__(self, service: MyService | None = None, **kwargs)` and resolve default
    instances via `academic_service_provider.provide(MyService)` (`WireupServiceProvider` in
    `academic/services/provider.py`), which delegates directly to Wireup's
    `get_app_container()`.
  - Keep controllers and services unit-testable by passing mock or stub collaborators directly
    into `__init__` constructors.
- **Prohibit runtime service locators (`di-avoid-service-locator`)**: never resolve services
  dynamically inside action methods or service methods (legacy `get_service(...)` lookups are
  removed). Declare all collaborators up front in `__init__` so Wireup validates the
  dependency graph at container boot time.
- **Keep controllers thin**: controllers translate HTTP requests and responses, apply guards
  and payload validation decorators, invoke serializers, and delegate queries and mutations to
  injected services. Controllers must not implement lifecycle rules or domain invariants.
- Serializers validate and represent the wire contract. Put cross-field domain rules,
  immutable-identity rules, and state transitions in domain services or validator classes.
- Preserve existing routes and wire contracts when restructuring controllers or services. Add
  focused DI/service tests (`test_*_di.py`) for container resolution, allowed/denied scopes,
  and HTTP contracts.

## Authorization permissions & scoping (`security-use-guards`)

- Enforce RBAC/ABAC capability validation declaratively at the controller boundary using
  DRF's native `permission_classes` with `HasScopedCapability` / `scoped_permission(...)`
  (exported from `academic.decorators` and `academic.guards`):
  - Pass `permission_classes=[IsAuthenticated, scoped_permission(...)]` directly to
    route decorators (`@get`, `@post`, `@put`, `@patch`, `@delete`) or DRF's
    `permission_classes` / `get_permissions()`.
  - Use `scope_field` for declarative dot-separated lookup on the payload or target instance
    (for example, `scoped_permission("program.manage", scope_field="department.institution")`,
    `scoped_permission("syllabus.draft", scope_field="offering")`,
    `scoped_permission("access.manage", scope_field="name")`).
  - Use `scope_param` when the scope UUID comes from a URL kwarg or payload field, or
    `scope_getter` when custom resolution is required.
  - Detail actions (`pk` in kwargs) without an explicit `scope_getter` or `scope_param`
    defer to `HasScopedCapability.has_object_permission()`, which DRF runs automatically
    inside `self.get_object()` (single DB query, preserving `404` on scoped-out objects).
- **Zero mutation authorization checks inside domain services**: domain services must not
  call `_check_access` or perform controller-boundary capability checks inside `create`/`update`
  mutations. Services own:
  - Actor-scoped, deny-by-default read querysets (`get_queryset(actor=...)` and
    `visible_queryset(...)` backed by `academic/scoping.py`),
  - Domain invariants, row locking (`select_for_update`), transactions, and persistence.
- Pass the acting user (`actor`) explicitly to service queries and actor-attributed operations
  (for example, `approve`, `activate`, `correct`, `release`). Do not infer an actor from
  global state or serializer context inside a service.
- Controllers must retrieve records through service-scoped querysets (`get_queryset`) before
  mutating individual objects so out-of-scope detail lookups return `404`.

## Decorator-driven routing & payload validation

- Register controllers and HTTP routes using NestJS-style decorators exported from
  `academic.decorators` (implemented in `academic/router.py` and `academic/decorators.py`):
  - Class decorator: `@controller("<prefix>", basename="<name>")`.
  - Method decorators: `@get(...)`, `@post(...)`, `@put(...)`, `@patch(...)`, `@delete(...)`
    (wrapping `@route(...)`).
    - Root collection routes: `@get()`, `@post()`
    - Detail routes: `@get("{id}")`, `@patch("{id}")`, `@delete("{id}")`
    - Sub-resource routes: `@get("{id}/enrollments")`, `@post("{id}/approve")`,
      `@patch(r"{id}/learning-outcomes/(?P<child_pk>[^/.]+)", url_name="learning-outcome-detail")`
- Use `AcademicRouter` (`academic_router` in `academic/router.py`) with auto-discovery in
  `academic/urls.py` (`import academic.controllers`). `AcademicRouter` maps root/detail
  decorator overrides and merges discrete actions sharing `(url, detail)` into a unified
  route mapping without route shadowing or `405` errors.
- Follow the single-responsibility handler pattern: write discrete methods for each HTTP verb
  (`list_<resource>`, `create_<resource>`, `update_<resource>`, `delete_<resource>`). Do NOT
  combine multiple HTTP verbs into a single handler with `if request.method == ...` branching.
- Use `@validate_payload(SerializerClass)` (aliases `@validate_dto`, `@body`) before handler
  execution. It context-binds and validates the serializer, injecting `payload=serializer.validated_data`
  (and `serializer=serializer` when requested) into handler kwargs. For partial updates pass
  `partial=True` (automatically enabled on `PATCH`); to inject URL params into the payload
  before validation, pass
  `merge_data=lambda self, request, pk=None: {"offering": str(self.get_object().pk)}`.

## Cross-cutting providers, interceptors, and exception filter

- **Configuration (`devops-use-config-module`)**: inject `@injectable class ApiConfig` from
  `config/config_service.py` rather than scattering raw `django.conf.settings` lookups inside
  services or components.
- **Structured logging & execution timing**: inject `@injectable class AppLogger` and apply
  `@intercept_logging` from `academic/interceptors.py` for structured action timing and audit
  logging.
- **Global exception filter**: `academic_exception_handler` (`academic/filters.py`) is
  configured as `REST_FRAMEWORK["EXCEPTION_HANDLER"]` in `apps/api/config/settings.py`
  (with `AcademicExceptionFilter` available as a mixin for standalone views). It globally
  intercepts `django.core.exceptions.ValidationError` (`400`) and
  `django.core.exceptions.PermissionDenied` (`403`) and sets `Cache-Control: no-store`.
  Do NOT write boilerplate `try: ... except DjangoValidationError: ...` blocks in controllers.
  All controllers also ensure `Cache-Control: no-store` in `finalize_response`.

## Domain validator design (business invariant enforcement)

- Follow the class-based domain validator pattern (e.g., `GradeValidator`,
  `ProgramOutcomeSetValidator`, `SyllabusValidator`).
- Encapsulate domain invariant rules, lifecycle prerequisites, sibling uniqueness constraints,
  and editability checks into dedicated validator classes in `<domain>_validation.py`.
- Structure validator classes with descriptive static methods:
  - `validate_<lifecycle_action>` (e.g., `validate_activation`, `validate_approval`,
    `validate_revision`)
  - `validate_<invariant>` (e.g., `validate_editable`, `validate_assessment_points`,
    `validate_mutation`, `validate_set_update`)
- Keep domain validation pure and isolated from database transaction locking (`select_for_update`)
  and write operations. Services own row locks, transactions, and mutations, passing models or
  pre-queried related state to validators.
- Validators must raise `django.core.exceptions.ValidationError` with specific, user-actionable
  error messages (or field error dictionaries for field-specific invariants).
- Export domain validator classes in `academic/services/__init__.py` alongside services so they
  can be tested in isolation and reused across commands or batch pipelines.
- Avoid loose module-level business or validation helper functions. Callers (controllers,
  commands, and tests) must directly invoke the domain service class or domain validator class.

## Django conventions

- Prefer explicit `@injectable` service classes and typed method inputs over module-level
  business functions.
- Keep each transaction (`@transaction.atomic`) around the complete domain operation, including
  its audit events, `RevisionTracker.bump(...)`, and related assignments.
- Use the `access` module's authorization and assignment services (`access.services.assign`,
  `access.services.revoke`, `AuthorizationService`); do not write role or capability records
  directly from academic controllers.
- Do not add destructive delete endpoints for academic history. Use the existing lifecycle or
  archival rules.
- Run API tests, Ruff lint and formatting checks, Django system checks, and migration checks
  for backend changes. Report any checks blocked by the environment.

## Subtask git / worktree & linear squash-merge workflow

- **Dedicated branch per subtask**: branch directly from an up-to-date `main` branch (e.g.
  `feat/<issue-slug>`). Never branch from an unmerged feature branch.
- **Isolated worktrees**: when executing subtasks in parallel or via a dedicated `git worktree`,
  use an isolated PostgreSQL database (`POSTGRES_DB=outcometrik_<slug>`) and never modify
  sibling worktrees. Do not run `git checkout main` or `gh pr merge --delete-branch` inside
  a linked worktree; delete only the remote branch after squash-merge.
- **Linear squash-merge**:
  - Rebase onto latest `origin/main` (`git fetch origin main && git rebase origin/main`) and
    re-verify checks before pushing.
  - Open an independent PR targeting `main` with a conventional PR title, valid branch name,
    non-empty body, `Closes #<subtask-issue-id>`, and `Ref: #<parent-issue-id>`.
  - Wait until all CI workflows (`PR Validation`, `lint`, `test`, `build`, `e2e`) pass and the
    PR is squash-merged into `main` before starting the next subtask.
