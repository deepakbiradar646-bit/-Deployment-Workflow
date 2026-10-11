# MLOps Angular Dashboard

The Angular dashboard provides model inventory, version lifecycle actions, monitoring metrics, version comparison, and deployment management for the MLOps Platform Technical Assignment.

## Development server

From the `frontend` directory, start the dashboard with:

```powershell
npm run start -- --host 127.0.0.1 --port 4200
```

Open `http://127.0.0.1:4200/`. Run the FastAPI backend in a separate terminal for live application data.

## Building

Create a production build:

```powershell
npm run build
```

## Running unit tests

Run the Angular component tests with Vitest:

```powershell
npm test -- --watch=false --isolate=false
```

## Additional Resources

The dashboard communicates with the backend through the API service in `src/app/mlops.service.ts`; API base URL configuration is in `src/environments/environment.ts`. For additional Angular CLI references, visit the [Angular CLI Overview and Command Reference](https://angular.dev/tools/cli).
