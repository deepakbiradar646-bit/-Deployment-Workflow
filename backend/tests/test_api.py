from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def approve_version(model_id: int, version_id: int) -> None:
    validated = client.post(
        f"/models/{model_id}/versions/{version_id}/transition",
        json={"target_stage": "VALIDATED", "reason": "Automated acceptance test validation"},
    )
    assert validated.status_code == 200, validated.text
    approved = client.post(
        f"/models/{model_id}/versions/{version_id}/transition",
        json={"target_stage": "APPROVED", "reason": "Automated acceptance test approval"},
    )
    assert approved.status_code == 200, approved.text


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert client.get("/ready").json()["status"] == "ready"


def test_frontend_origin_is_allowed_by_cors():
    response = client.options(
        "/deployments",
        headers={
            "Origin": "http://127.0.0.1:4200",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:4200"


def test_register_model_and_version():
    model_name = f"forecast-model-{uuid4().hex[:8]}"
    model_response = client.post(
        "/models",
        json={
            "name": model_name,
            "description": "Demand forecasting model",
            "framework": "scikit-learn",
            "algorithm": "RandomForest",
            "owner": "ops-team",
            "tags": "forecasting,critical",
        },
    )
    assert model_response.status_code == 201, model_response.text
    model_id = model_response.json()["id"]

    version_response = client.post(
        f"/models/{model_id}/versions",
        json={
            "version": "1.0.0",
            "artifact_uri": "s3://models/forecast/1.0.0/model.pkl",
            "training_data_ref": "warehouse.sales.v1",
            "quality_score": 0.93,
            "drift_score": 0.08,
            "latency_ms": 130,
            "throughput_rps": 75,
            "error_rate": 0.02,
            "availability": 0.99,
            "monitoring_status": "HEALTHY",
        },
    )
    assert version_response.status_code == 201, version_response.text
    assert version_response.json()["approval_status"] == "PENDING"
    assert version_response.json()["lifecycle_stage"] == "DRAFT"

    versions_response = client.get(f"/models/{model_id}/versions")
    assert versions_response.status_code == 200
    data = versions_response.json()
    assert len(data) == 1
    assert data[0]["version"] == "1.0.0"


def test_prevent_unapproved_version_from_production_deployment():
    model_name = f"risk-model-{uuid4().hex[:8]}"
    model_response = client.post(
        "/models",
        json={
            "name": model_name,
            "description": "Risk model",
            "framework": "PyTorch",
            "algorithm": "CNN",
            "owner": "risk-team",
            "tags": "risk",
        },
    )
    model_id = model_response.json()["id"]

    version_response = client.post(
        f"/models/{model_id}/versions",
        json={
            "version": "1.0.0",
            "artifact_uri": "s3://models/risk/1.0.0/model.pt",
            "training_data_ref": "risk.snapshot.2024",
            "quality_score": 0.82,
        },
    )
    version_id = version_response.json()["id"]

    deployment_response = client.post(
        "/deployments",
        json={
            "model_id": model_id,
            "model_version_id": version_id,
            "environment": "PRODUCTION",
            "request_reason": "Need to validate production promotion",
        },
    )
    assert deployment_response.status_code == 400
    assert "approved" in deployment_response.json()["detail"].lower()


def test_retry_and_rollback_deployment_flow():
    model_name = f"deployment-model-{uuid4().hex[:8]}"
    model_response = client.post(
        "/models",
        json={
            "name": model_name,
            "description": "Deployment workflow model",
            "framework": "XGBoost",
            "algorithm": "GradientBoosting",
            "owner": "ml-platform",
            "tags": "deployment",
        },
    )
    model_id = model_response.json()["id"]

    version_response = client.post(
        f"/models/{model_id}/versions",
        json={
            "version": "2.0.0",
            "artifact_uri": "s3://models/deploy/2.0.0/model.json",
            "training_data_ref": "feature.store.v2",
            "quality_score": 0.95,
        },
    )
    version_id = version_response.json()["id"]
    approve_version(model_id, version_id)

    deployment_response = client.post(
        "/deployments",
        json={
            "model_id": model_id,
            "model_version_id": version_id,
            "environment": "PRODUCTION",
            "request_reason": "Promote new model version",
            "idempotency_key": f"deploy-{uuid4().hex}",
        },
    )
    assert deployment_response.status_code == 201
    deployment_id = deployment_response.json()["id"]
    assert deployment_response.json()["status"] == "REQUESTED"

    completed = client.get(f"/deployments/{deployment_id}").json()
    assert completed["status"] == "SUCCEEDED"
    events = client.get(f"/deployments/{deployment_id}/events")
    assert events.status_code == 200
    assert [event["to_status"] for event in events.json()] == [
        "REQUESTED", "VALIDATING", "DEPLOYING", "SUCCEEDED"
    ]
    assert all(event["correlation_id"] for event in events.json())
    production_version = client.get(f"/models/{model_id}/versions").json()[0]
    assert production_version["lifecycle_stage"] == "PRODUCTION"

    retry_response = client.post(f"/deployments/{deployment_id}/retry")
    assert retry_response.status_code == 409

    rollback_response = client.post(f"/deployments/{deployment_id}/rollback")
    assert rollback_response.status_code == 200
    assert rollback_response.json()["status"] == "ROLLED_BACK"
    assert rollback_response.json()["rolled_back"] is True
    demoted_version = client.get(f"/models/{model_id}/versions").json()[0]
    assert demoted_version["lifecycle_stage"] == "STAGING"


def test_failed_deployment_can_be_retried():
    model_response = client.post(
        "/models",
        json={
            "name": f"retry-model-{uuid4().hex[:8]}",
            "framework": "scikit-learn",
            "algorithm": "RandomForest",
            "owner": "ml-platform",
        },
    )
    model_id = model_response.json()["id"]
    version_response = client.post(
        f"/models/{model_id}/versions",
        json={
            "version": "1.0.0",
            "artifact_uri": "file:///models/retry/1.0.0/model.pkl",
            "training_data_ref": "retry.dataset.v1",
        },
    )
    approve_version(model_id, version_response.json()["id"])
    deployment_response = client.post(
        "/deployments",
        json={
            "model_id": model_id,
            "model_version_id": version_response.json()["id"],
            "environment": "PRODUCTION",
            "simulate_failure": True,
        },
    )
    deployment_id = deployment_response.json()["id"]
    failed = client.get(f"/deployments/{deployment_id}").json()
    assert failed["status"] == "FAILED"

    retry_response = client.post(f"/deployments/{deployment_id}/retry")
    assert retry_response.status_code == 200
    assert retry_response.json()["retry_count"] == 1
    retried = client.get(f"/deployments/{deployment_id}").json()
    assert retried["status"] == "SUCCEEDED"


def test_duplicate_deployment_request_is_safe():
    model_name = f"duplicate-model-{uuid4().hex[:8]}"
    model_response = client.post(
        "/models",
        json={
            "name": model_name,
            "description": "Duplicate-safe model",
            "framework": "scikit-learn",
            "algorithm": "LogisticRegression",
            "owner": "analytics",
            "tags": "duplicate",
        },
    )
    model_id = model_response.json()["id"]

    version_response = client.post(
        f"/models/{model_id}/versions",
        json={
            "version": "1.2.0",
            "artifact_uri": "s3://models/duplicate/1.2.0/model.pkl",
            "training_data_ref": "duplicate.train.v1",
            "quality_score": 0.9,
        },
    )
    version_id = version_response.json()["id"]
    approve_version(model_id, version_id)
    key = f"duplicate-{uuid4().hex}"

    first = client.post(
        "/deployments",
        json={
            "model_id": model_id,
            "model_version_id": version_id,
            "environment": "STAGING",
            "request_reason": "Test duplicate requests",
            "idempotency_key": key,
        },
    )
    second = client.post(
        "/deployments",
        json={
            "model_id": model_id,
            "model_version_id": version_id,
            "environment": "STAGING",
            "request_reason": "Test duplicate requests",
            "idempotency_key": key,
        },
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


def test_version_comparison_and_lifecycle_gate():
    model = client.post(
        "/models",
        json={
            "name": f"compare-model-{uuid4().hex[:8]}",
            "framework": "scikit-learn",
            "algorithm": "RandomForest",
            "owner": "test-team",
        },
    ).json()
    version_ids = []
    for version, score in [("1.0.0", 0.87), ("2.0.0", 0.94)]:
        created = client.post(
            f"/models/{model['id']}/versions",
            json={
                "version": version,
                "artifact_uri": f"file:///models/compare/{version}.pkl",
                "training_data_ref": f"compare.dataset.{version}",
                "quality_score": score,
            },
        )
        assert created.status_code == 201
        version_ids.append(created.json()["id"])

    comparison = client.get(
        f"/models/{model['id']}/versions/compare",
        params={"first_version_id": version_ids[0], "second_version_id": version_ids[1]},
    )
    assert comparison.status_code == 200
    assert comparison.json()["first"]["quality_score"] == 0.87
    assert comparison.json()["second"]["quality_score"] == 0.94
    identical_comparison = client.get(
        f"/models/{model['id']}/versions/compare",
        params={"first_version_id": version_ids[0], "second_version_id": version_ids[0]},
    )
    assert identical_comparison.status_code == 400

    approve_version(model["id"], version_ids[0])
    audit = client.get(f"/models/{model['id']}/versions/{version_ids[0]}/events")
    assert audit.status_code == 200
    assert [event["to_stage"] for event in audit.json()] == ["DRAFT", "VALIDATED", "APPROVED"]
    assert audit.json()[0]["event_type"] == "VERSION_REGISTERED"
    assert audit.json()[-1]["event_type"] == "VERSION_APPROVED"

    blocked_transition = client.post(
        f"/models/{model['id']}/versions/{version_ids[0]}/transition",
        json={"target_stage": "PRODUCTION", "reason": "Skip required promotion stages"},
    )
    assert blocked_transition.status_code == 409

    cannot_skip_deploy = client.post(
        f"/models/{model['id']}/versions/{version_ids[0]}/transition",
        json={"target_stage": "PRODUCTION", "reason": "Try to promote without deployment"},
    )
    assert cannot_skip_deploy.status_code == 409


def test_request_id_is_returned_and_deployment_conflict_is_rejected():
    model = client.post(
        "/models",
        json={
            "name": f"conflict-model-{uuid4().hex[:8]}",
            "framework": "scikit-learn",
            "algorithm": "LogisticRegression",
            "owner": "test-team",
        },
    ).json()
    versions = []
    for version in ("1.0.0", "2.0.0"):
        created = client.post(
            f"/models/{model['id']}/versions",
            json={
                "version": version,
                "artifact_uri": f"file:///models/conflict/{version}.pkl",
                "training_data_ref": f"conflict.dataset.{version}",
            },
        ).json()
        approve_version(model["id"], created["id"])
        versions.append(created["id"])

    first = client.post(
        "/deployments",
        headers={"X-Request-ID": "test-correlation-123"},
        json={
            "model_id": model["id"],
            "model_version_id": versions[0],
            "environment": "PRODUCTION",
        },
    )
    assert first.status_code == 201
    assert first.headers["X-Request-ID"] == "test-correlation-123"

    conflicting = client.post(
        "/deployments",
        json={
            "model_id": model["id"],
            "model_version_id": versions[1],
            "environment": "PRODUCTION",
        },
    )
    assert conflicting.status_code == 409
