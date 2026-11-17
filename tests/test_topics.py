import time

import pytest

from core import enrichment
from core.runtime import RequestState, state
from models.profile import CodeChefProfileResponse
from services import refresh, topics
from services.canonical_mapper import stats_from


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


class FakeJob:
    def __init__(self, subject):
        self.payload = {"subject": subject}
        self.data = {}

    async def save(self):
        return None


@pytest.fixture
def store(monkeypatch):
    """In-memory stand-in for Redis, patched where enrichment looks it up."""
    values = {}

    async def get_json(key):
        return values.get(key)

    async def get_many(keys):
        return [values.get(key) for key in keys]

    async def set_json(key, value, ttl):
        values[key] = value
        return True

    async def enqueue(kind, subject):
        return False

    monkeypatch.setattr(enrichment, "get_json", get_json)
    monkeypatch.setattr(enrichment, "get_many", get_many)
    monkeypatch.setattr(enrichment, "set_json", set_json)
    monkeypatch.setattr(enrichment, "enqueue", enqueue)
    return values


@pytest.mark.anyio
async def test_discover_only_counts_accepted(monkeypatch) -> None:
    async def fake_page(handle: str, page: int) -> dict:
        return {"max_page": 1, "content": PAGE_0_HTML}

    monkeypatch.setattr(refresh, "_fetch_recent_page", fake_page)

    codes, cursor, complete = await refresh.discover("demo", None)

    assert codes == ["TSHIRTS"]
    assert complete is True


@pytest.mark.anyio
async def test_refresh_tallies_and_sorts_then_reads_from_cache(store) -> None:
    async def discover(handle, cursor):
        return ["TSHIRTS", "FLOW001"], "1", True

    fake_tags = {"TSHIRTS": ["Advanced DP", "Bit Manipulation"], "FLOW001": ["Basic Programming", "Advanced DP"]}

    async def fetch_tags(code):
        return fake_tags[code]

    job = FakeJob("demo")
    # Discovery finishes on its only page, so one slice also tags both codes.
    assert await enrichment.refresh_topics(job, discover, fetch_tags) is True

    result = await topics.build_topic_analysis("demo")

    assert [(t.topic, t.count) for t in result] == [
        ("Advanced DP", 2),
        ("Basic Programming", 1),
        ("Bit Manipulation", 1),
    ]


@pytest.mark.anyio
async def test_failed_tag_fetch_is_not_cached_as_empty(store) -> None:
    async def discover(handle, cursor):
        return ["TSHIRTS"], "1", True

    async def failing(code):
        raise RuntimeError("CodeChef problem unavailable")

    job = FakeJob("demo")
    with pytest.raises(RuntimeError):
        await enrichment.refresh_topics(job, discover, failing)

    assert enrichment.tag_key("TSHIRTS") not in store
    assert enrichment.key("demo") not in store


@pytest.mark.anyio
async def test_build_topic_analysis_empty_without_cache(store) -> None:
    assert await topics.build_topic_analysis("demo") == []


@pytest.mark.anyio
async def test_complete_topics_leave_response_cacheable(store) -> None:
    store[enrichment.key("demo")] = {
        "topics": [{"topic": "Arrays", "count": 3}],
        "covered": 1, "total": 1, "complete": True, "updatedAt": time.time(),
    }
    current = RequestState(deadline=time.monotonic() + 5, client=None)
    token = state.set(current)
    try:
        result = await topics.build_topic_analysis("demo")
    finally:
        state.reset(token)

    assert [t.topic for t in result] == ["Arrays"]
    assert current.meta == {}


@pytest.mark.anyio
async def test_partial_topics_mark_response_uncacheable(store) -> None:
    store[enrichment.key("demo")] = {
        "topics": [{"topic": "Arrays", "count": 1}],
        "covered": 5, "total": 10, "complete": False, "updatedAt": time.time(),
    }
    current = RequestState(deadline=time.monotonic() + 5, client=None)
    token = state.set(current)
    try:
        await topics.build_topic_analysis("demo")
    finally:
        state.reset(token)

    assert current.meta["topics"]["status"] == "partial"
    assert current.meta["topics"]["covered"] == 5


@pytest.mark.anyio
async def test_stats_from_populates_topic_analysis(monkeypatch) -> None:
    async def fake_build(handle: str):
        return [topics.TopicCount(topic="Arrays", count=3)]

    monkeypatch.setattr(topics, "build_topic_analysis", fake_build)

    profile = CodeChefProfileResponse(success=True, status=200, totalSolved=10)
    stats = await stats_from(profile, "demo")

    assert [t.topic for t in stats.topicAnalysis] == ["Arrays"]
