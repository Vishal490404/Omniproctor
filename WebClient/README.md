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

## Run with Docker

```bash
cp .env.example .env
docker compose up --build
```

API docs: http://localhost:8001/docs

## Key Endpoints

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/users/students`
- `POST /api/v1/tests`
- `PATCH /api/v1/tests/{test_id}`
- `POST /api/v1/tests/{test_id}/students/{student_id}`
- `GET /api/v1/tests/{test_id}/students`
- `GET /api/v1/dashboard/me/tests`
