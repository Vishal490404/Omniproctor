import logging

from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminTeacherProctor, CurrentUser, DBSession, StudentOnly
from app.models.user import UserRole
from app.schemas.behavior import (
    MAX_BATCH_SIZE,
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

logger = logging.getLogger(__name__)

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

    Capped at ``MAX_BATCH_SIZE`` events per call (enforced here, not at
    schema time, so we can return a clean 413 instead of a 422). Each
    event is validated individually so a single malformed entry (e.g.
    a future ``event_type`` the server doesn't know yet) doesn't reject
    the whole batch.

    Returns the latest warning id known for the attempt so the kiosk can
    dedup its warning poll without an extra round-trip.
    """
    attempt = get_attempt_or_404(db, attempt_id)
    if attempt.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot log events for another student",
        )

    raw_events = payload.events or []
    if len(raw_events) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Batch may not exceed {MAX_BATCH_SIZE} events",
        )

    valid: list[BehaviorEventCreateRequest] = []
    rejected = 0
    for raw in raw_events:
        try:
            valid.append(BehaviorEventCreateRequest.model_validate(raw))
        except Exception as exc:
            rejected += 1
            logger.warning(
                "Dropping malformed event in batch (attempt %s): %s | event=%r",
                attempt_id,
                exc,
                raw,
            )

    accepted = create_behavior_events_bulk(db, attempt, valid) if valid else 0

    return BehaviorEventBatchResponse(
        accepted=accepted,
        rejected=rejected + (len(valid) - accepted),
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
