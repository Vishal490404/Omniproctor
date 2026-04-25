from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.api import api_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


NEW_BEHAVIOR_EVENT_VALUES: tuple[str, ...] = (
    "FOCUS_LOSS",
    "FOCUS_REGAIN",
    "MONITOR_COUNT_CHANGE",
    "KEYSTROKE",
    "BLOCKED_HOTKEY",
    "CLIPBOARD_COPY",
    "CLIPBOARD_PASTE",
    "VM_DETECTED",
    "SUSPICIOUS_PROCESS",
    "NETWORK_BLOCKED",
    "FULLSCREEN_EXIT",
    "RENDERER_CRASH",
    "WARNING_DELIVERED",
)


def ensure_schema_compatibility() -> None:
    # Keep existing Docker volumes usable when new model columns are introduced.
    if engine.dialect.name != "postgresql":
        return

    # ALTER TYPE ... ADD VALUE cannot run inside a transaction in older
    # Postgres versions, so we use AUTOCOMMIT for the enum upgrade.
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        for value in NEW_BEHAVIOR_EVENT_VALUES:
            conn.execute(
                text(f"ALTER TYPE behavioreventtype ADD VALUE IF NOT EXISTS '{value}'")
            )

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                ALTER TABLE tests
                ADD COLUMN IF NOT EXISTS start_time TIMESTAMPTZ
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE tests
                ADD COLUMN IF NOT EXISTS end_time TIMESTAMPTZ
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE tests
                ADD COLUMN IF NOT EXISTS max_attempts INTEGER
                """
            )
        )

        conn.execute(
            text(
                """
                UPDATE tests
                SET start_time = COALESCE(start_time, created_at, NOW())
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE tests
                SET end_time = COALESCE(end_time, NOW() + INTERVAL '2 hours')
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE tests
                SET max_attempts = COALESCE(max_attempts, 1)
                """
            )
        )

        conn.execute(
            text(
                """
                ALTER TABLE tests
                ALTER COLUMN start_time SET NOT NULL
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE tests
                ALTER COLUMN end_time SET NOT NULL
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE tests
                ALTER COLUMN max_attempts SET NOT NULL
                """
            )
        )


@app.on_event("startup")
def startup() -> None:
    # Create base schema first so ensure_schema_compatibility's ALTER TABLE
    # statements have something to alter on a fresh database.
    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility()


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(api_router, prefix=settings.api_v1_prefix)
