"""Server-side windowing for the canonical heatmap.

Slices ``dailyContributions`` to the requested view (``all`` | ``last_365`` |
``year``) and recomputes the window-scoped rollups, while keeping
``yearlyContributions`` and ``availableYears`` describing the *full* history so
the frontend year picker always shows every year since account creation.

Mirrors ``CodeTrace/src/api/unifiedClient.ts::windowUnifiedHeatmap``. The helper
reads/reassigns attributes only, so it works for both the Pydantic models and the
LeetCode dataclass ``Heatmap`` unchanged.
"""

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from fastapi import HTTPException

VALID_VIEWS = {"all", "last_365", "year"}

_VIEW_ALIASES = {
    "365": "last_365",
    "last365": "last_365",
    "last365days": "last_365",
    "days": "last_365",
    "last_year": "last_365",
}


def normalize_view(view: str, year: Optional[int]) -> tuple[str, Optional[int]]:
    """Coerce a raw view string + optional year into a canonical (view, year).

    Raises ``HTTPException(400)`` for an unknown view or a ``year`` view without a
    year. Passing a ``year`` with ``view=all`` is treated as ``view=year``.
    """
    normalized = (view or "all").lower().strip().replace("-", "_")
    normalized = _VIEW_ALIASES.get(normalized, normalized)

    if year is not None and normalized == "all":
        normalized = "year"

    if normalized not in VALID_VIEWS:
        raise HTTPException(
            status_code=400,
            detail="Invalid heatmap view. Use all, last_365, or year.",
        )
    if normalized == "year" and year is None:
        raise HTTPException(
            status_code=400,
            detail="The year parameter is required for view=year.",
        )
    return normalized, (year if normalized == "year" else None)


def _full_available_years(hm, today_year: int) -> List[int]:
    """Contiguous descending year range covering the user's full history."""
    years = [y.year for y in hm.yearlyContributions]
    if not years:
        years = [int(d.date[:4]) for d in hm.dailyContributions if d.date]
    if not years:
        return [today_year]
    low, high = min(years), max(max(years), today_year)
    return list(range(high, low - 1, -1))


def window_heatmap(hm, view: str = "all", year: Optional[int] = None, available_years: Optional[List[int]] = None):
    """Slice ``hm`` in place to ``view`` and return it.

    ``available_years`` lets platforms that expose an account-creation date supply
    the authoritative full range; otherwise it is derived from the data.
    """
    view, year = normalize_view(view, year)
    today = datetime.now(timezone.utc).date()

    hm.availableYears = available_years or _full_available_years(hm, today.year)
    hm.view = view
    hm.year = year

    days = sorted(hm.dailyContributions, key=lambda d: d.date)

    if view == "year":
        start, end = f"{year}-01-01", f"{year}-12-31"
        sliced = [d for d in days if d.date[:4] == str(year)]
    elif view == "last_365":
        start = (today - timedelta(days=364)).isoformat()
        end = today.isoformat()
        sliced = [d for d in days if start <= d.date <= end]
    else:  # all
        sliced = days
        start = days[0].date if days else None
        end = days[-1].date if days else None

    hm.dailyContributions = sliced
    hm.startDate = start
    hm.endDate = end

    active = [d for d in sliced if d.count > 0]
    hm.totalSubmissions = sum(d.count for d in sliced)
    hm.totalActiveDays = len(active)
    hm.maxDailySubmissions = max((d.count for d in sliced), default=0)
    hm.firstActiveDate = active[0].date if active else None
    hm.lastActiveDate = active[-1].date if active else None

    # longest run of consecutive active days within the window
    longest = current = 0
    prev: Optional[date] = None
    for d in active:
        cur = date.fromisoformat(d.date)
        current = current + 1 if (prev is not None and (cur - prev).days == 1) else 1
        longest = max(longest, current)
        prev = cur
    hm.longestStreak = longest

    # current streak ending today (or yesterday) within the window
    active_dates = {d.date for d in active}
    cursor = today
    if cursor.isoformat() not in active_dates:
        cursor -= timedelta(days=1)
    streak = 0
    while cursor.isoformat() in active_dates:
        streak += 1
        cursor -= timedelta(days=1)
    hm.currentStreak = streak

    return hm
