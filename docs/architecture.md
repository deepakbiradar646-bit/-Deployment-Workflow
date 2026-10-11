# Architecture document

## Context
The assignment asks for a representative MLOps application with a Python API, Angular UI, registry, deployment governance, monitoring, and operational design. The implementation is local-first and does not require Azure.

## Scope
- Model registration, versioning, lifecycle, and approval audit
- Deployment request, local asynchronous execution, retry, rollback, and event history
- Monitoring metadata, operational counts, health, and readiness APIs
- Angular operator workflow and API documentation
- Docker packaging, tests, and CI

## Architecture overview
Angular calls FastAPI over HTTP/JSON. FastAPI validates contracts and lifecycle rules, SQLAlchemy persists records in SQLite by default, and FastAPI background tasks simulate deployment execution in a separate database session. Database URL and CORS origins are configurable with environment variables. The Angular API URL is configured in `frontend/src/environments/environment.ts`.

The architecture diagram is in `architecture-diagram.svg`.

## Components and domain model
- Angular UI: model/version registration, lifecycle actions, comparison, metrics, deployment submission, retry/rollback, filters, and event history.
- FastAPI API: typed request/response contracts, validation, lifecycle policy, correlation IDs, health/readiness, and operational metrics.
- SQLAlchemy persistence: `ModelRecord`, `ModelVersion`, `Deployment`, `VersionEvent`, and `DeploymentEvent`.
- Local async processing: background task advances a deployment through validation and simulated execution.
- Docker Compose: starts the API and UI locally.

## Key workflows
1. Register a model and one or more versions. New versions start `DRAFT` and `PENDING`.
2. Advance versions through `DRAFT -> VALIDATED -> APPROVED -> STAGING`; a successful production deployment moves the version to `PRODUCTION`. Archive is available from non-archived states when safety rules permit.
3. Each lifecycle transition stores an actor label, reason, timestamp, and correlation ID.
4. Request a deployment. The API checks model/version ownership, approval for production, idempotency, and conflicting active production promotion.
5. The API persists `REQUESTED` and schedules local background work. Deployment events record the status path, failure reason, retry, or rollback.
6. Angular polls deployment records, supports searching/filtering, and retrieves event history on demand.
7. A successful production deployment moves its version to `PRODUCTION`; rollback returns it to `STAGING`. Operators can compare two versions and inspect their persisted quality/performance metadata.

## Reliability and safety
The API rejects invalid lifecycle transitions and prevents production use of unapproved versions. Idempotency prevents repeated requests with the same key from creating a second deployment. Application-level conflict detection blocks a different production version while another version is active or successful. A successful production deployment must be rolled back before a different version can be promoted. These SQLite checks are not a substitute for robust multi-process locking or database constraints.

Tests use a temporary SQLite database and reset it for each test. The application database uses SQLAlchemy `create_all` at startup to create missing tables; this is documented schema initialization, not a versioned migration system.

## Security
Authentication, RBAC, tenant isolation, production secret management, and tamper-proof audit storage are not implemented. Lifecycle actors are labels supplied by the caller, not authenticated identities. Production requires identity-bound authorization, tenant scoping, network boundaries, secrets integration, and immutable audit retention.

## Observability
HTTP requests emit JSON log lines with method, path, status, duration, and correlation ID. `X-Request-ID` is accepted or generated and returned in the response; deployment and version audit records retain it. `/health` is liveness, `/ready` checks database connectivity, `/ops/metrics` returns lightweight registry/deployment counts, and model metrics are available via `/models/{id}/metrics`.

## Scaling and G12 design questions
These are future architecture decisions, not capabilities claimed for this local build.

1. **100 to 10,000 models:** PostgreSQL, indexes, pagination, object storage for artifacts, separate time-series storage for high-volume metrics, and horizontal scaling of stateless APIs/workers.
2. **Conflicting promotions:** enforce a unique active slot per `(tenant, model, environment)` and serialize promotion with row/advisory locks or compare-and-swap generations. Local detection is best-effort under concurrent multi-process writes.
3. **External success/database failure:** use a durable outbox/saga, idempotent runtime commands, reconciliation polling, and compensating rollback. The local simulator has no external deployment side effects.
4. **Multiple runtimes:** use a versioned runtime adapter interface for validation, deploy, health check, and rollback commands.
5. **Multi-tenancy:** add tenant keys to domain records and enforce tenant scope in all queries, object-storage paths, authorization, and tests. Not implemented locally.
6. **Large metric volumes:** separate time-series from metadata, partition by time/tenant/model as appropriate, apply retention and rollups, and serve summarized windows to the UI.
7. **Unsafe rollback:** keep immutable artifact references and prior deployment IDs, validate health/compatibility, make rollback idempotent, and audit actor/reason. Local rollback is allowed only for successful production records.
8. **Zero-downtime schema updates:** use expand/contract migrations, backward-compatible application versions, backfill, cut-over, then remove old schema in a later release. No Alembic migration chain is included.
9. **Angular isolation:** the UI consumes HTTP DTOs through one API service and never accesses ORM/database internals; policy is enforced by FastAPI.
10. **Team split:** backend owns domain/API/persistence; frontend owns operator experience; platform owns CI/runtime/observability; architecture lead owns policy, risks, and integration sequencing.

## Trade-offs
SQLite and process-local background tasks keep local setup small and cloud-independent, but neither provides multi-instance concurrency or durable job execution. The production path is PostgreSQL with versioned migrations and a persistent queue/worker. Azure is optional; equivalent cloud infrastructure can be chosen by deployment context.
