"""Builds the unified cross-platform card for CodeChef from the scraped profile.

CodeChef only exposes a single HTML page, so every section is derived from one
``CodeChefProfileResponse``: the rating blob yields contests + a rating series,
the daily-submission blob yields the heatmap (with computed streaks), and the
star label yields the rank. CodeChef has no public badges, so that section is
empty. See ../UNIFIED_SCHEMA.md.
"""

from datetime import date, datetime, timedelta, timezone
from math import ceil
from typing import List, Optional

from models.codechef import CodeChefProfileResponse
from models.unified import (
    ContestHistoryItem,
    HeatDay,
    RatingPoint,
    UnifiedBadges,
    UnifiedCard,
    UnifiedContests,
    UnifiedHeatmap,
    UnifiedProfile,
    UnifiedRating,
    UnifiedStats,
    UnifiedSummary,
    YearContribution,
)
from services.profile import fetch_codechef_profile


def _to_int(value) -> Optional[int]:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _entry_date(entry: dict) -> Optional[date]:
    raw = entry.get("end_date") or entry.get("date")
    if raw:
        try:
            return datetime.fromisoformat(str(raw).split(" ")[0]).date()
        except ValueError:
            pass
    year, month, day = entry.get("getyear"), entry.get("getmonth"), entry.get("getday")
    try:
        return date(int(year), int(month), int(day))
    except (TypeError, ValueError):
        return None


def profile_from(profile: CodeChefProfileResponse, handle: str) -> UnifiedProfile:
    return UnifiedProfile(
        displayName=profile.name,
        username=handle,
        avatar=profile.profile,
        country=profile.countryName,
        countryFlag=profile.countryFlag,
        verified=False,
    )


def stats_from(profile: CodeChefProfileResponse) -> UnifiedStats:
    return UnifiedStats(
        totalSolved=profile.totalSolved or 0,
        byDifficulty={},
        topicAnalysis=[],
    )


def contests_from(profile: CodeChefProfileResponse) -> UnifiedContests:
    history: List[ContestHistoryItem] = []
    for entry in profile.ratingData:
        if not isinstance(entry, dict):
            continue
        entry_date = _entry_date(entry)
        timestamp = (
            int(datetime(entry_date.year, entry_date.month, entry_date.day, tzinfo=timezone.utc).timestamp())
            if entry_date
            else None
        )
        history.append(
            ContestHistoryItem(
                name=entry.get("name"),
                date=entry_date.isoformat() if entry_date else None,
                timestamp=timestamp,
                rating=_to_int(entry.get("rating")),
                ranking=_to_int(entry.get("rank")),
            )
        )
    return UnifiedContests(
        count=len(history),
        rating=profile.currentRating,
        maxRating=profile.highestRating,
        rank=profile.stars if profile.stars and profile.stars != "unrated" else None,
        globalRanking=profile.globalRank,
        history=history,
    )


def rating_from(profile: CodeChefProfileResponse, contests: Optional[UnifiedContests] = None) -> UnifiedRating:
    if contests is None:
        contests = contests_from(profile)
    history = [
        RatingPoint(timestamp=h.timestamp, rating=h.rating, contestName=h.name)
        for h in contests.history
        if h.rating is not None
    ]
    return UnifiedRating(current=profile.currentRating, max=profile.highestRating, history=history)


def _level(count: int, max_daily: int) -> int:
    if count <= 0 or max_daily <= 0:
        return 0
    return min(4, max(1, ceil((count / max_daily) * 4)))


def _parse_heatmap_date(raw) -> Optional[date]:
    """Parse a CodeChef daily-submission date.

    CodeChef emits non-zero-padded dates (e.g. ``"2024-8-6"``) which
    ``datetime.fromisoformat`` rejects, so split and build the date manually.
    """
    if not raw:
        return None
    text = str(raw).strip()
    try:
        return datetime.fromisoformat(text).date()
    except (ValueError, TypeError):
        pass
    parts = text.split("-")
    if len(parts) != 3:
        return None
    try:
        year, month, day = (int(p) for p in parts)
        return date(year, month, day)
    except (ValueError, TypeError):
        return None


def heatmap_from(profile: CodeChefProfileResponse) -> UnifiedHeatmap:
    date_counts: dict[date, int] = {}
    for entry in profile.heatMap:
        if not isinstance(entry, dict):
            continue
        day = _parse_heatmap_date(entry.get("date"))
        if day is None:
            continue
        date_counts[day] = date_counts.get(day, 0) + (_to_int(entry.get("value")) or 0)

    if not date_counts:
        return UnifiedHeatmap()

    active_dates = sorted(date_counts)
    max_daily = max(date_counts.values())
    total_submissions = sum(date_counts.values())

    # longest streak
    longest = current = 1
    for i in range(1, len(active_dates)):
        if active_dates[i] - active_dates[i - 1] == timedelta(days=1):
            current += 1
            longest = max(longest, current)
        else:
            current = 1

    # current streak (ending today or yesterday)
    today = datetime.now(timezone.utc).date()
    cursor = today if date_counts.get(today, 0) > 0 else (
        today - timedelta(days=1) if date_counts.get(today - timedelta(days=1), 0) > 0 else None
    )
    current_streak = 0
    while cursor is not None and date_counts.get(cursor, 0) > 0:
        current_streak += 1
        cursor -= timedelta(days=1)

    yearly: dict[int, dict] = {}
    for day, count in date_counts.items():
        bucket = yearly.setdefault(day.year, {"totalSubmissions": 0, "activeDays": 0})
        bucket["totalSubmissions"] += count
        bucket["activeDays"] += 1

    return UnifiedHeatmap(
        totalSubmissions=total_submissions,
        totalActiveDays=len(active_dates),
        currentStreak=current_streak,
        longestStreak=longest,
        maxDailySubmissions=max_daily,
        firstActiveDate=active_dates[0].isoformat(),
        lastActiveDate=active_dates[-1].isoformat(),
        dailyContributions=[
            HeatDay(date=d.isoformat(), count=date_counts[d], level=_level(date_counts[d], max_daily))
            for d in active_dates
        ],
        yearlyContributions=[
            YearContribution(year=y, totalSubmissions=v["totalSubmissions"], activeDays=v["activeDays"])
            for y, v in sorted(yearly.items())
        ],
    )


def summary_from(card: UnifiedCard) -> UnifiedSummary:
    return UnifiedSummary(
        totalSolved=card.stats.totalSolved,
        totalActiveDays=card.heatmap.totalActiveDays,
        totalContests=card.contests.count,
        currentRating=card.contests.rating,
        maxRating=card.contests.maxRating,
        rank=card.contests.rank,
        badgesCount=card.badges.count,
    )


def card_from(profile: CodeChefProfileResponse, handle: str) -> UnifiedCard:
    contests = contests_from(profile)
    return UnifiedCard(
        username=handle,
        profile=profile_from(profile, handle),
        stats=stats_from(profile),
        contests=contests,
        rating=rating_from(profile, contests),
        heatmap=heatmap_from(profile),
        badges=UnifiedBadges(),
    )


async def build_card(handle: str) -> UnifiedCard:
    profile = await fetch_codechef_profile(handle)
    return card_from(profile, handle)
