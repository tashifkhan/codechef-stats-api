"""Cache-only topic reads and bounded, checkpointed metadata refreshes."""
import hashlib
import time
from collections import Counter
from core.cache import get_json, get_many, set_json
from core.jobs import enqueue
from core.runtime import state


def key(username):
    return 'topics:v2:user:' + hashlib.sha256(username.lower().encode()).hexdigest()

def tag_key(slug):
    return 'topics:v2:item:' + hashlib.sha256(slug.encode()).hexdigest()

FRESH_SECONDS = 3600


async def read_topics(username):
    """Cached topic counts only. Never calls CodeChef from the request path."""
    cached = await get_json(key(username))
    if not isinstance(cached, dict):
        cached = None
    stale = bool(cached and time.time() - cached.get('updatedAt', 0) > FRESH_SECONDS)
    complete = bool(cached and cached.get('complete'))
    if complete and not stale:
        return cached.get('topics', [])
    queued = await enqueue('topics', username)
    status = 'stale' if stale else 'partial' if cached else 'pending' if queued else 'unavailable'
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
    for slug, tags in zip(batch, cached):
        if tags is None:
            tags = await fetch_tags(slug)  # Failure raises; never cache empty on failure.
            if not isinstance(tags, list): raise RuntimeError('Invalid tag metadata')
            if not await set_json(tag_key(slug), tags, 604800):
                raise RuntimeError('Tag metadata could not be stored')
        counts.update(set(tags))
    data['offset'], data['counts'] = offset+len(batch), dict(counts)
    complete = data['offset'] >= len(ids)
    snapshot = {'topics':[{'topic':tag,'count':n} for tag,n in sorted(counts.items(), key=lambda x:(-x[1],x[0]))],
                'covered':data['offset'], 'total':len(ids), 'complete':complete, 'updatedAt':time.time()}
    # Save the checkpoint before publishing. Replaying a slice remains idempotent.
    await job.save()
    if not await set_json(key(job.payload['subject']), snapshot, 604800):
        raise RuntimeError('Topic snapshot could not be stored')
    data['published'] = complete
    await job.save()
    return complete
