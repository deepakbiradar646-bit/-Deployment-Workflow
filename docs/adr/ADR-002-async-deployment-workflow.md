# ADR-002: Use asynchronous deployment handling in the design

## Status
Accepted

## Context
Model deployment and validation workflows can take longer than a simple request/response cycle. The assignment explicitly expects an asynchronous style workflow for at least one long-running domain process.

## Decision
The API persists each valid deployment request and schedules its validation/execution using FastAPI `BackgroundTasks`. The local workflow records `VALIDATING` and `DEPLOYING`, then reaches `SUCCEEDED` or `FAILED`. A request option can simulate failure for acceptance testing; a retry of a failed request executes again. Rollback is allowed only for a successful production deployment.

This process-local implementation is intentionally suitable for the assignment and local evaluation. It is not durable across application restarts and is not a substitute for a production queue.

## Alternatives Considered
- Fully synchronous deployment processing in the request handler
- A broker and separately deployed worker service, which would add infrastructure beyond the assignment's local scope

## Consequences
### Positive
- The API returns the persisted `REQUESTED` record while work proceeds after the response
- Status can be read from the API and polled by the dashboard
- Aligns with G12 expectations for operational design

### Negative
- Work can be lost if the process stops before background execution completes
- A production deployment should move the job to a durable queue and worker
