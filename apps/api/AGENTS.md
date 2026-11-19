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

## Controller action design (discrete HTTP handlers)

- Follow the single-responsibility handler pattern (analogous to NestJS `@Get()`/`@Post()`
  and Spring Boot `@GetMapping`/`@PostMapping`).
- Do NOT combine multiple HTTP verbs into a single controller method with
  `if request.method == ...` branching (e.g., avoid `@action(methods=["get", "post"]) def items(...)`).
- Write separate, discrete methods for each HTTP method on custom actions, using
  verb-prefixed method names:
  - `list_<resource>` for `GET` collection sub-actions.
  - `create_<resource>` for `POST` creation sub-actions.
  - `update_<resource>` for `PATCH` or `PUT` update sub-actions.
  - `delete_<resource>` for `DELETE` removal sub-actions.
- Specify matching `url_path` and `url_name` on paired actions targeting the same
  endpoint (e.g., `@action(detail=True, methods=["get"], url_path="items", url_name="items")`
  and `@action(detail=True, methods=["post"], url_path="items", url_name="items")`).
- Use `AcademicRouter` (from `academic.router`) in URL registrations. It automatically
  merges discrete actions sharing the same `(url, detail)` into a unified route mapping
  without route shadowing or 405 errors.
- Use the `@validate_payload(SerializerClass)` interceptor decorator (analogous to NestJS
  `@Body(ValidationPipe)`). It instantiates, context-binds, and validates the serializer before
  the handler executes, injecting validated data as `payload` into the method kwargs.
  For partial updates (e.g. PATCH), pass `partial=True`. When merging URL parameters into the
  validated payload, pass `merge_data=lambda self, request, pk=None: {"parent": str(self.get_object().pk)}`.
- Do NOT write boilerplate `try: ... except DjangoValidationError: ...` blocks in controllers.
  `AcademicController.handle_exception` intercepts `DjangoValidationError` globally (analogous to a
  NestJS `ExceptionFilter`) and transforms it into a standard DRF 400 `ValidationError` response.

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
