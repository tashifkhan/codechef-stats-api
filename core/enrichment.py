"""Cache-only topic reads and bounded, checkpointed metadata refreshes."""
import asyncio
import hashlib
import time
from collections import Counter
from core.cache import get_json, get_many, redis_enabled, set_json
from core.jobs import INLINE_BUDGET, advance_inline, enqueue
from core.runtime import remaining, state


def key(username):
    return 'topics:v2:user:' + hashlib.sha256(username.lower().encode()).hexdigest()

def tag_key(slug):
    return 'topics:v2:item:' + hashlib.sha256(slug.encode()).hexdigest()

FRESH_SECONDS = 3600


async def read_topics(username, handler=None):
    """Cached topic counts. With a handler, first advance the user's refresh job.

    The request spends at most INLINE_BUDGET seconds (and never the last 3s of
    its budget) on refresh slices, so topics fill in across requests without a
    scheduled worker. A complete, fresh snapshot returns with no upstream calls.
    """
    cached = await _snapshot(username)
    inline = handler is not None and redis_enabled()
    if not _fresh(cached) and inline:
        await advance_inline('topics', username, handler, min(INLINE_BUDGET, remaining() - 3.0))
        cached = await _snapshot(username)
    if _fresh(cached):
        return cached.get('topics', [])
    stale = bool(cached and time.time() - cached.get('updatedAt', 0) > FRESH_SECONDS)
    queued = await enqueue('topics', username)
    status = 'stale' if stale else 'partial' if cached else 'pending' if queued or inline else 'unavailable'
    current = state.get()
    if current:
        # Marks the response no-store and adds X-Data-State. Complete, fresh
        # data leaves meta empty so the response stays cacheable.
        current.meta['topics'] = {
            'status': status,
            'covered': cached.get('covered', 0) if cached else 0,
            'total': cached.get('total') if cached else None,
            'refreshQueued': queued,
        }
    return cached.get('topics', []) if cached else []


async def _snapshot(username):
    cached = await get_json(key(username))
    return cached if isinstance(cached, dict) else None


def _fresh(cached):
    return bool(cached and cached.get('complete')
                and time.time() - cached.get('updatedAt', 0) <= FRESH_SECONDS)

async def refresh_topics(job, discover, fetch_tags):
    """One discovery page or at most five metadata reads per invocation."""
    data = job.data
    # A finished job can be enqueued after the freshness window.
    if data.get('published'):
        data.clear()
    if not data.get('discovered'):
        ids, cursor, complete = await discover(job.payload['subject'], data.get('cursor'))
        data['ids'] = sorted(set(data.get('ids', [])) | set(ids))
        if cursor is not None and cursor == data.get('cursor') and not complete:
            raise RuntimeError('Discovery cursor did not advance')
        data['cursor'], data['discovered'] = cursor, complete
        await job.save()
        if not complete: return False
    ids = data.get('ids', [])
    offset = int(data.get('offset', 0))
    counts = Counter(data.get('counts', {}))
    batch = ids[offset:offset+5]
    cached = await get_many([tag_key(slug) for slug in batch])

    async def load(slug, tags):
        if tags is not None:
            return tags
        tags = await fetch_tags(slug)  # Failure raises; never cache empty on failure.
        if not isinstance(tags, list): raise RuntimeError('Invalid tag metadata')
        if not await set_json(tag_key(slug), tags, 604800):
            raise RuntimeError('Tag metadata could not be stored')
        return tags

    # One slice is a handful of independent lookups, so run them together.
    for tags in await asyncio.gather(*(load(slug, tags) for slug, tags in zip(batch, cached))):
        counts.update(set(tags))
    data['offset'], data['counts'] = offset+len(batch), dict(counts)
    complete = data['offset'] >= len(ids)
    snapshot = {'topics':[{'topic':tag,'count':n} for tag,n in sorted(counts.items(), key=lambda x:(-x[1],x[0]))],
                'covered':data['offset'], 'total':len(ids), 'complete':complete, 'updatedAt':time.time()}
    # Save the checkpoint before publishing. Replaying a slice remains idempotent.
    await job.save()
    previous = None if complete else await get_json(key(job.payload['subject']))
    # A stale refresh restarts from zero. Keep serving the last complete
    # snapshot until the rebuild finishes instead of publishing partial counts.
    keep_previous = isinstance(previous, dict) and previous.get('complete')
    if not keep_previous and not await set_json(key(job.payload['subject']), snapshot, 604800):
        raise RuntimeError('Topic snapshot could not be stored')
    data['published'] = complete
    await job.save()
    return complete
