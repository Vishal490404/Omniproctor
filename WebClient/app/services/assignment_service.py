from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assignment import TestAssignment
from app.models.test import Test
from app.models.user import User, UserRole


def ensure_student(user: User) -> None:
    if user.role != UserRole.STUDENT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is not a student")


def assign_student(
    db: Session,
    test: Test,
    student: User,
    added_by_user_id: int,
    note: str | None,
) -> TestAssignment:
    ensure_student(student)

    existing = (
        db.query(TestAssignment)
        .filter(TestAssignment.test_id == test.id, TestAssignment.student_id == student.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Student already assigned")

    assignment = TestAssignment(
        test_id=test.id,
        student_id=student.id,
        added_by=added_by_user_id,
        note=note,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def unassign_student(db: Session, test_id: int, student_id: int) -> None:
    assignment = (
        db.query(TestAssignment)
        .filter(TestAssignment.test_id == test_id, TestAssignment.student_id == student_id)
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    db.delete(assignment)
    db.commit()
