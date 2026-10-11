# MLOps Platform Technical Assignment

## Model Registry and Deployment Workflow

## Role and scope

**Target:** G13 implementation scope, with G12 architecture, governance, and leadership artifacts.

This repository delivers the MLOps platform workflow in the technical assignment: model registration and versioning, approval-gated deployment requests, asynchronous deployment orchestration, monitoring metadata, retry and rollback rules, a Python API, an Angular operational dashboard, tests, packaging, and architecture documentation.

The implementation emphasizes production-quality engineering patterns across model governance, APIs, persistence, operational visibility, and deployment workflow.

## Problem statement

An industrial organization needs a governed view of machine-learning models used across plants and environments. Operators need to know what model versions exist, which version is approved, what deployment requests are in progress, whether a deployment failed, and what model-health metrics are reported.

The platform therefore provides:

1. A model registry with metadata and version records.
2. Audited lifecycle transitions and a production approval gate.
3. Deployment requests with idempotency, status events, retry, rollback, and conflict checks.
4. Monitoring metrics and lightweight operational counts.
5. An Angular dashboard for model/version operations, comparisons, health metrics, and deployment status/history.

## Architecture at a glance

```text
Browser
  Angular dashboard :4200
       | HTTP / JSON (local CORS)
       v
  FastAPI API :8000
       |-- Pydantic request/response validation
       |-- SQLAlchemy persistence
       |-- FastAPI BackgroundTasks deployment simulation
       v
  SQLite database (backend/app/mlops.db)
```

- **Frontend:** Angular standalone application. It calls the backend API, shows model and deployment data, displays health metrics, and polls deployment history every two seconds.
- **Backend:** FastAPI routes implement registry, version, deployment, retry, rollback, health, and metrics behavior.
- **Persistence:** SQLAlchemy models persist models, model versions, lifecycle events, deployment records, and deployment events in a local SQLite database.
- **Asynchronous execution:** The API persists a deployment request, returns its initial `REQUESTED` representation, and schedules a process-local background task to validate and simulate execution.
- **Observability:** request JSON logs include correlation IDs; `/health`, `/ready`, `/ops/metrics`, model metrics, and event-history APIs expose local operational state.
- **API documentation:** FastAPI provides interactive OpenAPI documentation at `/docs`.

The architecture diagram is in [docs/architecture-diagram.svg](docs/architecture-diagram.svg).

## Technology stack

| Area | Technology | Why it is used here |
|---|---|---|
| API | Python, FastAPI | Typed REST endpoints, validation, OpenAPI, and background tasks |
| Contracts | Pydantic | Request validation and response serialization |
| Persistence | SQLAlchemy, SQLite | Relational domain records with straightforward local setup |
| UI | Angular, TypeScript | Browser-based operational dashboard with typed API data |
| Tests | Pytest; Angular/Vitest | Isolated backend API/workflow tests and basic Angular component tests |
| Packaging | Docker, Docker Compose | Repeatable local container setup |
| CI | GitHub Actions | Backend test and frontend build checks |

SQLite provides lightweight local persistence, with the database URL configurable for other supported SQLAlchemy databases.

## Run locally on Windows

Run the backend and frontend in separate PowerShell terminals and keep both terminals open.

### 1. Backend API

From the project folder:

```powershell
Set-Location "C:\Users\Deepak\OneDrive\Desktop\ABB\MLOps_G12_G13_Technical_Assignment_Pack\backend"
& "C:\Users\Deepak\AppData\Local\Programs\Python\Python313\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If using a different Python environment, activate it and install dependencies first:

```powershell
python -m pip install -r requirements.txt
```

Confirm the backend is available:

- Health: http://127.0.0.1:8000/health
- Interactive API: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

### 2. Angular dashboard

Open another PowerShell terminal:

```powershell
Set-Location "C:\Users\Deepak\OneDrive\Desktop\ABB\MLOps_G12_G13_Technical_Assignment_Pack\frontend"
& "C:\Program Files\nodejs\npm.cmd" run start -- --host 127.0.0.1 --port 4200
```

Open http://127.0.0.1:4200. The frontend terminal must remain open while using the dashboard.

### Docker Compose

From the repository root, if Docker Desktop is installed and running:

```powershell
docker compose up --build
```

The Compose file starts the API and Angular frontend as a containerized application.

### Local configuration and schema setup

The backend reads `MLOPS_DATABASE_URL` and `MLOPS_CORS_ORIGINS` from its process environment. Defaults are the local SQLite file and Angular development origins. Set the database URL in the backend process before starting the API to use another supported SQLAlchemy database. SQLAlchemy initializes the application schema at startup. The Angular API base URL is configured in `frontend/src/environments/environment.ts`.

## End-to-end demo: register, deploy, inspect

Use http://127.0.0.1:8000/docs to execute each request and copy returned IDs into later requests.

### Step 1 — Register a model

Call `POST /models`:

```json
{
  "name": "plant-quality-demo",
  "description": "Demo model for quality outcomes",
  "framework": "scikit-learn",
  "algorithm": "RandomForest",
  "owner": "ml-platform",
  "tags": "demo,quality"
}
```

The API returns the model record, including its generated `id`.

### Step 2 — Register a version (starts unapproved)

Call `POST /models/{model_id}/versions` using the returned model ID:

```json
{
  "version": "1.0.0",
  "artifact_uri": "file:///models/plant-quality-demo/1.0.0/model.pkl",
  "training_data_ref": "quality.dataset.v1",
  "quality_score": 0.94,
  "drift_score": 0.04,
  "latency_ms": 85,
  "throughput_rps": 120,
  "error_rate": 0.01,
  "availability": 0.99,
  "monitoring_status": "HEALTHY"
}
```

The API returns a version record and its generated `id`. Every new version starts in `DRAFT` with `PENDING` approval. Advance it using `POST /models/{model_id}/versions/{version_id}/transition`, in order:

```json
{"target_stage": "VALIDATED", "reason": "Validation checks passed", "actor": "reviewer"}
{"target_stage": "APPROVED", "reason": "Approved for controlled promotion", "actor": "approver"}
```

Continue to `STAGING` using the transition endpoint. A version enters `PRODUCTION` only when its production deployment succeeds; the API records that transition automatically. Lifecycle changes are recorded at `GET /models/{model_id}/versions/{version_id}/events`. The actor is a local label, not an authenticated identity.

### Step 3 — Submit a production deployment

Call `POST /deployments`:

```json
{
  "model_id": 1,
  "model_version_id": 1,
  "environment": "PRODUCTION",
  "request_reason": "Assignment demo deployment",
  "idempotency_key": "plant-quality-demo-1.0.0-production"
}
```

Replace the example IDs with the actual IDs returned in Steps 1 and 2. A valid request returns HTTP `201` with a deployment record initially marked `REQUESTED`. The backend then runs a local asynchronous simulation that records `VALIDATING`, `DEPLOYING`, and `SUCCEEDED`.

### Step 4 — Verify the deployment and its event history

- Query `GET /deployments/{deployment_id}` or `GET /deployments` in `/docs`.
- Query `GET /deployments/{deployment_id}/events` to inspect status transitions and correlation IDs.
- A successful production deployment moves the version lifecycle to `PRODUCTION`; rolling it back returns the version to `STAGING`.
- The Angular dashboard displays the deployment under **Deployment timeline**, polls the API, and provides a History action.
- A production request using a version not marked `APPROVED` is rejected with HTTP `400`.
- A different production version is blocked while another version is active/successful until rollback. Repeating the same idempotency key returns the existing record.

### Step 5 — Exercise failure and retry

For the first deployment request, optionally include:

```json
"simulate_failure": true
```

This is a test/demo switch: the local worker marks the deployment `FAILED`. Use the dashboard Retry action or call `POST /deployments/{deployment_id}/retry`; the retry is processed and the simulation then succeeds. Inspect the record and its event history again.

### Step 6 — Exercise rollback

Use the dashboard Rollback action or call `POST /deployments/{deployment_id}/rollback` for a `SUCCEEDED` deployment in the `PRODUCTION` environment. The record becomes `ROLLED_BACK`. The API rejects rollback of a non-production or unsuccessful deployment.

## How the assignment was approached and implemented

The implementation followed the assignment's preference for a complete vertical slice: first make the core model-to-deployment workflow work end to end, then add governance, observability, frontend workflow coverage, tests, and delivery documentation.

### Step 1 — Turn the brief into an end-to-end workflow

The mandatory requirements and acceptance scenarios were translated into this operator flow:

`Register model -> register versions -> validate and approve a version -> promote to staging -> request deployment -> inspect status and metrics -> retry or roll back when appropriate`

This kept implementation focused on the required MLOps platform behaviors rather than adding unrelated model-training functionality.

### Step 2 — Define the domain and API boundaries

The domain was represented with five persistent record types:

- `ModelRecord`: model identity and metadata (name, framework, algorithm, owner, tags).
- `ModelVersion`: artifact and training-data references, approval/lifecycle fields, and metric values.
- `Deployment`: target environment, requested version, status/reason, retries, idempotency key, timestamps, and rollback flag.
- `VersionEvent`: lifecycle changes with actor label, reason, timestamp, and correlation ID.
- `DeploymentEvent`: append-only deployment status and operator-action history with correlation ID.

FastAPI endpoints expose these resources, Pydantic schemas validate requests and responses, and SQLAlchemy maps the records to SQLite. The API is the policy boundary: the Angular client can request an action, but the backend decides whether that action is allowed.

### Step 3 — Implement registry and lifecycle governance

The registry supports model and version creation and listing, with duplicate checks. A new version starts as `DRAFT/PENDING`; explicit lifecycle transitions record the actor label, reason, and correlation information. Production deployment is rejected unless the version is approved. The version moves to `PRODUCTION` only after a successful production deployment, and rollback returns it to `STAGING`.

### Step 4 — Implement deployment workflow and persistence

The API checks model/version ownership, production approval, idempotency, and conflicting active production deployments before storing a request. FastAPI `BackgroundTasks` processes the validation and deployment stages. Each state change is persisted, allowing status inspection, retry of simulated failures, and rollback of a successful production deployment.

### Step 5 — Add monitoring and operational visibility

Version records hold monitoring metadata for quality, drift, latency, throughput, error rate, availability, and monitoring state. Health/readiness endpoints, lightweight operational counts, request logs with correlation IDs, and version/deployment event APIs make the local workflow inspectable. These are assignment-scale indicators, not live production inference telemetry.

### Step 6 — Build the Angular operator interface

The dashboard consumes the REST API through an Angular service. It provides model and version forms, lifecycle actions, version comparison, metrics, deployment submission, retry/rollback, filters, and event history. Loading, empty, and API-error states are shown instead of fabricating sample API responses.

### Step 7 — Validate behavior and package the result

Pytest checks the backend API and workflow rules using temporary SQLite storage. Angular component tests and a production build check the UI. Docker/Compose, environment configuration, and GitHub Actions support repeatable setup and automated checks. The README and G12 documents explain decisions, operational risks, and architecture.

## Frontend: what to show and explain

The main dashboard implementation is in `frontend/src/app/app.ts`, `app.html`, `app.css`, and `mlops.service.ts`.

| Frontend area | Objective | Current implementation |
|---|---|---|
| API connectivity indicator | Tell the operator whether live backend data is available | Shows `API online` or `API unavailable` |
| Overview cards | Give a quick portfolio/deployment/health summary | Model count, deployment count, selected-model quality and availability |
| Model inventory | Find and inspect a model | Loads API models, supports text search, and selects a model |
| Model registration | Add registry entries | Form calls `POST /models` |
| Version lifecycle | Register, approve, promote, or archive versions | Form creates a `DRAFT/PENDING` version; controls follow allowed transitions and display audit events. Production stage follows successful production deployment. |
| Version comparison | Compare versions before promotion | Select two versions and compare quality, drift, latency, throughput, and related metadata |
| Monitoring metrics | Surface operational health | Displays latency, throughput, drift, error rate, quality, availability, monitoring state, and inference timestamp |
| Deployment timeline | Make workflow status visible and actionable | Shows model, version, environment, status, retries, reason, and update time; supports search/filter, history, retry, and rollback |
| Deployment request | Submit a deployment without leaving the dashboard | Select version/environment, provide reason, optionally simulate failure; backend enforces approval and conflict rules |
| Loading/empty/error states | Avoid ambiguous blank screens | Loading state, no-model/no-deployment messages, API status, and visible API error messages |
| Responsive layout | Keep the dashboard usable across screen widths | CSS grid and flexible layout styling |

The frontend supports the assignment operator workflows, with approval actions and event histories connected to the backend APIs.

## Assignment files 01–09: objectives and how this repo addresses them

The numbered files are the assignment specification, expectations, templates, and submission guidance. They are not nine application modules. The sections below map each one to the repository work and give an interview-friendly explanation.

### 01 — Assignment brief

**Objective:** Build a representative MLOps application covering registry, versioning, approval, deployment tracking, monitoring, retry/rollback, and Angular views. The brief favors a complete vertical slice over sophisticated model training.

**Implementation:** FastAPI endpoints and SQLAlchemy entities provide the registry and workflow. SQLite persists state. The Angular dashboard reads model, deployment, and metric data. Pytest exercises the major API workflows.

**Challenge and response:** The solution focuses on the control-plane behaviors requested by the brief: policy validation, idempotent requests, persisted deployment states, and operator visibility. FastAPI background tasks advance deployment requests through the local orchestration workflow.

**Interview explanation:** “I treated deployment as a governed control-plane workflow. I implemented request validation, status tracking, retry, rollback, and monitoring surfaces around the model registry.”

### 02 — G12 expectations

**Objective:** Demonstrate architecture and leadership judgment in addition to code: async processing, scale approach, governance, observability, risks, ADRs, and team delivery.

**Implementation:** The repository includes an asynchronous local deployment simulation plus architecture, ADR, delivery plan, risk register, roadmap, review checklist, and production-readiness checklist.

**Challenge and response:** G12 asks for production-oriented reasoning alongside implementation. The docs explain scale, persistence, asynchronous processing, and deployment trade-offs. FastAPI `BackgroundTasks` demonstrates the asynchronous workflow, and the architecture describes a queue-and-worker pattern for scaled operation.

**Interview explanation:** “I implemented an asynchronous workflow that separates accepting a deployment request from processing it. I documented how the queue-and-worker architecture can scale this pattern.”

**Implemented governance and operations:** Lifecycle/deployment audit events, request correlation, structured request logs, database readiness, operational counts, and production approval checks support the workflow. The architecture documentation describes identity, tenancy, concurrency, and runtime integration patterns.

### 03 — G13 expectations

**Objective:** Deliver a working vertical slice across backend, Angular, persistence, tests, packaging, and documentation.

**Implementation:** The core API, database records, deployment status workflow, dashboard, Docker files, CI workflow, tests, README, and architecture diagram are present.

**Challenge and response:** The important boundary was keeping the frontend a client of stable API contracts rather than duplicating domain rules. The production approval gate is enforced by the backend, and Pydantic schemas validate API inputs.

**Interview explanation:** “The backend owns business rules and persistence. Angular consumes typed API data and focuses on operator visibility, so the browser is not the authority for deployment policy.”

### 04 — GitHub submission guidelines

**Objective:** Make the work straightforward to inspect, run, test, and evaluate; include setup, documentation, CI, packaging, and a sample workflow.

**Implementation:** The repo includes setup commands, FastAPI OpenAPI docs, Docker Compose, CI, architecture documentation, and workflow instructions.

**Challenge and response:** Docker Compose and SQLite provide a straightforward local setup for evaluation.

**Interview explanation:** “I optimized for reproducibility: run the API and UI locally, use `/docs` to exercise the workflow, run Pytest, and build the Angular app.”

**Submission preparation:** Include the repository link, screenshots, candidate details, and effort summary requested by the submission process.

### 05 — Evaluation scorecard

**Objective:** Clarify what reviewers assess: architecture, backend, MLOps behavior, frontend, testing, packaging, and (for G12) leadership.

**Implementation:** The code and docs map to these areas: domain/API behavior, Angular dashboard, tests, packaging/CI, ADRs, risk register, and roadmap.

**Challenge and response:** A scorecard rewards both behavior and engineering quality. The README maps implemented workflows and engineering artifacts to the evaluation areas.

**Interview explanation:** “I used the scorecard as a coverage checklist and prioritized a working end-to-end path over building many disconnected features.”

### 06 — Architecture template

**Objective:** Explain system context, scope, components, data model, workflows, reliability, security, observability, scaling, and trade-offs.

**Implementation:** `docs/architecture.md` and `docs/architecture-diagram.svg` describe the layers, domain records, workflows, persistence, trade-offs, and scaling strategy.

**Challenge and response:** The architecture diagram and template describe runtime, queue, and authentication boundaries as part of the system design.

**Interview explanation:** “I separated the operator UI, API/business rules, and persistence. I chose SQLite for local evaluation and documented PostgreSQL plus durable workers as the production path.”

### 07 — Test strategy template

**Objective:** Define unit/API/integration/UI coverage, an end-to-end scenario, CI, and coverage.

**Implementation:** `docs/test-strategy.md` and `backend/tests/test_api.py` cover API behavior, persistence-backed workflows, approval gating, idempotency, simulated failure/retry, and rollback. Angular has component tests and a production build check.

**Challenge and response:** Tests should verify observable outcomes, not just that endpoints return without crashing. The backend tests assert returned statuses, IDs, gates, and retry/rollback effects.

**Interview explanation:** “I test policy and workflow outcomes at the API boundary, including failure paths. The dashboard is production-build checked and has a basic component test suite.”

### 08 — ADR template

**Objective:** Record significant decisions with context, alternatives, and consequences so reviewers can understand why the design took its current form.

**Implementation:** `docs/adr/ADR-001-fastapi-angular-foundation.md` captures the stack choice. `docs/adr/ADR-002-async-deployment-workflow.md` records the decision to use FastAPI background tasks for the assignment workflow.

**Challenge and response:** A decision record captures context, alternatives, and consequences. The async ADR explains the background-task decision and the queue-and-worker scaling pattern.

**Interview explanation:** “I document decisions that materially affect maintainability and operation, including alternatives and operational trade-offs.”

### 09 — Submission email template

**Objective:** Provide a concise handoff containing role level, repository, architecture summary, run/test commands, demo location, project scope, and effort.

**Implementation:** `09_submission_email_template.md` is the supplied template; this README provides reusable project facts for filling it in.

**Challenge and response:** Submission communication should let evaluators get to the repository and run the demo quickly. The supplied template organizes the repository URL, candidate details, project summary, and effort in one handoff.

**Interview explanation:** “I would send the reviewer a concise handoff with the exact run and test commands, a demo path, and a clear summary of the implemented workflows.”

## Testing and CI

Run backend tests:

```powershell
Set-Location "C:\Users\Deepak\OneDrive\Desktop\ABB\MLOps_G12_G13_Technical_Assignment_Pack\backend"
& "C:\Users\Deepak\AppData\Local\Programs\Python\Python313\python.exe" -m pytest -q
```

Build the frontend:

```powershell
Set-Location "C:\Users\Deepak\OneDrive\Desktop\ABB\MLOps_G12_G13_Technical_Assignment_Pack\frontend"
& "C:\Program Files\nodejs\npm.cmd" run build
```

The GitHub Actions workflow runs backend Pytest, Angular unit tests, and an Angular production build. Backend tests use a temporary SQLite database. The Angular component suite passes locally when test isolation is disabled.

On Windows, the Vitest worker can time out when launched in isolation. The CI and local command below disable test isolation to run the current component suite reliably:

```powershell
Set-Location "C:\Users\Deepak\OneDrive\Desktop\ABB\MLOps_G12_G13_Technical_Assignment_Pack\frontend"
& "C:\Program Files\nodejs\npm.cmd" test -- --watch=false --isolate=false
```

## API reference

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Service health response |
| `GET` | `/ready` | Database readiness response |
| `GET` | `/ops/metrics` | Lightweight counts by deployment status |
| `POST` | `/models` | Register a model |
| `GET` | `/models` | List models |
| `GET` | `/models/{model_id}` | Read a model |
| `POST` | `/models/{model_id}/versions` | Register a version in `DRAFT/PENDING` with metric metadata |
| `GET` | `/models/{model_id}/versions` | List a model's versions |
| `POST` | `/models/{model_id}/versions/{version_id}/transition` | Advance lifecycle state |
| `GET` | `/models/{model_id}/versions/{version_id}/events` | Read version approval/lifecycle audit |
| `GET` | `/models/{model_id}/versions/compare` | Compare two versions' metadata and metrics |
| `POST` | `/deployments` | Request an environment deployment |
| `GET` | `/deployments` | List deployment history |
| `GET` | `/deployments/{deployment_id}` | Read one deployment status |
| `GET` | `/deployments/{deployment_id}/events` | Read deployment status/audit history |
| `POST` | `/deployments/{deployment_id}/retry` | Retry a failed deployment |
| `POST` | `/deployments/{deployment_id}/rollback` | Roll back a successful production deployment |
| `GET` | `/models/{model_id}/metrics` | Read latest-version monitoring metadata |

OpenAPI documentation is generated from the FastAPI schemas and available at `http://127.0.0.1:8000/docs`.

## Interview-ready project summary

> “I implemented an MLOps control plane with a FastAPI/SQLAlchemy backend and an Angular operator dashboard. It manages model registration, versions, approval metadata, deployment requests, monitoring metrics, and audit events. The API enforces production approval and idempotency, then processes deployment requests through an asynchronous workflow with status tracking, failure/retry, and rollback. The dashboard consumes the API and displays model health and deployment history. SQLite and FastAPI background tasks keep the application straightforward to run locally, while the architecture documents the system boundaries and scaling strategy.”

## Documentation map

- [docs/architecture.md](docs/architecture.md)
- [docs/test-strategy.md](docs/test-strategy.md)
- [docs/delivery-plan.md](docs/delivery-plan.md)
- [docs/risk-register.md](docs/risk-register.md)
- [docs/roadmap.md](docs/roadmap.md)
- [docs/code-review-checklist.md](docs/code-review-checklist.md)
- [docs/production-readiness-checklist.md](docs/production-readiness-checklist.md)
- [docs/adr/ADR-001-fastapi-angular-foundation.md](docs/adr/ADR-001-fastapi-angular-foundation.md)
- [docs/adr/ADR-002-async-deployment-workflow.md](docs/adr/ADR-002-async-deployment-workflow.md)
