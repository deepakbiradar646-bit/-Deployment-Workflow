# Production-readiness checklist

## Functional readiness
- model registration and versioning complete
- approval and promotion gates enforced
- deployment retry and rollback paths tested
- monitoring endpoints and operational visibility present

## Reliability
- idempotency for repeated requests
- error handling for invalid transitions and missing resources
- health and readability checks in place
- rollback path validated for production operations

## Security and governance
- RBAC and environment policy controls planned or in place
- secret management strategy documented
- audit trail and approval records captured where required

## Delivery and operations
- CI validation for Python and Angular
- Docker packaging and local orchestration working
- infrastructure, deployment, and rollback runbooks documented
- logs and metrics available for incident management
