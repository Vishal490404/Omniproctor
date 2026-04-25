from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.assignment import TestAssignment
from app.models.user import User
from app.schemas.assignment import (
    AssignmentBulkByEmailRequest,
    AssignmentBulkItemResponse,
    AssignmentBulkResponse,
    AssignmentCreateRequest,
)
from app.services.assignment_service import assign_student, unassign_student
from app.services.attempt_service import get_attempt_summary_map
from app.services.test_service import ensure_manage_permission, get_test_or_404


def assign_student_controller(
    db: Session,
    test_id: int,
    student_id: int,
    payload: AssignmentCreateRequest,
    added_by_user_id: int,
):
    test = get_test_or_404(db, test_id)
    current_user = db.query(User).filter(User.id == added_by_user_id).first()
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    ensure_manage_permission(test, current_user)

    student = db.query(User).filter(User.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    return assign_student(db, test, student, added_by_user_id, payload.note)


def remove_student_controller(db: Session, test_id: int, student_id: int, current_user: User):
    test = get_test_or_404(db, test_id)
    ensure_manage_permission(test, current_user)
    unassign_student(db, test_id, student_id)


def list_assigned_students_controller(db: Session, test_id: int):
    test = get_test_or_404(db, test_id)
    assignments = (
        db.query(TestAssignment, User)
        .join(User, User.id == TestAssignment.student_id)
        .filter(TestAssignment.test_id == test_id)
        .order_by(TestAssignment.id.desc())
        .all()
    )
    summary_map = get_attempt_summary_map(db, test, [student.id for _, student in assignments])
    return assignments, summary_map


def assign_students_by_email_controller(
    db: Session,
    test_id: int,
    payload: AssignmentBulkByEmailRequest,
    added_by_user_id: int,
) -> AssignmentBulkResponse:
    test = get_test_or_404(db, test_id)
    current_user = db.query(User).filter(User.id == added_by_user_id).first()
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    ensure_manage_permission(test, current_user)

    normalized_emails: list[str] = []
    for email in payload.emails:
        cleaned = email.strip()
        if not cleaned:
            continue

        if cleaned.lower() not in [item.lower() for item in normalized_emails]:
            normalized_emails.append(cleaned)

    if not normalized_emails:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide at least one valid email")

    results: list[AssignmentBulkItemResponse] = []
    assigned_count = 0
    failed_count = 0

    for email in normalized_emails:
        student = db.query(User).filter(func.lower(User.email) == email.lower()).first()
        if not student:
            failed_count += 1
            results.append(
                AssignmentBulkItemResponse(
                    email=email,
                    status="failed",
                    message="Email is not registered on the platform",
                )
            )
            continue

        try:
            assignment = assign_student(db, test, student, added_by_user_id, payload.note)
            assigned_count += 1
            results.append(
                AssignmentBulkItemResponse(
                    email=email,
                    status="assigned",
                    message="Student assigned successfully",
                    assignment_id=assignment.id,
                    student_id=student.id,
                )
            )
        except HTTPException as exc:
            failed_count += 1
            results.append(
                AssignmentBulkItemResponse(
                    email=email,
                    status="failed",
                    message=str(exc.detail),
                    student_id=student.id,
                )
            )

    return AssignmentBulkResponse(
        test_id=test_id,
        summary={"assigned": assigned_count, "failed": failed_count, "total": len(normalized_emails)},
        results=results,
    )
