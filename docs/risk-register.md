# Risk register

| Risk | Impact | Likelihood | Mitigation |
| --- | --- | --- | --- |
| Unapproved production promotion | Production outage or governance breach | Medium | Gate deployment by approval_status and lifecycle_stage |
| Duplicate deployment requests | Repeated or conflicting workflows | Medium | Enforce idempotency_key + duplicate detection |
| Failed deployment rollback | Service instability | Medium | Expose rollback endpoint and record action in deployment state |
| Metric drift or quality degradation | Silent model quality risk | High | Monitor quality, drift, latency, and availability in metrics endpoint |
| SQLite scaling limits | Limited concurrency or throughput | Medium | Move to PostgreSQL with migration tooling in production |
| Incomplete operational visibility | Slow incident diagnosis | Medium | Add health checks, metrics, and structured logs |

## Review cadence
- Weekly during implementation
- Required before merge for lifecycle and rollback changes
- Reassessed when adding new deployment environments or model families
