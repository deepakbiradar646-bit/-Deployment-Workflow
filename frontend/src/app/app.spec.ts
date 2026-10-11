import { provideHttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { vi } from 'vitest';
import { App } from './app';
import { MLOpsApiService } from './mlops.service';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [
        provideHttpClient(),
        {
          provide: MLOpsApiService,
          useValue: {
            getModels: () => of([
              {
                id: 1,
                name: 'demand-forecast',
                description: 'Forecasts regional demand for the next 14 days.',
                framework: 'scikit-learn',
                algorithm: 'RandomForest',
                owner: 'operations',
                tags: 'forecasting,critical',
                created_at: '2025-01-15T10:00:00Z',
                updated_at: '2025-01-16T09:30:00Z',
                versions: [],
              },
            ]),
            getDeployments: () => of([]),
            getMetrics: () => of({
              model_id: 1,
              model_name: 'demand-forecast',
              latest_version: '1.2.0',
              quality_score: 0.93,
              drift_score: 0.07,
              latency_ms: 150,
              throughput_rps: 82,
              error_rate: 0.02,
              availability: 0.99,
              monitoring_status: 'HEALTHY',
              last_successful_inference: '2025-03-21T08:40:00Z',
            }),
          },
        },
      ],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('should render the control plane heading', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('h1')?.textContent).toContain('Model governance and deployment overview');
  });

  it('should show model registration and empty deployment state', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Register model');
    expect(compiled.textContent).toContain('No deployments have been requested yet.');
    expect(compiled.textContent).toContain('API online');
  });

  it('should keep the API online when a model has no metrics and recover on a successful request', () => {
    const api = TestBed.inject(MLOpsApiService);
    const getMetrics = vi.spyOn(api, 'getMetrics')
      .mockReturnValueOnce(throwError(() => ({
        status: 404,
        error: { detail: 'Model has no versions' },
      })))
      .mockReturnValueOnce(of({
        model_id: 1,
        model_name: 'demand-forecast',
        latest_version: '1.2.0',
        quality_score: 0.93,
        drift_score: 0.07,
        latency_ms: 150,
        throughput_rps: 82,
        error_rate: 0.02,
        availability: 0.99,
        monitoring_status: 'HEALTHY',
        last_successful_inference: null,
      }));
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    fixture.detectChanges();

    expect(app.apiAvailable()).toBe(true);
    expect(app.error()).toBe('Model has no versions');
    expect(fixture.nativeElement.textContent).toContain('API online');

    app.selectModel(app.models()[0]);

    expect(getMetrics).toHaveBeenCalledTimes(2);
    expect(app.apiAvailable()).toBe(true);
    expect(app.error()).toBeNull();
  });
});