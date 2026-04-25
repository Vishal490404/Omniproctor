"""Pure-function unit tests for the risk scorer.

These never touch the DB - we synthesise lightweight ``BehaviorEvent``
stand-ins so the weight table can be exercised quickly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.models.behavior_event import BehaviorEventType
from app.services.risk_scorer import (
    CRITICAL_FLOOR,
    EVENT_WEIGHTS,
    MAX_SCORE,
    RISK_BAND_CRITICAL,
    RISK_BAND_WARN,
    score_from_events,
)


@dataclass
class _StubEvent:
    """Minimal duck-typed BehaviorEvent for the pure scorer."""

    event_type: BehaviorEventType
    severity: str = "info"
    event_time: datetime = datetime.now(timezone.utc)


def test_empty_event_stream_is_zero_score():
    breakdown = score_from_events([])
    assert breakdown.score == 0
    assert breakdown.band == "ok"
    assert breakdown.event_count == 0
    assert breakdown.has_critical_event is False
    assert breakdown.top_contributors == []


def test_focus_loss_uses_documented_weight():
    events = [_StubEvent(BehaviorEventType.FOCUS_LOSS, "warn") for _ in range(2)]
    breakdown = score_from_events(events)
    expected = EVENT_WEIGHTS[BehaviorEventType.FOCUS_LOSS] * 2
    assert breakdown.score == expected
    assert breakdown.band == "ok"
    assert breakdown.event_count == 2


def test_critical_event_pushes_above_alert_floor():
    events = [_StubEvent(BehaviorEventType.VM_DETECTED, "critical")]
    breakdown = score_from_events(events)
    assert breakdown.has_critical_event is True
    assert breakdown.score >= CRITICAL_FLOOR
    assert breakdown.band in {"warn", "critical"}


def test_score_is_capped_at_max():
    events = [
        _StubEvent(BehaviorEventType.VM_DETECTED, "critical"),
        _StubEvent(BehaviorEventType.SUSPICIOUS_PROCESS, "warn"),
        _StubEvent(BehaviorEventType.MONITOR_COUNT_CHANGE, "warn"),
        *[_StubEvent(BehaviorEventType.FOCUS_LOSS, "warn") for _ in range(20)],
    ]
    breakdown = score_from_events(events)
    assert breakdown.score == MAX_SCORE
    assert breakdown.band == "critical"


def test_top_contributors_are_sorted_descending():
    events = [
        *[_StubEvent(BehaviorEventType.FOCUS_LOSS, "warn") for _ in range(3)],
        _StubEvent(BehaviorEventType.MONITOR_COUNT_CHANGE, "warn"),
        _StubEvent(BehaviorEventType.BLOCKED_HOTKEY, "warn"),
    ]
    breakdown = score_from_events(events)
    assert len(breakdown.top_contributors) <= 3
    weights = [w for _, w in breakdown.top_contributors]
    assert weights == sorted(weights, reverse=True)


def test_warn_severity_floors_low_weight_events():
    """Even an unusually low-weight event becomes ≥5 if marked ``warn``."""
    events = [_StubEvent(BehaviorEventType.KEYSTROKE, "warn") for _ in range(3)]
    breakdown = score_from_events(events)
    # KEYSTROKE has weight 0 by default; warn floor of 5 applies per event.
    assert breakdown.score >= 15


def test_band_thresholds_are_consistent():
    """Building a stream that lands in each documented band."""
    # OK
    ok_events = [_StubEvent(BehaviorEventType.FOCUS_LOSS, "warn")]
    assert score_from_events(ok_events).band == "ok"

    # WARN
    warn_events = [
        _StubEvent(BehaviorEventType.MONITOR_COUNT_CHANGE, "warn"),
        _StubEvent(BehaviorEventType.SUSPICIOUS_PROCESS, "warn"),
        _StubEvent(BehaviorEventType.FULLSCREEN_EXIT, "warn"),
    ]
    warn_breakdown = score_from_events(warn_events)
    assert warn_breakdown.score >= RISK_BAND_WARN
    assert warn_breakdown.score < RISK_BAND_CRITICAL
    assert warn_breakdown.band == "warn"

    # CRITICAL via single critical-severity event
    crit_events = [_StubEvent(BehaviorEventType.VM_DETECTED, "critical")]
    crit_breakdown = score_from_events(crit_events)
    assert crit_breakdown.score >= CRITICAL_FLOOR
