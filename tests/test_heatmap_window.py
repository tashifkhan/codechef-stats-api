"""Shared windowing behaviour for the canonical heatmap (view=all|last_365|year).

This exercises ``services.heatmap_window.window_heatmap`` directly against the
canonical ``Heatmap``/``HeatDay`` models, so it needs no network or platform
service. The helper file is identical across all six services.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from models.canonical.heatmap import HeatDay, Heatmap
from services.heatmap_window import normalize_view, window_heatmap


def _utc_today():
    # match window_heatmap, which anchors on the UTC calendar day
    return datetime.now(timezone.utc).date()


def _sample() -> Heatmap:
    today = _utc_today()
    return Heatmap(
        dailyContributions=[
            HeatDay(date=(today - timedelta(days=500)).isoformat(), count=1, level=1),
            HeatDay(date=(today - timedelta(days=120)).isoformat(), count=2, level=1),
            HeatDay(date=today.isoformat(), count=5, level=4),
        ],
        yearlyContributions=[],
    )


def test_view_all_keeps_every_day():
    hm = window_heatmap(_sample(), "all", None)
    assert hm.view == "all"
    assert len(hm.dailyContributions) == 3
    assert hm.totalSubmissions == 8


def test_view_last_365_drops_older_days():
    hm = window_heatmap(_sample(), "last_365", None)
    assert hm.view == "last_365"
    # the 500-day-old entry falls outside the trailing 365-day window
    assert len(hm.dailyContributions) == 2
    assert hm.totalSubmissions == 7
    assert hm.lastActiveDate == _utc_today().isoformat()


def test_view_year_filters_to_calendar_year():
    hm = Heatmap(
        dailyContributions=[
            HeatDay(date="2024-09-01", count=9, level=4),
            HeatDay(date="2025-02-12", count=1, level=1),
            HeatDay(date="2025-06-10", count=2, level=1),
            HeatDay(date="2026-01-15", count=5, level=4),
        ],
    )
    out = window_heatmap(hm, "year", 2025)
    assert out.view == "year"
    assert out.year == 2025
    assert [d.date for d in out.dailyContributions] == ["2025-02-12", "2025-06-10"]
    # availableYears spans the full contiguous history, newest first
    assert out.availableYears == [2026, 2025, 2024]


def test_available_years_from_supplied_range():
    hm = window_heatmap(_sample(), "all", None, available_years=[2026, 2025, 2024, 2023])
    assert hm.availableYears == [2026, 2025, 2024, 2023]


def test_invalid_view_rejected():
    with pytest.raises(HTTPException) as exc:
        window_heatmap(_sample(), "weekly", None)
    assert exc.value.status_code == 400


def test_year_view_requires_year():
    with pytest.raises(HTTPException) as exc:
        normalize_view("year", None)
    assert exc.value.status_code == 400
