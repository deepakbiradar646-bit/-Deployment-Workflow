from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, relationship

from .database import Base


class ModelRecord(Base):
    __tablename__ = "models"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    name: Mapped[str] = Column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = Column(Text, nullable=True)
    framework: Mapped[str] = Column(String(100), nullable=False)
    algorithm: Mapped[str] = Column(String(100), nullable=False)
    owner: Mapped[str] = Column(String(100), nullable=False)
    tags: Mapped[str] = Column(String(500), default="")
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    versions: Mapped[List["ModelVersion"]] = relationship(back_populates="model", cascade="all, delete-orphan")
    deployments: Mapped[List["Deployment"]] = relationship(back_populates="model", cascade="all, delete-orphan")


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    model_id: Mapped[int] = Column(ForeignKey("models.id"), nullable=False)
    version: Mapped[str] = Column(String(50), nullable=False)
    artifact_uri: Mapped[str] = Column(String(500), nullable=False)
    training_data_ref: Mapped[str] = Column(String(500), nullable=False)
    approval_status: Mapped[str] = Column(String(50), default="PENDING", nullable=False)
    lifecycle_stage: Mapped[str] = Column(String(50), default="DRAFT", nullable=False)
    quality_score: Mapped[float] = Column(Float, default=0.0)
    drift_score: Mapped[float] = Column(Float, default=0.0)
    latency_ms: Mapped[float] = Column(Float, default=0.0)
    throughput_rps: Mapped[float] = Column(Float, default=0.0)
    error_rate: Mapped[float] = Column(Float, default=0.0)
    availability: Mapped[float] = Column(Float, default=0.0)
    monitoring_status: Mapped[str] = Column(String(50), default="HEALTHY")
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    model: Mapped[ModelRecord] = relationship(back_populates="versions")
    deployments: Mapped[List["Deployment"]] = relationship(back_populates="model_version", cascade="all, delete-orphan")
    events: Mapped[List["VersionEvent"]] = relationship(
        back_populates="model_version", cascade="all, delete-orphan", order_by="VersionEvent.created_at"
    )


class VersionEvent(Base):
    __tablename__ = "version_events"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    model_version_id: Mapped[int] = Column(ForeignKey("model_versions.id"), nullable=False, index=True)
    event_type: Mapped[str] = Column(String(50), nullable=False)
    from_stage: Mapped[str | None] = Column(String(50), nullable=True)
    to_stage: Mapped[str] = Column(String(50), nullable=False)
    actor: Mapped[str] = Column(String(100), nullable=False)
    reason: Mapped[str] = Column(Text, nullable=False)
    correlation_id: Mapped[str | None] = Column(String(64), nullable=True)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    model_version: Mapped[ModelVersion] = relationship(back_populates="events")


class Deployment(Base):
    __tablename__ = "deployments"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    model_id: Mapped[int] = Column(ForeignKey("models.id"), nullable=False)
    model_version_id: Mapped[int] = Column(ForeignKey("model_versions.id"), nullable=False)
    environment: Mapped[str] = Column(String(50), nullable=False)
    status: Mapped[str] = Column(String(50), default="REQUESTED", nullable=False)
    request_reason: Mapped[str | None] = Column(String(255), nullable=True)
    retry_count: Mapped[int] = Column(Integer, default=0)
    idempotency_key: Mapped[str | None] = Column(String(255), unique=True, nullable=True)
    status_reason: Mapped[str | None] = Column(Text, nullable=True)
    requested_at: Mapped[datetime] = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    rolled_back: Mapped[bool] = Column(Boolean, default=False)

    model: Mapped[ModelRecord] = relationship(back_populates="deployments")
    model_version: Mapped[ModelVersion] = relationship(back_populates="deployments")
    events: Mapped[List["DeploymentEvent"]] = relationship(
        back_populates="deployment", cascade="all, delete-orphan", order_by="DeploymentEvent.created_at"
    )


class DeploymentEvent(Base):
    __tablename__ = "deployment_events"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    deployment_id: Mapped[int] = Column(ForeignKey("deployments.id"), nullable=False, index=True)
    event_type: Mapped[str] = Column(String(50), nullable=False)
    from_status: Mapped[str | None] = Column(String(50), nullable=True)
    to_status: Mapped[str] = Column(String(50), nullable=False)
    reason: Mapped[str] = Column(Text, nullable=False)
    correlation_id: Mapped[str | None] = Column(String(64), nullable=True)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    deployment: Mapped[Deployment] = relationship(back_populates="events")
