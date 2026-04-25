"""Per-attempt risk scoring.

The risk score summarises how suspicious the recent telemetry from a single
candidate looks. It is computed as a weighted sum over a sliding 60 second
window of behavior events, capped at 100.

Used by:
  * the live monitoring endpoint (one row per active attempt)
  * the auto-alert popup on the teacher dashboard

Weights are intentionally documented as constants so they can be tuned
without spelunking through the code. None of the values are based on a
formal study - they are sensible defaults that put genuine cheating
attempts firmly in the "warn" / "critical" bands while leaving room for
honest students to score under 20.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.behavior_event import BehaviorEvent, BehaviorEventType


# ---------------------------------------------------------------------------
# Weight table
# ---------------------------------------------------------------------------
EVENT_WEIGHTS: dict[BehaviorEventType, int] = {
    # Persistent / one-shot serious indicators
    BehaviorEventType.VM_DETECTED: 30,
    BehaviorEventType.SUSPICIOUS_PROCESS: 20,
    BehaviorEventType.MONITOR_COUNT_CHANGE: 15,
    BehaviorEventType.RENDERER_CRASH: 10,
    BehaviorEventType.FULLSCREEN_EXIT: 8,

    # Recurrent suspicious activity
    BehaviorEventType.FOCUS_LOSS: 5,
    BehaviorEventType.NETWORK_BLOCKED: 4,
    BehaviorEventType.BLOCKED_HOTKEY: 3,
    BehaviorEventType.CLIPBOARD_PASTE: 6,
    BehaviorEventType.CLIPBOARD_COPY: 4,
    BehaviorEventType.WINDOW_SWITCH: 5,
    BehaviorEventType.TAB_SWITCH: 5,
    BehaviorEventType.PASTE: 6,
    BehaviorEventType.COPY: 4,

    # Background / informational - still tracked but cheap.
    BehaviorEventType.KEYSTROKE: 0,
    BehaviorEventType.KEYBOARD_PRESS: 0,
    BehaviorEventType.FOCUS_REGAIN: 0,
    BehaviorEventType.WARNING_DELIVERED: 0,
}

# A single severity=critical event always pushes the score above the
# auto-alert threshold so the teacher sees it immediately.
CRITICAL_FLOOR = 60

# Hard cap so the UI's progress bar stays bounded.
MAX_SCORE = 100

# Risk band thresholds used by the frontend for color coding.
RISK_BAND_OK = 20
RISK_BAND_WARN = 50
RISK_BAND_CRITICAL = 75

WINDOW_SECONDS = 60


@dataclass
class RiskBreakdown:
    score: int
    band: str  # "ok" | "warn" | "critical"
    top_contributors: list[tuple[str, int]]  # [(event_type, weighted_total), ...]
    event_count: int
    has_critical_event: bool


def _band_for(score: int) -> str:
    if score >= RISK_BAND_CRITICAL:
        return "critical"
    if score >= RISK_BAND_WARN:
        return "warn"
    return "ok"


def score_from_events(events: Iterable[BehaviorEvent]) -> RiskBreakdown:
    """Pure function so the unit tests don't need a DB."""
    totals: dict[str, int] = {}
    has_critical = False
    count = 0

    for ev in events:
        count += 1
        weight = EVENT_WEIGHTS.get(ev.event_type, 1)
        if (ev.severity or "").lower() == "critical":
            weight = max(weight, 25)
            has_critical = True
        elif (ev.severity or "").lower() == "warn":
            weight = max(weight, 5)

        key = ev.event_type.value if hasattr(ev.event_type, "value") else str(ev.event_type)
        totals[key] = totals.get(key, 0) + weight

    raw_score = sum(totals.values())
    if has_critical:
        raw_score = max(raw_score, CRITICAL_FLOOR)

    score = min(raw_score, MAX_SCORE)
    top = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:3]
    return RiskBreakdown(
        score=score,
        band=_band_for(score),
        top_contributors=top,
        event_count=count,
        has_critical_event=has_critical,
    )


def compute_attempt_risk(
    db: Session,
    attempt_id: int,
    *,
    window_seconds: int = WINDOW_SECONDS,
) -> RiskBreakdown:
    """Compute the risk score for one attempt over the last N seconds."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    rows = (
        db.query(BehaviorEvent)
        .filter(
            BehaviorEvent.attempt_id == attempt_id,
            BehaviorEvent.event_time >= cutoff,
        )
        .all()
    )
    return score_from_events(rows)
