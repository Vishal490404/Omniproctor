from fastapi import APIRouter

from app.api.v1.endpoints import (
    assignments,
    attempts,
    auth,
    behavior,
    dashboard,
    downloads,
    tests,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(tests.router, prefix="/tests", tags=["tests"])
api_router.include_router(assignments.router, prefix="/tests", tags=["assignments"])
api_router.include_router(attempts.router, prefix="/tests", tags=["attempts"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(behavior.router, prefix="/behavior", tags=["behavior"])
api_router.include_router(downloads.router, prefix="/downloads", tags=["downloads"])
