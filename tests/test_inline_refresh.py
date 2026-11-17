"""Topics fill in from public requests without a scheduled worker."""
import asyncio
import json
import time
import unittest
from unittest import mock

import core.enrichment as enrichment
import core.jobs as jobs


class FakeStore:
    def __init__(self):
        self.data = {}

    async def command(self, name, *args, **kwargs):
        if name == "set":
            key, value = args[0], args[1]
            if kwargs.get("nx") and key in self.data:
                return None
            self.data[key] = value
            return True
        if name == "eval":
            script, _, *rest = args
            if script == jobs.CHECKPOINT:
                lease, state_key, owner, payload = rest
                if self.data.get(lease) != owner:
                    return 0
                self.data[state_key] = json.loads(payload)
                return 1
            if script == jobs.RELEASE_LEASE:
                lease, owner = rest
                if self.data.get(lease) == owner:
                    del self.data[lease]
                    return 1
                return 0
        return None

    async def get_json(self, key):
        return self.data.get(key)

    async def get_many(self, keys):
        return [self.data.get(k) for k in keys]

    async def set_json(self, key, value, ttl=None):
        self.data[key] = value
        return True


def install(store):
    return [
        mock.patch.object(jobs, "command", store.command),
        mock.patch.object(jobs, "get_json", store.get_json),
        mock.patch.object(jobs, "redis_enabled", lambda: True),
        mock.patch.object(enrichment, "get_json", store.get_json),
        mock.patch.object(enrichment, "get_many", store.get_many),
        mock.patch.object(enrichment, "set_json", store.set_json),
        mock.patch.object(enrichment, "redis_enabled", lambda: True),
        mock.patch.object(enrichment, "enqueue", mock.AsyncMock(return_value=False)),
    ]


def make_handler(ids, tags, calls):
    async def discover(subject, cursor):
        calls.append(("discover", cursor))
        return ids, None, True

    async def fetch_tags(slug):
        calls.append(("tags", slug))
        return tags[slug]

    async def handle(job):
        return await enrichment.refresh_topics(job, discover, fetch_tags)

    return handle


class InlineRefreshTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.store = FakeStore()
        for patcher in install(self.store):
            patcher.start()
            self.addCleanup(patcher.stop)

    async def test_request_builds_topics_without_worker(self):
        ids = [f"p{i}" for i in range(7)]
        tags = {slug: ["dp"] if i % 2 else ["graphs", "dp"] for i, slug in enumerate(ids)}
        calls = []
        topics = await enrichment.read_topics("demo", make_handler(ids, tags, calls))
        self.assertEqual(topics, [{"topic": "dp", "count": 7}, {"topic": "graphs", "count": 4}])
        self.assertFalse(any(k.startswith("refresh:v1:lease:") for k in self.store.data), "lease released")

        calls.clear()
        self.assertEqual(await enrichment.read_topics("demo", make_handler(ids, tags, calls)), topics)
        self.assertEqual(calls, [], "fresh snapshot needs no upstream calls")

    async def test_budget_bounds_a_stalled_upstream(self):
        async def stalled(job):
            await asyncio.sleep(30)

        started = time.monotonic()
        done = await jobs.advance_inline("topics", "demo", stalled, 0.4)
        self.assertFalse(done)
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertFalse(any(k.startswith("refresh:v1:lease:") for k in self.store.data))

    async def test_held_lease_skips_inline_work(self):
        self.store.data["refresh:v1:lease:" + jobs.job_id("topics", "demo")] = "worker"
        handler = mock.AsyncMock(return_value=True)
        self.assertFalse(await jobs.advance_inline("topics", "demo", handler, 2.0))
        handler.assert_not_called()

    async def test_stale_rebuild_keeps_last_complete_snapshot(self):
        old = {"topics": [{"topic": "dp", "count": 9}], "covered": 9, "total": 9,
               "complete": True, "updatedAt": time.time() - 7200}
        self.store.data[enrichment.key("demo")] = old
        ids = [f"p{i}" for i in range(20)]
        tags = {slug: ["math"] for slug in ids}

        async def one_slice_then_stall(job, _h=make_handler(ids, tags, [])):
            if job.data.get("offset", 0) >= 5:
                await asyncio.sleep(30)
            return await _h(job)

        topics = await enrichment.read_topics("demo", one_slice_then_stall)
        self.assertEqual(topics, old["topics"], "partial rebuild must not replace complete data")
        self.assertEqual(self.store.data[enrichment.key("demo")], old)

    async def test_upstream_refusal_backs_off(self):
        handler = mock.AsyncMock(side_effect=RuntimeError("history unavailable"))
        self.assertFalse(await jobs.advance_inline("topics", "demo", handler, 2.0))
        self.assertEqual(handler.await_count, 1)
        state = self.store.data["refresh:v1:state:" + jobs.job_id("topics", "demo")]
        self.assertEqual(state["attempts"], 1)
        self.assertGreater(state["retryAt"], time.time())

        self.assertFalse(await jobs.advance_inline("topics", "demo", handler, 2.0))
        self.assertEqual(handler.await_count, 1, "no upstream call during backoff")

        state["retryAt"] = 0
        ok = mock.AsyncMock(return_value=True)
        self.assertTrue(await jobs.advance_inline("topics", "demo", ok, 2.0))
        state = self.store.data["refresh:v1:state:" + jobs.job_id("topics", "demo")]
        self.assertNotIn("attempts", state)
        self.assertNotIn("retryAt", state)


    async def test_pending_reports_discovery_progress(self):
        async def discovering(job):
            job.data["ids"] = sorted(set(job.data.get("ids", [])) | {"a", "b", "c"})
            job.data["cursor"] = "next"
            await job.save()
            return False

        request = mock.Mock(meta={})
        with mock.patch.object(enrichment, "state", mock.Mock(get=lambda: request)):
            self.assertEqual(await enrichment.read_topics("demo", discovering), [])
        self.assertEqual(request.meta["topics"]["status"], "pending")
        self.assertEqual(request.meta["topics"]["discovered"], 3)

    async def test_slice_looks_up_a_full_batch_concurrently(self):
        ids = [f"p{i:02d}" for i in range(enrichment.TAG_BATCH + 3)]
        in_flight = peak = 0

        async def fetch_tags(slug):
            nonlocal in_flight, peak
            in_flight += 1
            peak = max(peak, in_flight)
            await asyncio.sleep(0.01)
            in_flight -= 1
            return ["x"]

        async def discover(subject, cursor):
            return ids, None, True

        job = jobs.Job("j", "o", {"kind": "topics", "subject": "demo"}, {})
        job.save = mock.AsyncMock()
        while not job.data.get("offset"):
            await enrichment.refresh_topics(job, discover, fetch_tags)
        self.assertEqual(job.data["offset"], enrichment.TAG_BATCH)
        self.assertEqual(peak, enrichment.TAG_BATCH)

if __name__ == "__main__":
    unittest.main()
