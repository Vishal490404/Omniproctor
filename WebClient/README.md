# Omniproctor FastAPI Service

Standalone FastAPI service for Omniproctor test platform workflows.

## Features

- JWT authentication
- RBAC roles: admin, teacher, student, proctor
- Test creation and management
- Assign registered students to tests
- Student dashboard endpoint for all assigned tests (active and inactive)
- Docker Compose for API + PostgreSQL

## Structure

- `app/main.py` - FastAPI startup and router wiring
- `app/models` - SQLAlchemy models
- `app/schemas` - Pydantic request/response schemas
- `app/services` - Controller/service business logic
- `app/api/v1/endpoints` - REST endpoints

## Run with Docker (local development)

```bash
cp .env.example .env
docker compose up --build
```

| Service              | URL                              |
| -------------------- | -------------------------------- |
| Frontend (SPA)       | http://localhost:8080            |
| API (FastAPI + docs) | http://localhost:8001/docs       |
| Health checks        | `/healthz` (frontend), `/health` (API) |
| Postgres (host port) | localhost:5434                   |

The SPA reads its API base URL from `window.__APP_CONFIG__.API_BASE_URL`
which the frontend container writes at start-up from the `API_BASE_URL` env
var. That means one built image works in dev / staging / prod - no rebuild
when you move environments.

## Deploy to Azure

End-to-end VM walkthrough lives in [`AZURE_DEPLOY.md`](AZURE_DEPLOY.md). TL;DR:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

The prod overlay drops dev bind mounts, hides Postgres from the host, pins
restart policies, adds log rotation, and forces `API_BASE_URL` /
`POSTGRES_PASSWORD` / `SECRET_KEY` to be set in `.env` before the stack
starts.

## Key Endpoints

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/users/students`
- `POST /api/v1/tests`
- `PATCH /api/v1/tests/{test_id}`
- `POST /api/v1/tests/{test_id}/students/{student_id}`
- `GET /api/v1/tests/{test_id}/students`
- `GET /api/v1/dashboard/me/tests`
