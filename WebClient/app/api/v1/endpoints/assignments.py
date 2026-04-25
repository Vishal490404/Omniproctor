from fastapi import APIRouter

from app.api.deps import AdminOrTeacher, AdminTeacherProctor, DBSession
from app.controllers.assignment_controller import (
    assign_student_controller,
    assign_students_by_email_controller,
    list_assigned_students_controller,
    remove_student_controller,
)
from app.schemas.assignment import (
    AssignedStudentResponse,
    AssignmentBulkByEmailRequest,
    AssignmentBulkResponse,
    AssignmentCreateRequest,
    AssignmentResponse,
)

router = APIRouter()


@router.post("/{test_id}/students/bulk-email", response_model=AssignmentBulkResponse)
def bulk_assign_students_by_email(
    test_id: int,
    payload: AssignmentBulkByEmailRequest,
    db: DBSession,
    current_user: AdminOrTeacher,
):
    return assign_students_by_email_controller(db, test_id, payload, current_user.id)


@router.post("/{test_id}/students/{student_id}", response_model=AssignmentResponse)
def assign_student_to_test(
    test_id: int,
    student_id: int,
    payload: AssignmentCreateRequest,
    db: DBSession,
    current_user: AdminOrTeacher,
):
    return assign_student_controller(db, test_id, student_id, payload, current_user.id)


@router.delete("/{test_id}/students/{student_id}")
def remove_student_from_test(test_id: int, student_id: int, db: DBSession, current_user: AdminOrTeacher):
    remove_student_controller(db, test_id, student_id, current_user)
    return {"message": "Student removed from test"}


@router.get("/{test_id}/students", response_model=list[AssignedStudentResponse])
def list_assigned_students(test_id: int, db: DBSession, _: AdminTeacherProctor):
    assignments, summary_map = list_assigned_students_controller(db, test_id)

    return [
        AssignedStudentResponse(
            assignment_id=assignment.id,
            student_id=student.id,
            full_name=student.full_name,
            email=student.email,
            note=assignment.note,
            assigned_at=assignment.created_at,
            attempts_used=summary_map[student.id].attempts_used,
            attempts_remaining=summary_map[student.id].attempts_remaining,
            max_attempts=summary_map[student.id].max_attempts,
            can_attempt=summary_map[student.id].can_attempt,
        )
        for assignment, student in assignments
    ]
