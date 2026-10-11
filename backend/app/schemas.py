from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ModelBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    framework: str = Field(..., min_length=1)
    algorithm: str = Field(..., min_length=1)
    owner: str = Field(..., min_length=1)
    tags: str = ""


class ModelCreate(ModelBase):
    pass


class ModelVersionBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(..., min_length=1)
    artifact_uri: str = Field(..., min_length=1)
    training_data_ref: str = Field(..., min_length=1)
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    drift_score: float = Field(default=0.0, ge=0.0)
    latency_ms: float = Field(default=0.0, ge=0.0)
    throughput_rps: float = Field(default=0.0, ge=0.0)
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    availability: float = Field(default=0.0, ge=0.0, le=1.0)
    monitoring_status: str = "HEALTHY"


class ModelVersionCreate(ModelVersionBase):
    pass


class ModelVersionOut(ModelVersionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    model_id: int
    approval_status: str
    lifecycle_stage: str
    created_at: datetime


class ModelOut(ModelBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime
    versions: List[ModelVersionOut] = []


class DeploymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: int
    model_version_id: int
    environment: str = Field(..., pattern=r"^(DEV|STAGING|PRODUCTION)$")
    request_reason: Optional[str] = None
    idempotency_key: Optional[str] = None
    simulate_failure: bool = False


class DeploymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    model_id: int
    model_version_id: int
    environment: str
    status: str
    request_reason: Optional[str]
    retry_count: int
    idempotency_key: Optional[str]
    status_reason: Optional[str]
    requested_at: datetime
    updated_at: datetime
    rolled_back: bool


class VersionTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_stage: str
    reason: str = Field(..., min_length=1, max_length=500)
    actor: str = Field(default="local-operator", min_length=1, max_length=100)


class ModelVersionComparison(BaseModel):
    first: ModelVersionOut
    second: ModelVersionOut


class DeploymentEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    deployment_id: int
    event_type: str
    from_status: str | None
    to_status: str
    reason: str
    correlation_id: str | None
    created_at: datetime


class VersionEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    model_version_id: int
    event_type: str
    from_stage: str | None
    to_stage: str
    actor: str
    reason: str
    correlation_id: str | None
    created_at: datetime


class MetricsOut(BaseModel):
    model_id: int
    model_name: str
    latest_version: str
    quality_score: float
    drift_score: float
    latency_ms: float
    throughput_rps: float
    error_rate: float
    availability: float
    monitoring_status: str
    last_successful_inference: datetime | None = None


class HealthOut(BaseModel):
    status: str
    service: str
    database: str


class OpsMetricsOut(BaseModel):
    model_count: int
    version_count: int
    deployment_count: int
    failed_deployment_count: int
    deployments_by_status: dict[str, int]


class ApiMessage(BaseModel):
    detail: str
