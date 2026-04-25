from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminTeacherProctor, DBSession, StudentOnly
from app.models.user import UserRole
from app.schemas.attempt import AttemptEndRequest, AttemptSummaryResponse, AttemptWithSummaryResponse, TestAttemptResponse
from app.services.attempt_service import end_attempt, get_attempt_summary, list_attempts_for_student, start_attempt
from app.services.test_service import ensure_manage_permission, get_test_or_404

router = APIRouter()


@router.post("/{test_id}/attempts/start", response_model=AttemptWithSummaryResponse)
def start_test_attempt(test_id: int, db: DBSession, current_user: StudentOnly):
    test = get_test_or_404(db, test_id)
    attempt = start_attempt(db, test, current_user)
    summary = get_attempt_summary(db, test, current_user.id)
    return {"attempt": attempt, "summary": summary}


@router.post("/{test_id}/attempts/end", response_model=AttemptWithSummaryResponse)
def end_test_attempt(
    test_id: int,
    payload: AttemptEndRequest,
    db: DBSession,
    current_user: StudentOnly,
):
    test = get_test_or_404(db, test_id)
    attempt = end_attempt(db, test, current_user, payload.reason)
    summary = get_attempt_summary(db, test, current_user.id)
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
