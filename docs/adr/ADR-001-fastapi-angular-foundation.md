# ADR-001: Use FastAPI and Angular for the assignment platform

## Status
Accepted

## Context
The task requires a Python API and a browser-based operational interface with production-quality patterns, clean validation, and a testable architecture. The system also needs to support model lifecycle governance and monitoring surfaces.

## Decision
Use FastAPI for the backend and Angular for the frontend. This aligns with the assignment requirements and keeps the implementation straightforward, testable, and suitable for rapid iteration within the time box.

## Alternatives Considered
- Flask + vanilla JS: simpler but less aligned to typed API and UI constraints
- Django + template frontend: more opinionated and heavier for the required operational UI

## Consequences
### Positive
- Fast API development is quick and typed
- Angular provides a clean frontend structure for operational dashboards
- The separation supports maintainable domain boundaries

### Negative
- More moving parts than a monolithic app
- Requires separate packaging and operational coordination
