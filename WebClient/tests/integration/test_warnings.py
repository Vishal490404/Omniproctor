"""Tests for the teacher → student proctor warning channel."""

from __future__ import annotations


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _send_url(attempt_id: int) -> str:
    return f"/api/v1/proctor/attempts/{attempt_id}/warnings"


def _list_url(attempt_id: int, since_id: int = 0) -> str:
    qs = f"?since_id={since_id}" if since_id else ""
    return f"/api/v1/proctor/attempts/{attempt_id}/warnings{qs}"


def _ack_url(warning_id: int) -> str:
    return f"/api/v1/proctor/warnings/{warning_id}/ack"


# ---------------------------------------------------------------------------
# Send (POST /attempts/{id}/warnings)
# ---------------------------------------------------------------------------
def test_teacher_can_send_warning_for_their_test(
    client, teacher_token, assigned_attempt
):
    response = client.post(
        _send_url(assigned_attempt.id),
        headers=auth_header(teacher_token),
        json={"message": "Eyes on the screen.", "severity": "warn"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Eyes on the screen."
    assert body["severity"] == "warn"
    assert body["attempt_id"] == assigned_attempt.id


def test_admin_can_send_warning_for_any_test(
    client, admin_token, assigned_attempt
):
    response = client.post(
        _send_url(assigned_attempt.id),
        headers=auth_header(admin_token),
        json={"message": "Admin override", "severity": "critical"},
    )
    assert response.status_code == 200
    assert response.json()["severity"] == "critical"


def test_proctor_can_send_warning(client, proctor_token, assigned_attempt):
    response = client.post(
        _send_url(assigned_attempt.id),
        headers=auth_header(proctor_token),
        json={"message": "Behave please.", "severity": "info"},
    )
    assert response.status_code == 200


def test_student_cannot_send_warning(client, student_token, assigned_attempt):
    response = client.post(
        _send_url(assigned_attempt.id),
        headers=auth_header(student_token),
        json={"message": "self-warning", "severity": "warn"},
    )
    assert response.status_code == 403


def test_send_warning_validates_message_length(
    client, teacher_token, assigned_attempt
):
    response = client.post(
        _send_url(assigned_attempt.id),
        headers=auth_header(teacher_token),
        json={"message": "", "severity": "warn"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# List (GET /attempts/{id}/warnings)
# ---------------------------------------------------------------------------
def test_owning_student_can_list_their_warnings(
    client, teacher_token, student_token, assigned_attempt
):
    sent = client.post(
        _send_url(assigned_attempt.id),
        headers=auth_header(teacher_token),
        json={"message": "Warning 1", "severity": "warn"},
    )
    assert sent.status_code == 200

    listing = client.get(
        _list_url(assigned_attempt.id),
        headers=auth_header(student_token),
    )
    assert listing.status_code == 200
    rows = listing.json()
    assert len(rows) == 1
    assert rows[0]["message"] == "Warning 1"


def test_other_student_cannot_list_warnings(
    client, teacher_token, other_student_token, assigned_attempt
):
    client.post(
        _send_url(assigned_attempt.id),
        headers=auth_header(teacher_token),
        json={"message": "secret", "severity": "warn"},
    )
    response = client.get(
        _list_url(assigned_attempt.id),
        headers=auth_header(other_student_token),
    )
    assert response.status_code == 403


def test_since_id_filters_results(
    client, teacher_token, student_token, assigned_attempt
):
    first = client.post(
        _send_url(assigned_attempt.id),
        headers=auth_header(teacher_token),
        json={"message": "first", "severity": "warn"},
    ).json()
    client.post(
        _send_url(assigned_attempt.id),
        headers=auth_header(teacher_token),
        json={"message": "second", "severity": "warn"},
    )

    response = client.get(
        _list_url(assigned_attempt.id, since_id=first["id"]),
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    rows = response.json()
    assert [r["message"] for r in rows] == ["second"]


# ---------------------------------------------------------------------------
# Ack (POST /warnings/{id}/ack)
# ---------------------------------------------------------------------------
def test_owning_student_can_ack_warning(
    client, teacher_token, student_token, assigned_attempt
):
    sent = client.post(
        _send_url(assigned_attempt.id),
        headers=auth_header(teacher_token),
        json={"message": "ack me", "severity": "warn"},
    ).json()

    response = client.post(
        _ack_url(sent["id"]),
        headers=auth_header(student_token),
        json={},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["acknowledged_at"] is not None
    assert body["delivered_at"] is not None


def test_other_student_cannot_ack_warning(
    client, teacher_token, other_student_token, assigned_attempt
):
    sent = client.post(
        _send_url(assigned_attempt.id),
        headers=auth_header(teacher_token),
        json={"message": "private ack", "severity": "warn"},
    ).json()

    response = client.post(
        _ack_url(sent["id"]),
        headers=auth_header(other_student_token),
        json={},
    )
    assert response.status_code == 403


def test_teacher_cannot_ack_warning(
    client, teacher_token, assigned_attempt
):
    """Ack is a kiosk/student concern - staff should not be able to fake it."""
    sent = client.post(
        _send_url(assigned_attempt.id),
        headers=auth_header(teacher_token),
        json={"message": "x", "severity": "warn"},
    ).json()
    response = client.post(
        _ack_url(sent["id"]),
        headers=auth_header(teacher_token),
        json={},
    )
    assert response.status_code == 403
