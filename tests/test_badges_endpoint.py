import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from routes.badges import get_badges  # noqa: E402


class BadgeEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_badges_endpoint_returns_empty_canonical_envelope(self):
        payload = await get_badges("alice")

        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["platform"], "codechef")
        self.assertEqual(payload["username"], "alice")
        self.assertEqual(payload["data"], {"count": 0, "active": None, "list": []})


if __name__ == "__main__":
    unittest.main()
