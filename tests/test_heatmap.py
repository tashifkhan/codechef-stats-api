from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from models.codechef import CodeChefProfileResponse
from services.heatmap import fetch_heatmap


@pytest.mark.anyio
async def test_fetch_heatmap_supports_last_365(monkeypatch) -> None:
    today = date.today()
    sample_profile = CodeChefProfileResponse(
        success=True,
        status=200,
        heatMap=[
            {"date": today.isoformat(), "value": 5},
            {"date": (today - timedelta(days=120)).isoformat(), "value": 2},
            {"date": (today - timedelta(days=500)).isoformat(), "value": 1},
        ],
    )

    async def fake_fetch(handle: str) -> CodeChefProfileResponse:
        return sample_profile

    monkeypatch.setattr("services.heatmap.fetch_codechef_profile", fake_fetch)

    response = await fetch_heatmap("demo", view="last_365")

    assert response.view == "last_365"
    assert len(response.heatMap) == 2
    assert response.lastActiveDate == today.isoformat()


@pytest.mark.anyio
async def test_fetch_heatmap_supports_specific_year(monkeypatch) -> None:
    sample_profile = CodeChefProfileResponse(
        success=True,
        status=200,
        heatMap=[
            {"date": "2026-01-15", "value": 5},
            {"date": "2025-06-10", "value": 2},
            {"date": "2025-02-12", "value": 1},
            {"date": "2024-09-01", "value": 9},
        ],
    )

    async def fake_fetch(handle: str) -> CodeChefProfileResponse:
        return sample_profile

    monkeypatch.setattr("services.heatmap.fetch_codechef_profile", fake_fetch)

    response = await fetch_heatmap("demo", view="year", year=2025)

    assert response.view == "year"
    assert response.year == 2025
    assert response.availableYears == [2026, 2025, 2024]
    assert response.heatMap == [
        {"date": "2025-02-12", "value": 1},
        {"date": "2025-06-10", "value": 2},
    ]


@pytest.mark.anyio
async def test_fetch_heatmap_rejects_invalid_view(monkeypatch) -> None:
    sample_profile = CodeChefProfileResponse(success=True, status=200, heatMap=[])

    async def fake_fetch(handle: str) -> CodeChefProfileResponse:
        return sample_profile

    monkeypatch.setattr("services.heatmap.fetch_codechef_profile", fake_fetch)

    with pytest.raises(HTTPException) as exc:
        await fetch_heatmap("demo", view="weekly")

    assert exc.value.status_code == 400
