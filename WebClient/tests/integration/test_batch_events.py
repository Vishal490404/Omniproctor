"""Tests for the bulk telemetry ingestion endpoint."""

from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.behavior import MAX_BATCH_SIZE


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _batch_url(attempt_id: int) -> str:
    return f"/api/v1/behavior/attempts/{attempt_id}/events:batch"


def _sample_event(event_type: str = "FOCUS_LOSS", severity: str = "warn") -> dict:
    return {
        "event_type": event_type,
        "severity": severity,
        "payload": {"hwnd": 1234, "proc": "explorer.exe"},
        "event_time": datetime.now(timezone.utc).isoformat(),
    }


def test_owning_student_can_post_batch(client, student_token, assigned_attempt):
    response = client.post(
        _batch_url(assigned_attempt.id),
        headers=auth_header(student_token),
        json={
            "events": [
                _sample_event("FOCUS_LOSS"),
                _sample_event("KEYSTROKE", severity="info"),
                _sample_event("CLIPBOARD_COPY", severity="info"),
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] == 3
    assert body["rejected"] == 0
    # No warnings exist yet for this attempt.
    assert body["latest_warning_id"] in (None, 0)


def test_empty_batch_is_accepted_as_noop(client, student_token, assigned_attempt):
    response = client.post(
        _batch_url(assigned_attempt.id),
        headers=auth_header(student_token),
        json={"events": []},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] == 0
    assert body["rejected"] == 0


def test_batch_over_cap_is_rejected_by_validator(
    client, student_token, assigned_attempt
):
    big = [_sample_event("FOCUS_LOSS") for _ in range(MAX_BATCH_SIZE + 1)]
    response = client.post(
        _batch_url(assigned_attempt.id),
        headers=auth_header(student_token),
        json={"events": big},
    )
    assert response.status_code == 422


def test_other_student_cannot_post_batch(
    client, other_student_token, assigned_attempt
):
    response = client.post(
        _batch_url(assigned_attempt.id),
        headers=auth_header(other_student_token),
        json={"events": [_sample_event()]},
    )
    assert response.status_code == 403


def test_teacher_cannot_post_batch_as_student(
    client, teacher_token, assigned_attempt
):
    """The batch endpoint is gated by ``StudentOnly`` - non-students get 403."""
    response = client.post(
        _batch_url(assigned_attempt.id),
        headers=auth_header(teacher_token),
        json={"events": [_sample_event()]},
    )
    assert response.status_code == 403


def test_unknown_severity_is_normalized_to_info(
    client, student_token, assigned_attempt
):
    response = client.post(
        _batch_url(assigned_attempt.id),
        headers=auth_header(student_token),
        json={
            "events": [
                {
                    "event_type": "FOCUS_LOSS",
                    "severity": "ohno",
                    "payload": {},
                }
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["accepted"] == 1


def test_batch_endpoint_returns_latest_warning_id(
    client,
    student_token,
    teacher_token,
    assigned_attempt,
):
    # Teacher sends a warning first.
    send = client.post(
        f"/api/v1/proctor/attempts/{assigned_attempt.id}/warnings",
        headers=auth_header(teacher_token),
        json={"message": "Please stay focused", "severity": "warn"},
    )
    assert send.status_code == 200
    warning_id = send.json()["id"]

    # Then the kiosk pushes a batch and expects to see the warning id back.
    resp = client.post(
        _batch_url(assigned_attempt.id),
        headers=auth_header(student_token),
        json={"events": [_sample_event()]},
    )
    assert resp.status_code == 200
    assert resp.json()["latest_warning_id"] == warning_id
