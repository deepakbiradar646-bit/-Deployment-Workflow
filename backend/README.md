# MLOps Backend

This FastAPI backend implements the model registry and deployment workflow for the MLOps Platform Technical Assignment.

## Features

- Model registration and versioning
- Approval and lifecycle checks
- Deployment requests with idempotency key support
- Retry and rollback operations
- Monitoring metrics endpoint
- SQLite persistence
- Automated pytest coverage for core workflows

## Run locally

```bash
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Health check

```bash
curl http://127.0.0.1:8000/health
```

## Tests

```bash
cd backend
python -m pytest -q
```
