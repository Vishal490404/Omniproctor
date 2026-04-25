"""Teacher live monitoring endpoint.

GET /api/v1/proctor/tests/{test_id}/live returns a per-attempt snapshot for
the live dashboard. Polled every ~3s by the frontend, with a 1s in-memory
cache on the server so a roomful of teachers viewing the same page doesn't
hammer the DB.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AdminTeacherProctor, DBSession
from app.models.user import UserRole
from app.schemas.live import LiveTestSnapshot
from app.services.live_service import get_live_snapshot
from app.services.test_service import ensure_manage_permission, get_test_or_404

router = APIRouter()


@router.get("/tests/{test_id}/live", response_model=LiveTestSnapshot)
def live_test_snapshot(
    test_id: int,
    db: DBSession,
    current_user: AdminTeacherProctor,
):
    test = get_test_or_404(db, test_id)
    if current_user.role in {UserRole.ADMIN, UserRole.TEACHER}:
        ensure_manage_permission(test, current_user)
    return get_live_snapshot(db, test)
