from datetime import date, timedelta

from fastapi import HTTPException

from models.codechef import CodeChefHeatmapResponse
from services.profile import fetch_codechef_profile


def _parse_entry_date(value: str) -> date | None:
    parts = value.split("-")
    if len(parts) != 3:
        return None

    try:
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None


def _normalize_entries(entries: list[dict]) -> list[dict[str, date | str | int]]:
    normalized_entries: list[dict[str, date | str | int]] = []

    for entry in entries:
        raw_date = str(entry.get("date", ""))
        parsed_date = _parse_entry_date(raw_date)
        if parsed_date is None:
            continue

        try:
            value = int(entry.get("value", 0))
        except (TypeError, ValueError):
            value = 0

        normalized_entries.append(
            {
                "date_obj": parsed_date,
                "date": parsed_date.isoformat(),
                "value": value,
            }
        )

    normalized_entries.sort(key=lambda entry: entry["date_obj"])
    return normalized_entries


def _normalize_view(view: str, year: int | None) -> tuple[str, int | None]:
    normalized_view = view.lower().strip().replace("-", "_")
    aliases = {
        "365": "last_365",
        "last365": "last_365",
        "last_year": "last_365",
    }
    normalized_view = aliases.get(normalized_view, normalized_view)

    if year is not None and normalized_view == "all":
        normalized_view = "year"

    if normalized_view not in {"all", "last_365", "year"}:
        raise HTTPException(
            status_code=400,
            detail="Invalid heatmap view. Use all, last_365, or year.",
        )

    if normalized_view == "year" and year is None:
        raise HTTPException(status_code=400, detail="The year parameter is required for view=year.")

    return normalized_view, year


def _serialize_entries(entries: list[dict[str, date | str | int]]) -> list[dict[str, str | int]]:
    return [{"date": str(entry["date"]), "value": int(entry["value"])} for entry in entries]


async def fetch_heatmap(handle: str, view: str = "all", year: int | None = None) -> CodeChefHeatmapResponse:
    profile = await fetch_codechef_profile(handle)
    normalized_view, selected_year = _normalize_view(view, year)
    normalized_entries = _normalize_entries(profile.heatMap)
    available_years = sorted({entry["date_obj"].year for entry in normalized_entries}, reverse=True)

    if normalized_view == "last_365":
        earliest_allowed = date.today() - timedelta(days=364)
        filtered_entries = [entry for entry in normalized_entries if entry["date_obj"] >= earliest_allowed]
    elif normalized_view == "year":
        filtered_entries = [entry for entry in normalized_entries if entry["date_obj"].year == selected_year]
    else:
        filtered_entries = normalized_entries

    first_active_date = str(normalized_entries[0]["date"]) if normalized_entries else None
    last_active_date = str(normalized_entries[-1]["date"]) if normalized_entries else None

    return CodeChefHeatmapResponse(
        success=profile.success,
        status=profile.status,
        handle=handle,
        view=normalized_view,
        year=selected_year if normalized_view == "year" else None,
        availableYears=available_years,
        firstActiveDate=first_active_date,
        lastActiveDate=last_active_date,
        heatMap=_serialize_entries(filtered_entries),
    )
