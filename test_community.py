from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from community import CommunityClient, CommunityRateLimit
from config import SearchConfig


class CommunityClientTests(unittest.TestCase):
    def test_key_is_loaded_from_environment_but_not_repr(self):
        previous = os.environ.get("NMS_ALMANAC_API_KEY")
        os.environ["NMS_ALMANAC_API_KEY"] = "test-secret"
        try:
            config = SearchConfig()
            self.assertEqual(config.community_api_key, "test-secret")
            self.assertNotIn("test-secret", repr(config))
        finally:
            if previous is None:
                os.environ.pop("NMS_ALMANAC_API_KEY", None)
            else:
                os.environ["NMS_ALMANAC_API_KEY"] = previous

    def test_hourly_budget_is_persistent_and_stops_before_exceeding_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            config = SearchConfig(community_api_key="secret", community_cache_path=Path(directory) / "community.sqlite",
                                  community_hourly_request_limit=2, community_min_request_interval=0)
            with CommunityClient(config) as client:
                client._reserve_request()
                client._reserve_request()
                with self.assertRaises(CommunityRateLimit):
                    client._reserve_request()
            with CommunityClient(config) as client:
                with self.assertRaises(CommunityRateLimit):
                    client._reserve_request()

    def test_community_cache_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            config = SearchConfig(community_api_key="secret", community_cache_path=Path(directory) / "community.sqlite")
            expected = {"found": False, "address": "0807F07FFFFF", "galaxy": 19}
            with CommunityClient(config) as client:
                client._cache(expected["address"], 18, expected)
                self.assertEqual(client._cached(expected["address"], 18), expected)


if __name__ == "__main__":
    unittest.main()
