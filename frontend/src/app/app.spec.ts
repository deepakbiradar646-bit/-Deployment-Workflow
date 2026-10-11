import { provideHttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
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
});