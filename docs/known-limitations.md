# Known Limitations

- Local SQLite is used instead of a distributed transactional database.
- Authentication/RBAC and production secret management are not implemented. Version and deployment event histories are persisted, but there is no tamper-proof audit store or authenticated identity; lifecycle events use a caller-provided actor label.
- Deployment execution is a local simulation using process-bound FastAPI background tasks; it does not deploy a model to an external serving runtime and queued work is not durable across restarts.
- SQLite is the tested local database. `create_all` initializes missing tables but is not a versioned migration system.
- Concurrent-promotion protection is an application-level check and is not safe against all multi-process races; use database locking/constraints with a production database.
- Operational metrics are local record counts, not Prometheus instrumentation or inference telemetry.
