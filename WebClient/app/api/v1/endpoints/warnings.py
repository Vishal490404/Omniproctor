"""Teacher → student warning endpoints (proctor banner channel)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.orm import joinedload

from app.api.deps import AdminTeacherProctor, CurrentUser, DBSession, StudentOnly
from app.models.proctor_warning import ProctorWarning
from app.models.user import UserRole
from app.schemas.warning import (
    ProctorWarningAckRequest,
    ProctorWarningCreateRequest,
    ProctorWarningResponse,
)
from app.services.behavior_service import get_attempt_or_404
from app.services.test_service import ensure_manage_permission, get_test_or_404
from app.services.warning_service import (
    acknowledge_warning,
    create_warning,
    get_warning_or_404,
    list_warnings_for_attempt,
)

router = APIRouter()


def _serialize(warning: ProctorWarning) -> ProctorWarningResponse:
    sender_name = None
    if warning.sender is not None:
        sender_name = warning.sender.full_name or warning.sender.email
    return ProctorWarningResponse(
        id=warning.id,
        attempt_id=warning.attempt_id,
        sender_id=warning.sender_id,
        sender_name=sender_name,
        message=warning.message,
        severity=warning.severity,
        created_at=warning.created_at,
        delivered_at=warning.delivered_at,
        acknowledged_at=warning.acknowledged_at,
    )


@router.post("/attempts/{attempt_id}/warnings", response_model=ProctorWarningResponse)
def send_warning(
    attempt_id: int,
    payload: ProctorWarningCreateRequest,
    db: DBSession,
    current_user: AdminTeacherProctor,
):
    """Teacher / admin / proctor pushes a warning into the kiosk banner."""
    attempt = get_attempt_or_404(db, attempt_id)
    test = get_test_or_404(db, attempt.test_id)
    if current_user.role in {UserRole.ADMIN, UserRole.TEACHER}:
        ensure_manage_permission(test, current_user)

    warning = create_warning(db, attempt, current_user, payload.message, payload.severity)
    return _serialize(warning)


@router.get("/attempts/{attempt_id}/warnings", response_model=list[ProctorWarningResponse])
def list_warnings(
    attempt_id: int,
    db: DBSession,
    current_user: CurrentUser,
    since_id: int = Query(0, ge=0, description="Return only warnings with id > since_id"),
):
    """Both the candidate (kiosk short-poll) and staff can read this list.

    The student is only allowed to see their own warnings; staff can see any
    attempt for tests they manage (or any test if admin/proctor).
    """
    attempt = get_attempt_or_404(db, attempt_id)

    if current_user.role == UserRole.STUDENT:
        if attempt.student_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot view another student's warnings",
            )
    else:
        test = get_test_or_404(db, attempt.test_id)
        if current_user.role in {UserRole.ADMIN, UserRole.TEACHER}:
            ensure_manage_permission(test, current_user)

    rows = (
        db.query(ProctorWarning)
        .options(joinedload(ProctorWarning.sender))
        .filter(ProctorWarning.attempt_id == attempt_id)
    )
    if since_id:
        rows = rows.filter(ProctorWarning.id > since_id)
    rows = rows.order_by(ProctorWarning.id.asc()).all()
    return [_serialize(w) for w in rows]


@router.post("/warnings/{warning_id}/ack", response_model=ProctorWarningResponse)
def ack_warning(
    warning_id: int,
    payload: ProctorWarningAckRequest,
    db: DBSession,
    current_user: StudentOnly,
):
    """The kiosk acks delivery so the teacher dashboard shows a green check."""
    warning = get_warning_or_404(db, warning_id)
    attempt = get_attempt_or_404(db, warning.attempt_id)
    if attempt.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot acknowledge another student's warning",
        )

    warning = acknowledge_warning(db, warning, payload.delivered_at)
    return _serialize(warning)
