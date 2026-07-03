import pytest

from services import topics
from services.canonical_mapper import stats_from
from models.profile import CodeChefProfileResponse


PAGE_0_HTML = """
<table class="dataTable">
<tbody>
<tr><td title='01:00'>t</td><td title='TSHIRTS'><a href='/problems/TSHIRTS'>TSHIRTS</a></td>
<td title='(100)'><span title='accepted'>ok</span></td><td>C++</td><td>x</td></tr>
<tr><td title='02:00'>t</td><td title='FLOW001'><a href='/problems/FLOW001'>FLOW001</a></td>
<td title='(0)'><span title='wrong answer'>bad</span></td><td>C++</td><td>x</td></tr>
<tr><td title='03:00'>t</td><td title='TSHIRTS'><a href='/problems/TSHIRTS'>TSHIRTS</a></td>
<td title='(100)'><span title='accepted'>ok</span></td><td>C++</td><td>x</td></tr>
</tbody>
</table>
"""


@pytest.mark.anyio
async def test_fetch_solved_codes_only_counts_accepted(monkeypatch) -> None:
    async def fake_page(handle: str, page: int) -> dict:
        return {"max_page": 1, "content": PAGE_0_HTML}

    monkeypatch.setattr(topics, "_fetch_recent_page", fake_page)

    codes = await topics._fetch_solved_codes("demo")

    assert codes == {"TSHIRTS"}


@pytest.mark.anyio
async def test_build_topic_analysis_tallies_and_sorts(monkeypatch) -> None:
    async def fake_codes(handle: str, max_pages: int = 40):
        return {"TSHIRTS", "FLOW001"}

    fake_tags = {"TSHIRTS": ["Advanced DP", "Bit Manipulation"], "FLOW001": ["Basic Programming"]}

    async def fake_problem_tags(code: str):
        return fake_tags.get(code, [])

    monkeypatch.setattr(topics, "_fetch_solved_codes", fake_codes)
    monkeypatch.setattr(topics, "_fetch_problem_tags", fake_problem_tags)

    result = await topics.build_topic_analysis("demo")

    as_dict = {t.topic: t.count for t in result}
    assert as_dict == {"Advanced DP": 1, "Bit Manipulation": 1, "Basic Programming": 1}


@pytest.mark.anyio
async def test_build_topic_analysis_empty_when_no_codes(monkeypatch) -> None:
    async def fake_codes(handle: str, max_pages: int = 40):
        return set()

    monkeypatch.setattr(topics, "_fetch_solved_codes", fake_codes)

    result = await topics.build_topic_analysis("demo")

    assert result == []


@pytest.mark.anyio
async def test_stats_from_populates_topic_analysis(monkeypatch) -> None:
    async def fake_build(handle: str):
        return [topics.TopicCount(topic="Arrays", count=3)]

    monkeypatch.setattr(topics, "build_topic_analysis", fake_build)

    profile = CodeChefProfileResponse(success=True, status=200, totalSolved=10)
    stats = await stats_from(profile, "demo")

    assert [t.topic for t in stats.topicAnalysis] == ["Arrays"]
