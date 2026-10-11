# Test Strategy

## Unit Tests
- lifecycle validation rules
- production promotion constraints
- version uniqueness and duplicate request safety
- retry and rollback behavior

## API Tests
- happy path registry and version requests
- invalid production deployment attempts
- 404 and conflict handling
- duplicate deployment idempotency

## Integration Tests
- database-backed workflow from model creation to deployment
- metrics retrieval and monitoring state checks
- asynchronous deployment completion and persisted status checks
- simulated failure followed by retry to success
- rollback permitted only for a successful production deployment

## Angular Tests
- component creation and dashboard headings
- registration form and empty deployment state rendering
- three component-level tests for app creation, dashboard heading, and model registration/empty deployment state
- production build for template and type compilation

## End-to-End Scenario
Register model -> register version -> approve -> deploy -> view metrics -> roll back.

## CI, Coverage and Limitations
The repository includes a CI workflow for backend Pytest, Angular unit tests, and frontend production build. Backend tests use a temporary SQLite database and reset its tables per test, so they do not pollute the local demo database. The Angular component suite runs with test isolation disabled to avoid Vitest worker startup timeouts in this environment. Coverage remains focused on assignment workflows. Deployment execution is simulated through process-local background tasks; it does not contact a real model-serving runtime.
