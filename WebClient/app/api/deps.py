from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.test_attempt import TestAttempt
from app.models.user import User, UserRole
from app.services.kiosk_token_service import decode_kiosk_token


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
# Separate scheme so the OpenAPI docs label kiosk endpoints clearly.
# Both schemes read the same ``Authorization: Bearer ...`` header at
# runtime; the dep below decides which decoder to apply.
kiosk_oauth_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    scheme_name="KioskAttemptToken",
    auto_error=True,
)
DBSession = Annotated[Session, Depends(get_db)]


def get_current_user(db: DBSession, token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    subject = decode_access_token(token)
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.query(User).filter(User.id == int(subject)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def role_required(*allowed_roles: UserRole) -> Callable[[User], User]:
    def dependency(current_user: CurrentUser) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user

    return dependency


AdminOrTeacher = Annotated[
    User,
    Depends(role_required(UserRole.ADMIN, UserRole.TEACHER)),
]


AdminTeacherProctor = Annotated[
    User,
    Depends(role_required(UserRole.ADMIN, UserRole.TEACHER, UserRole.PROCTOR)),
]


StudentOnly = Annotated[User, Depends(role_required(UserRole.STUDENT))]


# ---------------------------------------------------------------------------
# Kiosk (capability-token) auth
# ---------------------------------------------------------------------------
def get_kiosk_attempt(
    db: DBSession,
    token: Annotated[str, Depends(kiosk_oauth_scheme)],
) -> TestAttempt:
    """Resolve the kiosk's bearer token to the bound TestAttempt row.

    A 401 is returned for an invalid/expired/foreign-audience token, OR
    if the attempt referenced in the token has been deleted server-side
    (e.g. the test was wiped). Kiosk endpoints should always rely on
    this rather than ``CurrentUser`` so they keep working even if the
    student's WebClient session has expired.
    """
    claims = decode_kiosk_token(token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired kiosk token",
        )
    try:
        attempt_id = int(claims.get("attempt_id"))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed kiosk token",
        ) from None

    attempt = db.query(TestAttempt).filter(TestAttempt.id == attempt_id).first()
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Attempt no longer exists",
        )
    return attempt


KioskAttempt = Annotated[TestAttempt, Depends(get_kiosk_attempt)]


@dataclass
class WarningReader:
    """Result of the polymorphic auth used by the warnings-list endpoint.

    Exactly one of ``user`` / ``attempt`` is populated:

      * ``user`` is set when a staff member or the candidate's own
        WebClient session is calling.
      * ``attempt`` is set when the kiosk is calling with an
        attempt-bound token (the common case during the exam).

    Endpoints branch on this to decide ``include_acknowledged`` defaults
    and to apply the right authorisation rules.
    """

    user: User | None = None
    attempt: TestAttempt | None = None

    @property
    def is_kiosk(self) -> bool:
        return self.attempt is not None and self.user is None


def get_warning_reader(
    db: DBSession,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> WarningReader:
    """Accept either a kiosk attempt token OR a standard user JWT.

    Tried in order:
      1. Kiosk decode (audience='omniproctor:kiosk'). If it succeeds we
         resolve the attempt and return a kiosk-flavoured reader.
      2. User decode (audience-less HS256). If it succeeds we return a
         user-flavoured reader.

    Anything else → 401.
    """
    kiosk_claims = decode_kiosk_token(token)
    if kiosk_claims:
        try:
            attempt_id = int(kiosk_claims.get("attempt_id"))
        except (TypeError, ValueError):
            attempt_id = None
        if attempt_id:
            attempt = db.query(TestAttempt).filter(TestAttempt.id == attempt_id).first()
            if attempt is not None:
                return WarningReader(attempt=attempt)
        # Fall through to user decode rather than 401-ing - a malformed
        # kiosk-shaped token shouldn't lock a legitimate staff caller out.

    subject = decode_access_token(token)
    if subject:
        user = db.query(User).filter(User.id == int(subject)).first()
        if user is not None:
            return WarningReader(user=user)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token",
    )


WarningReaderDep = Annotated[WarningReader, Depends(get_warning_reader)]
