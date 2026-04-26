"""Tests for the bulk telemetry ingestion endpoint.

Auth model: the kiosk POSTs telemetry using a per-attempt capability
token issued at attempt-start time, NOT the student's WebClient JWT.
The token is bound to a single ``test_attempts.id``, so a token for
attempt A must not be usable to write events to attempt B - and a
plain student JWT must not work either.
"""

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


def test_kiosk_token_can_post_batch(client, kiosk_token, assigned_attempt):
    response = client.post(
        _batch_url(assigned_attempt.id),
        headers=auth_header(kiosk_token),
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
    assert body["latest_warning_id"] in (None, 0)


def test_empty_batch_is_accepted_as_noop(client, kiosk_token, assigned_attempt):
    response = client.post(
        _batch_url(assigned_attempt.id),
        headers=auth_header(kiosk_token),
        json={"events": []},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] == 0
    assert body["rejected"] == 0


def test_batch_over_cap_is_rejected_by_validator(
    client, kiosk_token, assigned_attempt
):
    big = [_sample_event("FOCUS_LOSS") for _ in range(MAX_BATCH_SIZE + 1)]
    response = client.post(
        _batch_url(assigned_attempt.id),
        headers=auth_header(kiosk_token),
        json={"events": big},
    )
    assert response.status_code == 422


def test_kiosk_token_cannot_post_to_other_attempt(
    client, kiosk_token, other_attempt
):
    """A token bound to attempt A must not write to attempt B."""
    response = client.post(
        _batch_url(other_attempt.id),
        headers=auth_header(kiosk_token),
        json={"events": [_sample_event()]},
    )
    assert response.status_code == 403


def test_student_jwt_cannot_post_batch(
    client, student_token, assigned_attempt
):
    """The plain student JWT is no longer accepted on kiosk endpoints -
    callers must use the kiosk capability token. This is the whole
    point of the new auth model: short-lived student sessions don't
    have to keep working past the WebClient login expiry.
    """
    response = client.post(
        _batch_url(assigned_attempt.id),
        headers=auth_header(student_token),
        json={"events": [_sample_event()]},
    )
    assert response.status_code == 401


def test_teacher_jwt_cannot_post_batch(
    client, teacher_token, assigned_attempt
):
    response = client.post(
        _batch_url(assigned_attempt.id),
        headers=auth_header(teacher_token),
        json={"events": [_sample_event()]},
    )
    assert response.status_code == 401


def test_unknown_severity_is_normalized_to_info(
    client, kiosk_token, assigned_attempt
):
    response = client.post(
        _batch_url(assigned_attempt.id),
        headers=auth_header(kiosk_token),
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
    kiosk_token,
    teacher_token,
    assigned_attempt,
):
    # Teacher sends a warning first (uses staff JWT - unchanged).
    send = client.post(
        f"/api/v1/proctor/attempts/{assigned_attempt.id}/warnings",
        headers=auth_header(teacher_token),
        json={"message": "Please stay focused", "severity": "warn"},
    )
    assert send.status_code == 200
    warning_id = send.json()["id"]

    # Kiosk pushes a batch with its capability token and gets the
    # latest_warning_id back so the warning poller can advance.
    resp = client.post(
        _batch_url(assigned_attempt.id),
        headers=auth_header(kiosk_token),
        json={"events": [_sample_event()]},
    )
    assert resp.status_code == 200
    assert resp.json()["latest_warning_id"] == warning_id
