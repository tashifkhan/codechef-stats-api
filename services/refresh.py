from core.jobs import main
from core.enrichment import refresh_topics
from services.topics import _fetch_recent_page, _accepted_codes_from_page, _fetch_problem_tags

async def discover(username, cursor):
    page = int(cursor or 0)
    payload = await _fetch_recent_page(username, page)
    total = max(1, int(payload.get('max_page') or 1))
    return list(_accepted_codes_from_page(payload.get('content',''))), str(page+1), page+1 >= total

async def handle(job):
    return await refresh_topics(job, discover, _fetch_problem_tags)

if __name__ == '__main__': main(handle)
