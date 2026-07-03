import pytest

from models.profile import CodeChefProfileResponse
from services.profile import fetch_profile_info


@pytest.mark.anyio
async def test_fetch_profile_info_includes_total_solved(monkeypatch):
    async def fake_profile(handle: str):
        return CodeChefProfileResponse(
            success=True,
            status=200,
            name="Alice",
            currentRating=1600,
            highestRating=1700,
            totalSolved=123,
        )

    monkeypatch.setattr("services.profile.fetch_codechef_profile", fake_profile)

    response = await fetch_profile_info("alice")

    assert response.profile.totalSolved == 123
