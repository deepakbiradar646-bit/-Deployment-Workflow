import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../environments/environment';

export interface ModelVersion {
  id: number;
  model_id: number;
  version: string;
  artifact_uri: string;
  training_data_ref: string;
  approval_status: string;
  lifecycle_stage: string;
  quality_score: number;
  drift_score: number;
  latency_ms: number;
  throughput_rps: number;
  error_rate: number;
  availability: number;
  monitoring_status: string;
  created_at: string;
}

export interface ModelRecord {
  id: number;
  name: string;
  description?: string | null;
  framework: string;
  algorithm: string;
  owner: string;
  tags: string;
  created_at: string;
  updated_at: string;
  versions?: ModelVersion[];
}

export interface Deployment {
  id: number;
  model_id: number;
  model_version_id: number;
  environment: string;
  status: string;
  request_reason?: string | null;
  retry_count: number;
  idempotency_key?: string | null;
  status_reason?: string | null;
  requested_at: string;
  updated_at: string;
  rolled_back: boolean;
}

export interface Metrics {
  model_id: number;
  model_name: string;
  latest_version: string;
  quality_score: number;
  drift_score: number;
  latency_ms: number;
  throughput_rps: number;
  error_rate: number;
  availability: number;
  monitoring_status: string;
  last_successful_inference?: string | null;
}

export interface DeploymentEvent {
  id: number;
  deployment_id: number;
  event_type: string;
  from_status?: string | null;
  to_status: string;
  reason: string;
  correlation_id?: string | null;
  created_at: string;
}

export interface VersionEvent {
  id: number;
  model_version_id: number;
  event_type: string;
  from_stage: string;
  to_stage: string;
  actor: string;
  reason: string;
  correlation_id?: string | null;
  created_at: string;
}

export interface ModelVersionComparison {
  first: ModelVersion;
  second: ModelVersion;
}

@Injectable({ providedIn: 'root' })
export class MLOpsApiService {
  private http = inject(HttpClient);
  private readonly baseUrl = environment.apiBaseUrl;

  createModel(payload: Omit<ModelRecord, 'id' | 'created_at' | 'updated_at' | 'versions'>): Observable<ModelRecord> {
    return this.http.post<ModelRecord>(`${this.baseUrl}/models`, payload);
  }

  createVersion(
    modelId: number,
    payload: Omit<ModelVersion, 'id' | 'model_id' | 'created_at' | 'approval_status' | 'lifecycle_stage'>,
  ): Observable<ModelVersion> {
    return this.http.post<ModelVersion>(`${this.baseUrl}/models/${modelId}/versions`, payload);
  }

  transitionVersion(modelId: number, versionId: number, targetStage: string): Observable<ModelVersion> {
    return this.http.post<ModelVersion>(`${this.baseUrl}/models/${modelId}/versions/${versionId}/transition`, {
      target_stage: targetStage,
      reason: `Operator advanced version to ${targetStage}`,
    });
  }

  compareVersions(modelId: number, firstId: number, secondId: number): Observable<ModelVersionComparison> {
    return this.http.get<ModelVersionComparison>(`${this.baseUrl}/models/${modelId}/versions/compare`, {
      params: { first_version_id: firstId, second_version_id: secondId },
    });
  }

  createDeployment(payload: {
    model_id: number;
    model_version_id: number;
    environment: string;
    request_reason: string;
    idempotency_key: string;
    simulate_failure: boolean;
  }): Observable<Deployment> {
    return this.http.post<Deployment>(`${this.baseUrl}/deployments`, payload);
  }

  retryDeployment(deploymentId: number): Observable<Deployment> {
    return this.http.post<Deployment>(`${this.baseUrl}/deployments/${deploymentId}/retry`, {});
  }

  rollbackDeployment(deploymentId: number): Observable<Deployment> {
    return this.http.post<Deployment>(`${this.baseUrl}/deployments/${deploymentId}/rollback`, {});
  }

  getDeploymentEvents(deploymentId: number): Observable<DeploymentEvent[]> {
    return this.http.get<DeploymentEvent[]>(`${this.baseUrl}/deployments/${deploymentId}/events`);
  }

  getVersionEvents(modelId: number, versionId: number): Observable<VersionEvent[]> {
    return this.http.get<VersionEvent[]>(`${this.baseUrl}/models/${modelId}/versions/${versionId}/events`);
  }

  getModels(): Observable<ModelRecord[]> {
    return this.http.get<ModelRecord[]>(`${this.baseUrl}/models`);
  }

  getDeployments(): Observable<Deployment[]> {
    return this.http.get<Deployment[]>(`${this.baseUrl}/deployments`);
  }

  getMetrics(modelId: number): Observable<Metrics> {
    return this.http.get<Metrics>(`${this.baseUrl}/models/${modelId}/metrics`);
  }
}
