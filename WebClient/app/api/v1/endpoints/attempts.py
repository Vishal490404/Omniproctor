from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminTeacherProctor, DBSession, KioskAttempt, StudentOnly
from app.models.user import UserRole
from app.schemas.attempt import AttemptEndRequest, AttemptSummaryResponse, AttemptWithSummaryResponse, TestAttemptResponse
from app.services.attempt_service import end_attempt, get_attempt_summary, list_attempts_for_student, start_attempt
from app.services.kiosk_token_service import issue_kiosk_token
from app.services.test_service import ensure_manage_permission, get_test_or_404

router = APIRouter()


@router.post("/{test_id}/attempts/start", response_model=AttemptWithSummaryResponse)
def start_test_attempt(test_id: int, db: DBSession, current_user: StudentOnly):
    """Student clicks "Open in kiosk browser" → WebClient calls this.

    The student JWT is required (the candidate must be authenticated to
    create an attempt), but the response also includes a separate
    kiosk capability token that the kiosk will use for the rest of the
    exam. This decouples telemetry/End Session from the WebClient
    session lifetime so a long exam doesn't run past the user JWT's
    expiry.
    """
    test = get_test_or_404(db, test_id)
    attempt = start_attempt(db, test, current_user)
    summary = get_attempt_summary(db, test, current_user.id)
    kiosk_token = issue_kiosk_token(attempt, test)
    return {"attempt": attempt, "summary": summary, "kiosk_token": kiosk_token}


@router.post("/{test_id}/attempts/end", response_model=AttemptWithSummaryResponse)
def end_test_attempt(
    test_id: int,
    payload: AttemptEndRequest,
    db: DBSession,
    kiosk_attempt: KioskAttempt,
):
    """Kiosk → "End Session". Authenticates with the kiosk capability
    token (NOT the student JWT) so this still works after the user's
    WebClient session has expired.

    The kiosk token is bound to a specific attempt; we still take
    ``test_id`` in the URL for the existing route shape, but cross-
    check it against the token to refuse mismatches.
    """
    if kiosk_attempt.test_id != test_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kiosk token does not belong to this test",
        )
    test = get_test_or_404(db, test_id)
    student = kiosk_attempt.student
    attempt = end_attempt(db, test, student, payload.reason)
    summary = get_attempt_summary(db, test, student.id)
    return {"attempt": attempt, "summary": summary}


@router.get("/{test_id}/attempts/me", response_model=list[TestAttemptResponse])
def my_attempts_for_test(test_id: int, db: DBSession, current_user: StudentOnly):
    return list_attempts_for_student(db, test_id, current_user.id)


@router.get("/{test_id}/students/{student_id}/attempt-summary", response_model=AttemptSummaryResponse)
def attempt_summary_for_student(
    test_id: int,
    student_id: int,
    db: DBSession,
    current_user: AdminTeacherProctor,
):
    test = get_test_or_404(db, test_id)
    if current_user.role in {UserRole.ADMIN, UserRole.TEACHER}:
        ensure_manage_permission(test, current_user)
    return get_attempt_summary(db, test, student_id)


@router.get("/{test_id}/students/{student_id}/attempts", response_model=list[TestAttemptResponse])
def attempts_for_student(
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

    return list_attempts_for_student(db, test_id, student_id)
