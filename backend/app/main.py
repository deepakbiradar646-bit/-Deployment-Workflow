from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine, get_db
from .models import Deployment, DeploymentEvent, ModelRecord, ModelVersion, VersionEvent
from .schemas import (
    DeploymentCreate,
    DeploymentEventOut,
    DeploymentOut,
    HealthOut,
    MetricsOut,
    ModelCreate,
    ModelOut,
    ModelVersionComparison,
    ModelVersionCreate,
    ModelVersionOut,
    OpsMetricsOut,
    VersionTransition,
    VersionEventOut,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="MLOps Platform API", version="0.1.0", lifespan=lifespan)
cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "MLOPS_CORS_ORIGINS",
        "http://127.0.0.1:4200,http://localhost:4200",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_LIFECYCLE_STAGES = {"DRAFT", "VALIDATED", "APPROVED", "STAGING", "PRODUCTION", "ARCHIVED"}
LIFECYCLE_TRANSITIONS = {
    "DRAFT": {"VALIDATED", "ARCHIVED"},
    "VALIDATED": {"APPROVED", "ARCHIVED"},
    "APPROVED": {"STAGING", "ARCHIVED"},
    "STAGING": {"PRODUCTION", "ARCHIVED"},
    "PRODUCTION": {"ARCHIVED"},
    "ARCHIVED": set(),
}


@app.middleware("http")
async def add_request_correlation(request: Request, call_next):
    correlation_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.correlation_id = correlation_id
    started_at = datetime.now(timezone.utc)
    response = await call_next(request)
    response.headers["X-Request-ID"] = correlation_id
    logging.getLogger("mlops.api").info(
        json.dumps(
            {
                "event": "http_request",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "correlation_id": correlation_id,
                "duration_ms": (datetime.now(timezone.utc) - started_at).total_seconds() * 1000,
            }
        )
    )
    return response


def get_model_or_404(db: Session, model_id: int) -> ModelRecord:
    model = db.get(ModelRecord, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    return model


def get_version_or_404(db: Session, version_id: int) -> ModelVersion:
    version = db.get(ModelVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail=f"Model version {version_id} not found")
    return version


def get_deployment_or_404(db: Session, deployment_id: int) -> Deployment:
    deployment = db.get(Deployment, deployment_id)
    if deployment is None:
        raise HTTPException(status_code=404, detail=f"Deployment {deployment_id} not found")
    return deployment


def record_deployment_transition(
    db: Session,
    deployment: Deployment,
    to_status: str,
    reason: str,
    event_type: str,
    correlation_id: str | None,
) -> None:
    from_status = deployment.status
    deployment.status = to_status
    deployment.status_reason = reason
    deployment.updated_at = datetime.now(timezone.utc)
    db.add(
        DeploymentEvent(
            deployment_id=deployment.id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            correlation_id=correlation_id,
        )
    )
    db.commit()


def process_deployment(
    deployment_id: int,
    simulate_failure: bool = False,
    correlation_id: str | None = None,
) -> None:
    with SessionLocal() as db:
        deployment = db.get(Deployment, deployment_id)
        if deployment is None or deployment.status != "REQUESTED":
            return

        record_deployment_transition(
            db, deployment, "VALIDATING", "Validating model version and target environment",
            "VALIDATION_STARTED", correlation_id,
        )

        if simulate_failure:
            record_deployment_transition(
                db, deployment, "FAILED", "Simulated deployment failure", "DEPLOYMENT_FAILED", correlation_id
            )
            return

        record_deployment_transition(
            db, deployment, "DEPLOYING", "Deployment validation passed", "DEPLOYMENT_STARTED", correlation_id
        )
        record_deployment_transition(
            db, deployment, "SUCCEEDED", "Deployment completed successfully", "DEPLOYMENT_SUCCEEDED", correlation_id
        )
        version = db.get(ModelVersion, deployment.model_version_id)
        if deployment.environment == "PRODUCTION" and version is not None and version.lifecycle_stage != "PRODUCTION":
            from_stage = version.lifecycle_stage
            version.lifecycle_stage = "PRODUCTION"
            db.add(
                VersionEvent(
                    model_version_id=version.id,
                    event_type="PRODUCTION_DEPLOYMENT_SUCCEEDED",
                    from_stage=from_stage,
                    to_stage="PRODUCTION",
                    actor="deployment-worker",
                    reason=f"Deployment {deployment.id} succeeded",
                    correlation_id=correlation_id,
                )
            )
            db.commit()


Base.metadata.create_all(bind=engine)


@app.get("/health", response_model=HealthOut)
def healthcheck() -> HealthOut:
    return HealthOut(status="healthy", service="mlops-platform", database=database_kind())


def database_kind() -> str:
    return "sqlite" if engine.url.get_backend_name() == "sqlite" else engine.url.get_backend_name()


@app.get("/ready", response_model=HealthOut)
def readiness(db: Session = Depends(get_db)) -> HealthOut:
    db.execute(text("SELECT 1"))
    return HealthOut(status="ready", service="mlops-platform", database=database_kind())


@app.get("/ops/metrics", response_model=OpsMetricsOut)
def operational_metrics(db: Session = Depends(get_db)) -> OpsMetricsOut:
    status_rows = db.execute(
        select(Deployment.status, func.count(Deployment.id)).group_by(Deployment.status)
    ).all()
    deployments_by_status = {deployment_status: count for deployment_status, count in status_rows}
    return OpsMetricsOut(
        model_count=db.scalar(select(func.count(ModelRecord.id))) or 0,
        version_count=db.scalar(select(func.count(ModelVersion.id))) or 0,
        deployment_count=db.scalar(select(func.count(Deployment.id))) or 0,
        failed_deployment_count=deployments_by_status.get("FAILED", 0),
        deployments_by_status=deployments_by_status,
    )


@app.post("/models", response_model=ModelOut, status_code=status.HTTP_201_CREATED)
def create_model(payload: ModelCreate, db: Session = Depends(get_db)) -> ModelOut:
    existing = db.execute(select(ModelRecord).where(ModelRecord.name == payload.name)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Model name already exists")

    model = ModelRecord(
        name=payload.name,
        description=payload.description,
        framework=payload.framework,
        algorithm=payload.algorithm,
        owner=payload.owner,
        tags=payload.tags,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


@app.get("/models", response_model=list[ModelOut])
def list_models(db: Session = Depends(get_db)) -> list[ModelOut]:
    models = db.execute(select(ModelRecord).order_by(ModelRecord.created_at.desc())).scalars().all()
    return models


@app.get("/models/{model_id}", response_model=ModelOut)
def get_model(model_id: int, db: Session = Depends(get_db)) -> ModelOut:
    model = get_model_or_404(db, model_id)
    return model


@app.post("/models/{model_id}/versions", response_model=ModelVersionOut, status_code=status.HTTP_201_CREATED)
def create_model_version(
    model_id: int,
    payload: ModelVersionCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> ModelVersionOut:
    model = get_model_or_404(db, model_id)
    version_exists = db.execute(
        select(ModelVersion).where(ModelVersion.model_id == model_id, ModelVersion.version == payload.version)
    ).scalar_one_or_none()
    if version_exists is not None:
        raise HTTPException(status_code=409, detail="Version already exists for this model")

    version = ModelVersion(
        model_id=model.id,
        version=payload.version,
        artifact_uri=payload.artifact_uri,
        training_data_ref=payload.training_data_ref,
        approval_status="PENDING",
        lifecycle_stage="DRAFT",
        quality_score=payload.quality_score,
        drift_score=payload.drift_score,
        latency_ms=payload.latency_ms,
        throughput_rps=payload.throughput_rps,
        error_rate=payload.error_rate,
        availability=payload.availability,
        monitoring_status=payload.monitoring_status,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    db.add(
        VersionEvent(
            model_version_id=version.id,
            event_type="VERSION_REGISTERED",
            from_stage=None,
            to_stage="DRAFT",
            actor="registry",
            reason="Model version registered",
            correlation_id=request.state.correlation_id,
        )
    )
    db.commit()
    return version


@app.get("/models/{model_id}/versions", response_model=list[ModelVersionOut])
def list_model_versions(model_id: int, db: Session = Depends(get_db)) -> list[ModelVersionOut]:
    get_model_or_404(db, model_id)
    versions = db.execute(
        select(ModelVersion).where(ModelVersion.model_id == model_id).order_by(ModelVersion.created_at.desc())
    ).scalars().all()
    return versions


@app.post(
    "/models/{model_id}/versions/{version_id}/transition",
    response_model=ModelVersionOut,
)
def transition_model_version(
    model_id: int,
    version_id: int,
    payload: VersionTransition,
    request: Request,
    db: Session = Depends(get_db),
) -> ModelVersionOut:
    get_model_or_404(db, model_id)
    version = get_version_or_404(db, version_id)
    if version.model_id != model_id:
        raise HTTPException(status_code=400, detail="Version does not belong to the selected model")
    if payload.target_stage not in ALLOWED_LIFECYCLE_STAGES:
        raise HTTPException(status_code=400, detail=f"target_stage must be one of {sorted(ALLOWED_LIFECYCLE_STAGES)}")
    if payload.target_stage not in LIFECYCLE_TRANSITIONS[version.lifecycle_stage]:
        raise HTTPException(
            status_code=409,
            detail=f"Lifecycle transition from {version.lifecycle_stage} to {payload.target_stage} is not allowed",
        )
    if payload.target_stage == "PRODUCTION":
        succeeded = db.execute(
            select(Deployment).where(
                Deployment.model_version_id == version.id,
                Deployment.environment == "PRODUCTION",
                Deployment.status == "SUCCEEDED",
            )
        ).scalars().first()
        if succeeded is None:
            raise HTTPException(
                status_code=409,
                detail="A version can enter PRODUCTION only after a successful production deployment",
            )
    if payload.target_stage == "ARCHIVED":
        active_production = db.execute(
            select(Deployment).where(
                Deployment.model_version_id == version.id,
                Deployment.environment == "PRODUCTION",
                Deployment.status == "SUCCEEDED",
            )
        ).scalars().first()
        if active_production is not None:
            raise HTTPException(status_code=409, detail="Roll back the active production deployment before archiving")

    from_stage = version.lifecycle_stage
    version.lifecycle_stage = payload.target_stage
    if payload.target_stage == "APPROVED":
        version.approval_status = "APPROVED"
    db.add(
        VersionEvent(
            model_version_id=version.id,
            event_type="VERSION_APPROVED" if payload.target_stage == "APPROVED" else "LIFECYCLE_TRANSITION",
            from_stage=from_stage,
            to_stage=payload.target_stage,
            actor=payload.actor,
            reason=payload.reason,
            correlation_id=request.state.correlation_id,
        )
    )
    db.commit()
    db.refresh(version)
    return version


@app.get(
    "/models/{model_id}/versions/{version_id}/events",
    response_model=list[VersionEventOut],
)
def list_version_events(
    model_id: int,
    version_id: int,
    db: Session = Depends(get_db),
) -> list[VersionEventOut]:
    get_model_or_404(db, model_id)
    version = get_version_or_404(db, version_id)
    if version.model_id != model_id:
        raise HTTPException(status_code=400, detail="Version does not belong to the selected model")
    return list(
        db.execute(
            select(VersionEvent)
            .where(VersionEvent.model_version_id == version_id)
            .order_by(VersionEvent.created_at, VersionEvent.id)
        ).scalars().all()
    )


@app.get("/models/{model_id}/versions/compare", response_model=ModelVersionComparison)
def compare_model_versions(
    model_id: int,
    first_version_id: int,
    second_version_id: int,
    db: Session = Depends(get_db),
) -> ModelVersionComparison:
    get_model_or_404(db, model_id)
    first = get_version_or_404(db, first_version_id)
    second = get_version_or_404(db, second_version_id)
    if first.model_id != model_id or second.model_id != model_id:
        raise HTTPException(status_code=400, detail="Both versions must belong to the selected model")
    if first.id == second.id:
        raise HTTPException(status_code=400, detail="Choose two different versions to compare")
    return ModelVersionComparison(first=first, second=second)


@app.post("/deployments", response_model=DeploymentOut, status_code=status.HTTP_201_CREATED)
def create_deployment(
    payload: DeploymentCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
) -> DeploymentOut:
    model = get_model_or_404(db, payload.model_id)
    version = get_version_or_404(db, payload.model_version_id)

    if version.model_id != model.id:
        raise HTTPException(status_code=400, detail="Version does not belong to the selected model")
    if payload.environment == "PRODUCTION" and version.approval_status != "APPROVED":
        raise HTTPException(status_code=400, detail="Production deployment requires an approved model version")

    if payload.idempotency_key:
        duplicate = db.execute(
            select(Deployment).where(Deployment.idempotency_key == payload.idempotency_key)
        ).scalar_one_or_none()
        if duplicate is not None:
            return duplicate

    if payload.environment == "PRODUCTION":
        active_production = db.execute(
            select(Deployment).where(
                Deployment.model_id == model.id,
                Deployment.environment == "PRODUCTION",
                Deployment.status.in_(("REQUESTED", "VALIDATING", "DEPLOYING", "SUCCEEDED")),
                Deployment.model_version_id != version.id,
            )
        ).scalars().first()
        if active_production is not None:
            raise HTTPException(
                status_code=409,
                detail="Another production version is active; roll it back before promoting a different version",
            )

    deployment = Deployment(
        model_id=model.id,
        model_version_id=version.id,
        environment=payload.environment,
        status="REQUESTED",
        request_reason=payload.request_reason,
        idempotency_key=payload.idempotency_key,
        status_reason="Deployment requested",
    )
    db.add(deployment)
    db.commit()
    db.refresh(deployment)
    db.add(
        DeploymentEvent(
            deployment_id=deployment.id,
            event_type="DEPLOYMENT_REQUESTED",
            from_status=None,
            to_status="REQUESTED",
            reason="Deployment request accepted",
            correlation_id=request.state.correlation_id,
        )
    )
    db.commit()
    background_tasks.add_task(
        process_deployment, deployment.id, payload.simulate_failure, request.state.correlation_id
    )
    return deployment


@app.get("/deployments", response_model=list[DeploymentOut])
def list_deployments(db: Session = Depends(get_db)) -> list[DeploymentOut]:
    deployments = db.execute(select(Deployment).order_by(Deployment.requested_at.desc())).scalars().all()
    return deployments


@app.get("/deployments/{deployment_id}", response_model=DeploymentOut)
def get_deployment(deployment_id: int, db: Session = Depends(get_db)) -> DeploymentOut:
    deployment = get_deployment_or_404(db, deployment_id)
    return deployment


@app.get("/deployments/{deployment_id}/events", response_model=list[DeploymentEventOut])
def list_deployment_events(deployment_id: int, db: Session = Depends(get_db)) -> list[DeploymentEventOut]:
    get_deployment_or_404(db, deployment_id)
    return list(
        db.execute(
            select(DeploymentEvent)
            .where(DeploymentEvent.deployment_id == deployment_id)
            .order_by(DeploymentEvent.created_at, DeploymentEvent.id)
        ).scalars().all()
    )


@app.post("/deployments/{deployment_id}/retry", response_model=DeploymentOut)
def retry_deployment(
    deployment_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
) -> DeploymentOut:
    deployment = get_deployment_or_404(db, deployment_id)
    if deployment.status != "FAILED":
        raise HTTPException(status_code=409, detail="Only failed deployments can be retried")
    deployment.retry_count += 1
    record_deployment_transition(
        db, deployment, "REQUESTED", "Retry requested by operator", "RETRY_REQUESTED",
        request.state.correlation_id,
    )
    db.refresh(deployment)
    background_tasks.add_task(process_deployment, deployment.id, False, request.state.correlation_id)
    return deployment


@app.post("/deployments/{deployment_id}/rollback", response_model=DeploymentOut)
def rollback_deployment(
    deployment_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> DeploymentOut:
    deployment = get_deployment_or_404(db, deployment_id)
    if deployment.environment != "PRODUCTION" or deployment.status != "SUCCEEDED":
        raise HTTPException(status_code=409, detail="Only successful production deployments can be rolled back")
    deployment.rolled_back = True
    record_deployment_transition(
        db, deployment, "ROLLED_BACK", "Rollback completed", "DEPLOYMENT_ROLLED_BACK",
        request.state.correlation_id,
    )
    version = db.get(ModelVersion, deployment.model_version_id)
    if version is not None and version.lifecycle_stage == "PRODUCTION":
        version.lifecycle_stage = "STAGING"
        db.add(
            VersionEvent(
                model_version_id=version.id,
                event_type="PRODUCTION_ROLLED_BACK",
                from_stage="PRODUCTION",
                to_stage="STAGING",
                actor="local-operator",
                reason=f"Deployment {deployment.id} was rolled back",
                correlation_id=request.state.correlation_id,
            )
        )
        db.commit()
    db.refresh(deployment)
    return deployment


@app.get("/models/{model_id}/metrics", response_model=MetricsOut)
def get_model_metrics(model_id: int, db: Session = Depends(get_db)) -> MetricsOut:
    model = get_model_or_404(db, model_id)
    latest_version = (
        db.execute(select(ModelVersion).where(ModelVersion.model_id == model_id).order_by(ModelVersion.created_at.desc()))
        .scalars()
        .first()
    )
    if latest_version is None:
        raise HTTPException(status_code=404, detail="Model has no versions")

    return MetricsOut(
        model_id=model.id,
        model_name=model.name,
        latest_version=latest_version.version,
        quality_score=latest_version.quality_score,
        drift_score=latest_version.drift_score,
        latency_ms=latest_version.latency_ms,
        throughput_rps=latest_version.throughput_rps,
        error_rate=latest_version.error_rate,
        availability=latest_version.availability,
        monitoring_status=latest_version.monitoring_status,
        last_successful_inference=None,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
