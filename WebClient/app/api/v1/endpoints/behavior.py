from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminTeacherProctor, CurrentUser, DBSession, StudentOnly
from app.models.user import UserRole
from app.schemas.behavior import (
    BehaviorEventBatchRequest,
    BehaviorEventBatchResponse,
    BehaviorEventCreateRequest,
    BehaviorEventResponse,
)
from app.services.behavior_service import (
    create_behavior_event,
    create_behavior_events_bulk,
    get_attempt_or_404,
    list_events_for_attempt,
    list_events_for_test_student,
)
from app.services.test_service import ensure_manage_permission, get_test_or_404
from app.services.warning_service import latest_warning_id_for_attempt

router = APIRouter()


@router.post("/attempts/{attempt_id}/events", response_model=BehaviorEventResponse)
def ingest_behavior_event(
    attempt_id: int,
    payload: BehaviorEventCreateRequest,
    db: DBSession,
    current_user: StudentOnly,
):
    attempt = get_attempt_or_404(db, attempt_id)
    if attempt.student_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot log event for another student")

    return create_behavior_event(
        db,
        attempt,
        payload.event_type,
        payload.payload,
        payload.severity,
        payload.event_time,
    )


@router.post(
    "/attempts/{attempt_id}/events:batch",
    response_model=BehaviorEventBatchResponse,
)
def ingest_behavior_events_batch(
    attempt_id: int,
    payload: BehaviorEventBatchRequest,
    db: DBSession,
    current_user: StudentOnly,
):
    """Bulk ingestion path used by the kiosk's BatchPoster.

    Capped at ``MAX_BATCH_SIZE`` events per call (validated by the schema).
    Returns the latest warning id known for the attempt so the kiosk can
    dedup its warning poll without an extra round-trip.
    """
    attempt = get_attempt_or_404(db, attempt_id)
    if attempt.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot log events for another student",
        )

    accepted = 0
    rejected = 0
    if payload.events:
        accepted = create_behavior_events_bulk(db, attempt, payload.events)
        rejected = len(payload.events) - accepted

    return BehaviorEventBatchResponse(
        accepted=accepted,
        rejected=rejected,
        latest_warning_id=latest_warning_id_for_attempt(db, attempt_id),
    )


@router.get("/attempts/{attempt_id}/events", response_model=list[BehaviorEventResponse])
def get_attempt_events(attempt_id: int, db: DBSession, current_user: CurrentUser):
    attempt = get_attempt_or_404(db, attempt_id)

    if current_user.role == UserRole.STUDENT and attempt.student_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot view another student's events")

    if current_user.role in {UserRole.ADMIN, UserRole.TEACHER, UserRole.PROCTOR}:
        test = get_test_or_404(db, attempt.test_id)
        if current_user.role in {UserRole.ADMIN, UserRole.TEACHER}:
            ensure_manage_permission(test, current_user)

    return list_events_for_attempt(db, attempt_id)


@router.get("/tests/{test_id}/students/{student_id}/events", response_model=list[BehaviorEventResponse])
def get_test_student_events(
    test_id: int,
    student_id: int,
    db: DBSession,
    current_user: AdminTeacherProctor,
):
    test = get_test_or_404(db, test_id)
    if current_user.role in {UserRole.ADMIN, UserRole.TEACHER}:
        ensure_manage_permission(test, current_user)

    if student_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid student id")

    return list_events_for_test_student(db, test_id, student_id)
