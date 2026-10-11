import { CommonModule } from '@angular/common';
import { Component, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { timer } from 'rxjs';
import {
  Deployment,
  DeploymentEvent,
  Metrics,
  ModelRecord,
  ModelVersion,
  ModelVersionComparison,
  MLOpsApiService,
  VersionEvent,
} from './mlops.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App implements OnInit {
  private readonly api = inject(MLOpsApiService);
  private readonly destroyRef = inject(DestroyRef);

  models = signal<ModelRecord[]>([]);
  deployments = signal<Deployment[]>([]);
  selectedModel = signal<ModelRecord | null>(null);
  metrics = signal<Metrics | null>(null);
  loading = signal(true);
  error = signal<string | null>(null);
  notice = signal<string | null>(null);
  comparison = signal<ModelVersionComparison | null>(null);
  selectedDeploymentEvents = signal<DeploymentEvent[]>([]);
  selectedDeploymentId = signal<number | null>(null);
  selectedVersionEvents = signal<VersionEvent[]>([]);
  selectedVersionEventId = signal<number | null>(null);

  modelForm = { name: '', description: '', framework: 'scikit-learn', algorithm: '', owner: '', tags: '' };
  versionForm = {
    version: '',
    artifact_uri: '',
    training_data_ref: '',
    quality_score: 0,
    drift_score: 0,
    latency_ms: 0,
    throughput_rps: 0,
    error_rate: 0,
    availability: 0,
    monitoring_status: 'HEALTHY',
  };
  deploymentVersionId: number | null = null;
  deploymentEnvironment = 'STAGING';
  deploymentReason = '';
  simulateFailure = false;
  firstCompareId: number | null = null;
  secondCompareId: number | null = null;
  modelSearch = '';
  deploymentSearch = '';
  deploymentEnvironmentFilter = 'ALL';

  ngOnInit(): void {
    this.loadModels();
    timer(0, 2000)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.loadDeployments());
  }

  selectModel(model: ModelRecord): void {
    this.selectedModel.set(model);
    this.comparison.set(null);
    this.firstCompareId = null;
    this.secondCompareId = null;
    this.deploymentVersionId = model.versions?.[0]?.id ?? null;
    this.api.getMetrics(model.id).subscribe({
      next: (metric) => this.metrics.set(metric),
      error: () => {
        this.metrics.set(null);
        this.setError('Model metrics could not be loaded from the API.');
      },
    });
  }

  createModel(): void {
    this.notice.set(null);
    this.api.createModel(this.modelForm).subscribe({
      next: (model) => {
        this.modelForm = { name: '', description: '', framework: 'scikit-learn', algorithm: '', owner: '', tags: '' };
        this.notice.set(`Model "${model.name}" registered.`);
        this.loadModels(model.id);
      },
      error: (error: { error?: { detail?: string } }) =>
        this.setError(error.error?.detail ?? 'Model registration failed.'),
    });
  }

  createVersion(): void {
    const model = this.selectedModel();
    if (!model) return;
    this.notice.set(null);
    this.api.createVersion(model.id, this.versionForm).subscribe({
      next: (version) => {
        this.notice.set(`Version ${version.version} registered in DRAFT.`);
        this.versionForm = {
          version: '',
          artifact_uri: '',
          training_data_ref: '',
          quality_score: 0,
          drift_score: 0,
          latency_ms: 0,
          throughput_rps: 0,
          error_rate: 0,
          availability: 0,
          monitoring_status: 'HEALTHY',
        };
        this.loadModels(model.id);
      },
      error: (error: { error?: { detail?: string } }) =>
        this.setError(error.error?.detail ?? 'Version registration failed.'),
    });
  }

  advanceVersion(version: ModelVersion): void {
    const model = this.selectedModel();
    if (!model) return;
    const nextStage: Record<string, string> = {
      DRAFT: 'VALIDATED',
      VALIDATED: 'APPROVED',
      APPROVED: 'STAGING',
    };
    const target = nextStage[version.lifecycle_stage];
    if (!target) return;
    this.api.transitionVersion(model.id, version.id, target).subscribe({
      next: () => {
        this.notice.set(`Version ${version.version} advanced to ${target}.`);
        this.loadModels(model.id);
      },
      error: (error: { error?: { detail?: string } }) =>
        this.setError(error.error?.detail ?? 'Version promotion failed.'),
    });
  }

  canAdvanceVersion(version: ModelVersion): boolean {
    return ['DRAFT', 'VALIDATED', 'APPROVED'].includes(version.lifecycle_stage);
  }

  archiveVersion(version: ModelVersion): void {
    const model = this.selectedModel();
    if (!model) return;
    this.api.transitionVersion(model.id, version.id, 'ARCHIVED').subscribe({
      next: () => {
        this.notice.set(`Version ${version.version} archived.`);
        this.loadModels(model.id);
      },
      error: (error: { error?: { detail?: string } }) =>
        this.setError(error.error?.detail ?? 'Version archival failed.'),
    });
  }

  viewVersionEvents(version: ModelVersion): void {
    const model = this.selectedModel();
    if (!model) return;
    this.selectedVersionEventId.set(version.id);
    this.api.getVersionEvents(model.id, version.id).subscribe({
      next: (events) => this.selectedVersionEvents.set(events),
      error: (error: { error?: { detail?: string } }) =>
        this.setError(error.error?.detail ?? 'Version audit history could not be loaded.'),
    });
  }

  compareSelectedVersions(): void {
    const model = this.selectedModel();
    if (!model || !this.firstCompareId || !this.secondCompareId) return;
    this.api.compareVersions(model.id, this.firstCompareId, this.secondCompareId).subscribe({
      next: (result) => this.comparison.set(result),
      error: (error: { error?: { detail?: string } }) =>
        this.setError(error.error?.detail ?? 'Version comparison failed.'),
    });
  }

  createDeployment(): void {
    const model = this.selectedModel();
    if (!model || !this.deploymentVersionId) return;
    this.api.createDeployment({
      model_id: model.id,
      model_version_id: this.deploymentVersionId,
      environment: this.deploymentEnvironment,
      request_reason: this.deploymentReason,
      idempotency_key: `ui-${crypto.randomUUID()}`,
      simulate_failure: this.simulateFailure,
    }).subscribe({
      next: (deployment) => {
        this.notice.set(`Deployment ${deployment.id} accepted; tracking its status.`);
        this.deploymentReason = '';
        this.loadDeployments();
      },
      error: (error: { error?: { detail?: string } }) =>
        this.setError(error.error?.detail ?? 'Deployment request failed.'),
    });
  }

  retryDeployment(deployment: Deployment): void {
    this.api.retryDeployment(deployment.id).subscribe({
      next: () => {
        this.notice.set(`Retry requested for deployment ${deployment.id}.`);
        this.loadDeployments();
      },
      error: (error: { error?: { detail?: string } }) =>
        this.setError(error.error?.detail ?? 'Deployment retry failed.'),
    });
  }

  rollbackDeployment(deployment: Deployment): void {
    this.api.rollbackDeployment(deployment.id).subscribe({
      next: () => {
        this.notice.set(`Rollback completed for deployment ${deployment.id}.`);
        this.loadDeployments();
      },
      error: (error: { error?: { detail?: string } }) =>
        this.setError(error.error?.detail ?? 'Deployment rollback failed.'),
    });
  }

  viewDeploymentEvents(deployment: Deployment): void {
    this.selectedDeploymentId.set(deployment.id);
    this.api.getDeploymentEvents(deployment.id).subscribe({
      next: (events) => this.selectedDeploymentEvents.set(events),
      error: (error: { error?: { detail?: string } }) =>
        this.setError(error.error?.detail ?? 'Deployment event history could not be loaded.'),
    });
  }

  private loadModels(selectedModelId?: number): void {
    this.api.getModels().subscribe({
      next: (data) => {
        this.models.set(data);
        this.error.set(null);
        if (data.length > 0) {
          this.selectModel(data.find((model) => model.id === selectedModelId) ?? data[0]);
        } else {
          this.selectedModel.set(null);
          this.metrics.set(null);
        }
        this.loading.set(false);
      },
      error: () => {
        this.setError('Could not load model inventory from the API.');
        this.loading.set(false);
      },
    });
  }

  private loadDeployments(): void {
    this.api.getDeployments().subscribe({
      next: (data) => {
        const previousStatuses = new Map(this.deployments().map((deployment) => [deployment.id, deployment.status]));
        this.deployments.set(data);
        const selectedModelId = this.selectedModel()?.id;
        const completedProductionChange = data.some((deployment) =>
          deployment.model_id === selectedModelId &&
          deployment.environment === 'PRODUCTION' &&
          ['SUCCEEDED', 'ROLLED_BACK'].includes(deployment.status) &&
          previousStatuses.has(deployment.id) &&
          previousStatuses.get(deployment.id) !== deployment.status,
        );
        if (completedProductionChange && selectedModelId !== undefined) {
          this.loadModels(selectedModelId);
        }
      },
      error: () => this.setError('Deployment history could not be loaded from the API.'),
    });
  }

  private setError(message: string): void {
    this.error.set(message);
    this.notice.set(null);
  }

  modelName(modelId: number): string {
    return this.models().find((model) => model.id === modelId)?.name ?? `Model ${modelId}`;
  }

  filteredModels(): ModelRecord[] {
    const query = this.modelSearch.trim().toLowerCase();
    return this.models().filter((model) =>
      `${model.name} ${model.framework} ${model.algorithm} ${model.owner} ${model.tags}`.toLowerCase().includes(query),
    );
  }

  filteredDeployments(): Deployment[] {
    const query = this.deploymentSearch.trim().toLowerCase();
    return this.deployments().filter((deployment) => {
      const matchesEnvironment =
        this.deploymentEnvironmentFilter === 'ALL' || deployment.environment === this.deploymentEnvironmentFilter;
      const searchable = `${this.modelName(deployment.model_id)} ${deployment.status} ${deployment.environment} ${deployment.request_reason ?? ''} ${deployment.status_reason ?? ''}`.toLowerCase();
      return matchesEnvironment && searchable.includes(query);
    });
  }

  trackById(index: number, item: { id: number }): number {
    return item.id;
  }
}
