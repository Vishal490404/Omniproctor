"""Kiosk capability token service.

The kiosk runs without a logged-in user session: it receives a JWT at
attempt-start time, signed with a kiosk-only secret and scoped to a
single ``test_attempts.id``. Lifetime is tied to the exam window
(``test.end_time + kiosk_token_grace_minutes``) so telemetry and the
final End Session POST keep working long after the student's WebClient
JWT would have expired.

Why a separate token rather than reusing the student JWT?

  * Lifetime decoupling. The student JWT is short-lived (60 min by
    default). An exam can run longer than that. With this token, the
    kiosk's auth horizon is the exam itself.
  * Scope. This token can ONLY be used to act on its own ``attempt_id``
    via the kiosk-facing endpoints. If it leaks, the holder still
    cannot list other tests, read other students' events, change
    passwords, etc.
  * Statelessness. Verification is a JWT decode + a single DB lookup
    of the attempt - same cost as the existing user-token path.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from app.core.config import settings
from app.models.test import Test
from app.models.test_attempt import TestAttempt

# Distinct audience so kiosk tokens can never satisfy ``decode_access_token``
# and vice-versa, even if both happened to be signed with the same secret
# in a misconfigured deployment.
KIOSK_AUDIENCE = "omniproctor:kiosk"


def _signing_secret() -> str:
    """Return the secret used to sign kiosk tokens.

    Falls back to a derivation of ``secret_key`` so the system works
    out of the box. The derivation guarantees the kiosk secret is
    different from the user-JWT secret even if the operator never set
    ``KIOSK_TOKEN_SECRET`` explicitly.
    """
    explicit = settings.kiosk_token_secret
    if explicit:
        return explicit
    return f"{settings.secret_key}::kiosk"


def _expiry_for(test: Test) -> datetime:
    """exp = test.end_time + grace, clamped to a sane upper bound."""
    end = test.end_time
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    grace = timedelta(minutes=settings.kiosk_token_grace_minutes)
    candidate = end + grace
    # Hard ceiling so a misconfigured "100-year exam window" can't mint
    # an effectively-eternal token.
    ceiling = datetime.now(timezone.utc) + timedelta(days=14)
    return min(candidate, ceiling)


def issue_kiosk_token(attempt: TestAttempt, test: Test) -> str:
    """Mint the JWT the WebClient hands to the kiosk via the launch URL."""
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(attempt.id),
        "aud": KIOSK_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int(_expiry_for(test).timestamp()),
        # Custom claims the dep uses to bind the token to a specific
        # row. attempt_id is duplicated in ``sub`` for clarity.
        "attempt_id": attempt.id,
        "student_id": attempt.student_id,
        "test_id": attempt.test_id,
    }
    return jwt.encode(payload, _signing_secret(), algorithm=settings.algorithm)


def decode_kiosk_token(token: str) -> dict[str, Any] | None:
    """Verify signature + audience + expiry. Returns claims or None.

    Returns None on any failure - callers should translate to 401.
    """
    if not token:
        return None
    try:
        return jwt.decode(
            token,
            _signing_secret(),
            algorithms=[settings.algorithm],
            audience=KIOSK_AUDIENCE,
        )
    except JWTError:
        return None
