from datetime import datetime, timedelta, timezone


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_teacher_create_assign_student_and_student_dashboard(
    client,
    teacher_token,
    student_token,
    student_user,
):
    now = datetime.now(timezone.utc)
    create_resp = client.post(
        "/api/v1/tests",
        headers=auth_header(teacher_token),
        json={
            "name": "Midterm",
            "description": "Physics",
            "external_link": "https://example.com/midterm",
            "is_active": True,
            "start_time": (now - timedelta(hours=1)).isoformat(),
            "end_time": (now + timedelta(hours=2)).isoformat(),
        },
    )
    assert create_resp.status_code == 200
    test_id = create_resp.json()["id"]

    assign_resp = client.post(
        f"/api/v1/tests/{test_id}/students/{student_user.id}",
        headers=auth_header(teacher_token),
        json={"note": "Front row"},
    )
    assert assign_resp.status_code == 200

    dashboard_resp = client.get(
        "/api/v1/dashboard/me/tests",
        headers=auth_header(student_token),
    )
    assert dashboard_resp.status_code == 200
    ids = [item["id"] for item in dashboard_resp.json()]
    assert test_id in ids


def test_duplicate_assignment_returns_conflict(client, teacher_token, student_user, sample_test):
    url = f"/api/v1/tests/{sample_test.id}/students/{student_user.id}"
    first = client.post(url, headers=auth_header(teacher_token), json={"note": None})
    second = client.post(url, headers=auth_header(teacher_token), json={"note": None})

    assert first.status_code == 200
    assert second.status_code == 409


def test_student_cannot_create_test(client, student_token):
    now = datetime.now(timezone.utc)
    response = client.post(
        "/api/v1/tests",
        headers=auth_header(student_token),
        json={
            "name": "Unauthorized",
            "description": None,
            "external_link": "https://example.com/x",
            "is_active": True,
            "start_time": (now - timedelta(hours=1)).isoformat(),
            "end_time": (now + timedelta(hours=2)).isoformat(),
        },
    )
    assert response.status_code == 403


def test_proctor_can_list_students_but_cannot_create_test(client, proctor_token):
    list_resp = client.get("/api/v1/users/students", headers=auth_header(proctor_token))
    assert list_resp.status_code == 200

    now = datetime.now(timezone.utc)
    create_resp = client.post(
        "/api/v1/tests",
        headers=auth_header(proctor_token),
        json={
            "name": "P1",
            "description": "Nope",
            "external_link": "https://example.com/p1",
            "is_active": True,
            "start_time": (now - timedelta(hours=1)).isoformat(),
            "end_time": (now + timedelta(hours=2)).isoformat(),
        },
    )
    assert create_resp.status_code == 403


def test_invalid_token_returns_401(client):
    response = client.get(
        "/api/v1/tests",
        headers={"Authorization": "Bearer invalid.token.value"},
    )
    assert response.status_code == 401
